# OVOS Messagebus Chat Plugin

An OVOS `ChatEngine` agent plugin that proxies user turns through a connected
[OpenVoiceOS](https://github.com/OpenVoiceOS) messagebus. Each `continue_chat`
call sends the latest user utterance to the OVOS pipeline and collects the
synthesized response.

The plugin reuses the `SessionManager`-owned `Session` for each `session_id`,
so multi-turn conversations preserve OVOS-side state (active skills, entity
context, response-mode flags, language). Skills that rely on
`MycroftSkill.get_response()`, common_query disambiguation, or
context-managed intents keep working across turns.

## Installation

```bash
pip install ovos-messagebus-chat-plugin
```

## Usage

### Via plugin discovery

The plugin registers under `opm.agents.chat` with name `ovos-messagebus`. Any
OVOS component that loads chat-agent plugins (e.g. `ovos-persona`) will pick it
up automatically:

```python
from ovos_plugin_manager.agents import load_chat_agent_plugin

agent_cls = load_chat_agent_plugin("ovos-messagebus")
agent = agent_cls(config={"autoconnect": True, "host": "127.0.0.1", "port": 8181})
```

### Direct programmatic use

```python
from ovos_bus_client import MessageBusClient
from ovos_messagebus_chat_plugin import OVOSMessagebusChatAgent
from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole

bus = MessageBusClient()
bus.run_in_thread()
bus.connected_event.wait()

agent = OVOSMessagebusChatAgent(bus=bus, config={"timeout": 15})

reply = agent.continue_chat(
    [AgentMessage(role=MessageRole.USER, content="what time is it?")],
    session_id="kitchen",
)
print(reply.content)

# next turn — same session_id reuses the Session, so OVOS skills that need
# follow-up context (get_response, common_query, dialog flow) keep working
reply = agent.continue_chat(
    [
        AgentMessage(role=MessageRole.USER, content="what time is it?"),
        AgentMessage(role=MessageRole.ASSISTANT, content=reply.content),
        AgentMessage(role=MessageRole.USER, content="and tomorrow morning?"),
    ],
    session_id="kitchen",
)
```

## Configuration

| Key            | Type | Default                     | Notes                                                                    |
|----------------|------|-----------------------------|--------------------------------------------------------------------------|
| `autoconnect`  | bool | `False`                     | Open an internal `MessageBusClient` on init.                              |
| `host`         | str  | `127.0.0.1`                 | OVOS messagebus host (only used with `autoconnect`).                      |
| `port`         | int  | `8181`                      | OVOS messagebus port (only used with `autoconnect`).                      |
| `timeout`      | int  | `30`                        | Per-utterance wait, refreshed on every `speak` to allow multi-speak.       |
| `source_name`  | str  | `messagebus_chat_agent`     | Value set on outgoing `context.source`. Useful for OVOS routing rules.    |

## Documentation

Full developer docs live in [`docs/`](docs/):

- [`docs/architecture.md`](docs/architecture.md) — where the plugin fits in the
  OVOS agent ecosystem and the SessionManager interplay.
- [`docs/configuration.md`](docs/configuration.md) — every config key with
  behaviour notes.
- [`docs/message_flow.md`](docs/message_flow.md) — end-to-end turn lifecycle,
  including the cross-turn Session reuse story.
- [`docs/development.md`](docs/development.md) — local tests, releases.

## License

Apache 2.0. See [LICENSE.md](LICENSE.md).
