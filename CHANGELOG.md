# Changelog

## 0.1.0a1

Initial release.

- `OVOSMessagebusChatAgent`: a `ChatEngine` (`opm.agents.chat`) plugin that
  proxies user turns through a connected OVOS messagebus.
- Cross-turn `Session` reuse via `SessionManager`, keyed by `session_id`.
  Multi-turn OVOS features (skill `get_response`, common_query
  disambiguation, context-managed intents) work as expected.
- Stateless agent: each call is a one-off query; conversation history is the
  caller's responsibility (typically an `opm.agents.memory` plugin layered
  in front).
- `stream_sentences` for incremental `speak` delivery.
