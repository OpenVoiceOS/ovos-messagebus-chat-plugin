# OVOS Messagebus Chat Plugin

An OVOS `ChatEngine` agent plugin that proxies user turns through a connected
[OpenVoiceOS](https://github.com/OpenVoiceOS) messagebus. Each `continue_chat`
call sends the latest user utterance to the OVOS pipeline and collects the
synthesized response.

The plugin reuses the `SessionManager`-owned `Session` for each `session_id`.
This keeps OVOS-side state across multi-turn conversations: active skills,
entity context, response-mode flags, and language. Skills that rely on
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

# next turn: same session_id reuses the Session, so OVOS skills that need
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

- [`docs/architecture.md`](docs/architecture.md): where the plugin fits in the
  OVOS agent ecosystem and the SessionManager interplay.
- [`docs/configuration.md`](docs/configuration.md): every config key with
  behaviour notes.
- [`docs/message_flow.md`](docs/message_flow.md): end-to-end turn lifecycle,
  including the cross-turn Session reuse story.
- [`docs/development.md`](docs/development.md): local tests, releases.

## Related projects

- [OpenVoiceOS/ovos-bus-client](https://github.com/OpenVoiceOS/ovos-bus-client): owns the `SessionManager` and `Session` classes this plugin reuses across turns.
- [OpenVoiceOS/ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager): defines the `ChatEngine` agent template and the `opm.agents.chat` entry point this plugin implements.
- [OpenVoiceOS/ovos-persona](https://github.com/OpenVoiceOS/ovos-persona): a chat-agent consumer that loads this plugin through plugin discovery.

## License

Apache 2.0. See [LICENSE.md](LICENSE.md).

## Credits

Developed by [TigreGótico](https://tigregotico.pt) for
[OpenVoiceOS](https://openvoiceos.org).

[![NGI0 Commons Fund](./ngi.png)](https://nlnet.nl/project/OpenVoiceOS)

This project was funded through the [NGI0 Commons Fund](https://nlnet.nl/commonsfund),
a fund established by [NLnet](https://nlnet.nl) with financial support from the
European Commission's [Next Generation Internet](https://ngi.eu) programme, under
the aegis of [DG Communications Networks, Content and Technology](https://commission.europa.eu/about-european-commission/departments-and-executive-agencies/communications-networks-content-and-technology_en)
under grant agreement No [101135429](https://cordis.europa.eu/project/id/101135429).
