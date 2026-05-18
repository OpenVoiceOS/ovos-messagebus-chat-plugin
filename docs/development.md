# Development

## Local setup

```bash
git clone https://github.com/OpenVoiceOS/ovos-messagebus-chat-plugin
cd ovos-messagebus-chat-plugin
pip install -e .[test]
```

## Running tests

```bash
pytest tests/ -v
```

Tests use `FakeBus` and never start a real OVOS instance or messagebus
server. Each turn is exercised end-to-end (emit utterance, simulate `speak`
replies, emit `ovos.utterance.handled`, assert the returned `AgentMessage`).

### Coverage

```bash
pytest tests/ --cov=ovos_messagebus_chat_plugin --cov-report=term-missing
```

## Branching and releases

- `dev` is the active development branch. All PRs target `dev`.
- `master` carries tagged releases. Direct pushes to `master` are reserved for
  the publish workflow.
- Alpha builds publish to PyPI automatically when a PR is merged to `dev` (see
  `.github/workflows/release_workflow.yml`).
- Stable releases publish when changes land on `master` (see
  `.github/workflows/publish_stable.yml`).

Versions live in `ovos_messagebus_chat_plugin/version.py`; the publish
workflows bump them automatically.

## Adding tests

Tests live under `tests/`. Conventions:

- Use `FakeBus`. Never spin up a real `MessageBusClient`.
- Drive turns by emitting `speak` and `ovos.utterance.handled` on the
  `FakeBus` from the test body.
- Each behaviour from `docs/message_flow.md` should have a corresponding test.
- For cross-turn tests, reset `SessionManager.sessions` between test functions
  (a `conftest.py` fixture handles this automatically).

## Release checklist

1. Open PRs against `dev`.
2. Merge to `dev` — alpha is published automatically.
3. When ready for stable, the "Release Alpha and Propose Stable" workflow
   opens a PR from `dev` → `master`.
4. Merge that PR — stable is published automatically and the version is
   bumped.
