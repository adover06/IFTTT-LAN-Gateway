# ESP32 Alarm Example

This is a minimal ESP32 HTTP server example that exposes a `POST /alarm` endpoint.
It is intended to be used with `rustplus-lan-bridge` as a LAN-only alarm target.

## Behavior
- `POST /alarm` with `{ "action": "on" }` turns the onboard LED on
- Optional `duration_s` automatically turns it off

## Notes
- The GPIO can be set to pin 2 for testing using the onboard LED.
- No authentication is used (LAN-only)
