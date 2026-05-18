# Developer Documentation

Documentation for contributors and integrators of
`ovos-messagebus-chat-plugin`.

For end-user installation and usage, see the [top-level README](../README.md).

## Contents

- [`architecture.md`](architecture.md) — where this plugin fits in the OVOS
  agent ecosystem, and the `SessionManager` interplay that gives it multi-turn
  semantics.
- [`configuration.md`](configuration.md) — every configuration key the plugin
  reads, with defaults and behaviour notes.
- [`message_flow.md`](message_flow.md) — end-to-end trace of a turn: how the
  user utterance reaches OVOS, how `speak` messages are collected, and how
  cross-turn `Session` state is preserved.
- [`development.md`](development.md) — local development, testing, and
  release workflow.
