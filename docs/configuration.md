# Configuration

The plugin is configured by the standard `ovos-plugin-manager` config block.

```json
{
  "ovos-messagebus": {
    "autoconnect": true,
    "host": "127.0.0.1",
    "port": 8181,
    "timeout": 30,
    "source_name": "messagebus_chat_agent"
  }
}
```

## Keys

| Key            | Type | Default                  | Description                                                                                                                                                |
|----------------|------|--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `autoconnect`  | bool | `False`                  | If `True`, the plugin opens its own `MessageBusClient` on init. If `False`, you must inject a connected bus via `OVOSMessagebusChatAgent(bus=...)` or `.bind(bus)`. |
| `host`         | str  | `127.0.0.1`              | OVOS messagebus host. Only consulted when `autoconnect` is `True`.                                                                                          |
| `port`         | int  | `8181`                   | OVOS messagebus port. Only consulted when `autoconnect` is `True`.                                                                                          |
| `timeout`      | int  | `30`                     | Per-utterance wait in seconds. Refreshed every time a `speak` message arrives, so a multi-speak response does not time out mid-stream.                       |
| `source_name`  | str  | `messagebus_chat_agent`  | Value written to `context.source` on the outgoing `recognizer_loop:utterance`. OVOS routing rules that exclude `messagebus_chat_agent` can use this.        |

## Bus injection

If you already have a connected `MessageBusClient`, inject it directly. This
is the recommended path for tests, multi-tenant servers, and any deployment
that manages its own bus lifecycle:

```python
agent = OVOSMessagebusChatAgent(bus=existing_bus, config={"timeout": 15})
```

If neither `bus=` is supplied nor `autoconnect` is set, the agent has no bus
and `continue_chat` raises `RuntimeError`. Call `.bind(bus)` later to attach
one.

## OVOS config interaction

The plugin does not read `mycroft.conf` directly. All configuration flows
through the `config` dict passed to `__init__`.

---
[← Architecture](architecture.md) · [Home](README.md) · [Message flow →](message_flow.md)
