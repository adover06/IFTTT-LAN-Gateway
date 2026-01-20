# rustplus-lan-bridge

`rustplus-lan-bridge` is a **local automation gateway** that listens directly to **Rust+ Smart Alarm events** and triggers **LAN-only IoT devices** (ESP32, relays, sirens, lights) in real time.

It runs entirely on your local machine and network — **no IFTTT, no cloud automation services, no public webhooks required**.

---

## What this does

- Connects to Rust+ the same way the official Rust+ mobile app does
- Listens for **Smart Alarm ON/OFF state changes**
- Emits high-level events like:
  - `rust_smart_alarm_on`
  - `rust_smart_alarm_off`
- Uses a **YAML config** to map those events to actions
- Sends HTTP requests to **local IoT devices** on your LAN

Example use cases:
- Turn on a real siren when your base alarm triggers
- Flash lights when someone enters your base
- Trigger multiple devices from one alarm
- Use different alarms for different real-world actions


The gateway **initiates all connections**. Nothing needs to be exposed to the internet. 

---

## Requirements

- Python 3.9+
- A Rust server with Rust+ enabled
- At least one **Smart Alarm** placed in-game
- A device on your LAN that can receive HTTP requests (ESP32, TP-Link Kasa device etc.)

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourname/rustplus-lan-bridge.git
cd rustplus-lan-bridge
```
### 2. Create a virtual environment (recommended)
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install rustplus httpx pyyaml
```

## Configuration

### 1. `data.json` (Rust+ connection details and smart alarm entityIds)

The `data.json` file will be created when you run the `FCMListener.py` file in the project root, for this to work you must have the correct token JSON which can be attained [here](https://chromewebstore.google.com/detail/rustpluspy-link-companion/gojhnmnggbnflhdcpcemeahejhcimnlf):

### 2. `config.yaml` (Device endpoints, Rules, targets, settings, etc)

See the `config.example.yaml` file for example and fomratting.

## Running

```bash
python3 main.py
```
