import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
import yaml
from dotenv import load_dotenv
from rustplus import RustSocket, ServerDetails, EntityEvent, EntityEventPayload

load_dotenv()


# ----------------------------
# Config schema
# ----------------------------

@dataclass
class Target:
    name: str
    url: str
    method: str = "POST"
    timeout_s: float = 3.0
    headers: Optional[Dict[str, str]] = None


@dataclass
class Rule:
    event: str
    targets: List[str]
    payload_template: Optional[Dict[str, Any]] = None


@dataclass
class Settings:
    forward_retries: int = 1
    forward_retry_backoff_s: float = 0.3
    forward_concurrency: int = 10
    # Prevent repeated triggers (seconds) per alarm+event
    cooldown_s: float = 10.0


@dataclass
class AppConfig:
    settings: Settings
    targets: Dict[str, Target]
    rules: Dict[str, Rule]


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    sraw = raw.get("settings", {}) or {}
    settings = Settings(
        forward_retries=int(sraw.get("forward_retries", 1)),
        forward_retry_backoff_s=float(sraw.get("forward_retry_backoff_s", 0.3)),
        forward_concurrency=int(sraw.get("forward_concurrency", 10)),
        cooldown_s=float(sraw.get("cooldown_s", 10.0)),
    )

    targets: Dict[str, Target] = {}
    for t in (raw.get("targets", []) or []):
        tgt = Target(
            name=t["name"],
            url=t["url"],
            method=(t.get("method") or "POST").upper(),
            timeout_s=float(t.get("timeout_s", 3.0)),
            headers=t.get("headers"),
        )
        targets[tgt.name] = tgt

    rules: Dict[str, Rule] = {}
    for r in (raw.get("rules", []) or []):
        rule = Rule(
            event=r["event"],
            targets=list(r.get("targets", [])),
            payload_template=r.get("payload_template"),
        )
        rules[rule.event] = rule

    # Validate rule targets exist
    for ev, rule in rules.items():
        for tn in rule.targets:
            if tn not in targets:
                raise ValueError(f"Rule '{ev}' references unknown target '{tn}'")

    return AppConfig(settings=settings, targets=targets, rules=rules)


# ----------------------------
# Forwarding / dispatcher
# ----------------------------

_sem: asyncio.Semaphore
_last_fire: Dict[str, float] = {}  # key -> last time


async def _forward_once(
    client: httpx.AsyncClient,
    target: Target,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    timeout = httpx.Timeout(target.timeout_s)
    headers = target.headers or {}

    if target.method == "POST":
        r = await client.post(target.url, json=payload, headers=headers, timeout=timeout)
    elif target.method == "PUT":
        r = await client.put(target.url, json=payload, headers=headers, timeout=timeout)
    elif target.method == "GET":
        r = await client.get(target.url, params=payload, headers=headers, timeout=timeout)
    else:
        return {"target": target.name, "ok": False, "error": f"Unsupported method {target.method}"}

    ok = 200 <= r.status_code < 300
    return {"target": target.name, "ok": ok, "status": r.status_code, "body": (r.text[:300] if r.text else "")}


async def forward_to_target(
    client: httpx.AsyncClient,
    cfg: AppConfig,
    target: Target,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    retries = cfg.settings.forward_retries
    backoff = cfg.settings.forward_retry_backoff_s
    last_err = None

    for attempt in range(retries + 1):
        try:
            async with _sem:
                return await _forward_once(client, target, payload)
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                await asyncio.sleep(backoff * (2 ** attempt))

    return {"target": target.name, "ok": False, "error": last_err or "unknown error"}


async def dispatch_event(cfg: AppConfig, event_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    rule = cfg.rules.get(event_name)
    if not rule:
        return {"ok": False, "error": f"No rule for event '{event_name}'"}

    payload: Dict[str, Any] = {
        "event": event_name,
        "timestamp": int(time.time()),
        "data": data,
    }
    if rule.payload_template:
        payload.update(rule.payload_template)

    async with httpx.AsyncClient() as client:
        tasks = []
        for tn in rule.targets:
            tgt = cfg.targets[tn]
            tasks.append(asyncio.create_task(forward_to_target(client, cfg, tgt, payload)))

        results = await asyncio.gather(*tasks)

    return {"ok": all(r.get("ok") for r in results), "forwarded": results}


def _cooldown_key(alarm_id: int, event_name: str) -> str:
    return f"{alarm_id}:{event_name}"


async def emit_with_cooldown(cfg: AppConfig, alarm_id: int, event_name: str, data: Dict[str, Any]) -> None:
    key = _cooldown_key(alarm_id, event_name)
    now = time.time()
    last = _last_fire.get(key, 0.0)
    if (now - last) < cfg.settings.cooldown_s:
        # Too soon; ignore
        return
    _last_fire[key] = now

    res = await dispatch_event(cfg, event_name, data)
    if res.get("ok"):
        print(f"[dispatch] {event_name} -> ok")
    else:
        print(f"[dispatch] {event_name} -> FAIL: {res}")


# ----------------------------
# Rust+ listener
# ----------------------------

def env_required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


RUST_IP = env_required("RUSTPLUS_IP")
RUST_PORT = env_required("RUSTPLUS_PORT")
STEAM_ID = int(env_required("RUSTPLUS_STEAM_ID"))
PLAYER_TOKEN = env_required("RUSTPLUS_PLAYER_TOKEN")


# Support multiple alarms: "123,456,789"
ALARM_IDS = [int(x.strip()) for x in env_required("RUSTPLUS_ALARM_ENTITY_IDS").split(",") if x.strip()]

CONFIG_PATH = os.getenv("RUSTPLUS_BRIDGE_CONFIG", "./config.yaml")
_cfg = load_config(CONFIG_PATH)
_sem = asyncio.Semaphore(_cfg.settings.forward_concurrency)

server_details = ServerDetails(RUST_IP, RUST_PORT, STEAM_ID, PLAYER_TOKEN)


def make_alarm_handler(alarm_id: int):
    @EntityEvent(server_details, alarm_id)
    async def _on_alarm(event: EntityEventPayload):
        # event.value is typically boolean-like for Smart Alarm state
        is_on = bool(event.value)
        state = "ON" if is_on else "OFF"
        print(f"[SmartAlarm {alarm_id}] -> {state}")

        event_name = "rust_smart_alarm_on" if is_on else "rust_smart_alarm_off"
        data = {
            "alarm_entity_id": alarm_id,
            "value": is_on,
        }
        await emit_with_cooldown(_cfg, alarm_id, event_name, data)

    return _on_alarm


# Register handlers for each alarm id
_handlers = [make_alarm_handler(aid) for aid in ALARM_IDS]


async def main():
    socket = RustSocket(server_details)
    await socket.connect()

    # IMPORTANT: must call get_entity_info for each entity to receive EntityEvent updates
    for aid in ALARM_IDS:
        await socket.get_entity_info(aid)

    print("Listening for Smart Alarm changes... (Ctrl+C to stop)")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
