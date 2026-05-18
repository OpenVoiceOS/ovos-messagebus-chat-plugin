# Message Flow

A single turn from `continue_chat` to `AgentMessage`.

## Turn lifecycle

```
caller                       OVOSMessagebusChatAgent             OVOS bus
  |                                  |                              |
  | continue_chat(messages, sid) --->|                              |
  |                                  | look up sess from            |
  |                                  | SessionManager.sessions[sid] |
  |                                  | (create if absent)           |
  |                                  | apply lang/units overrides   |
  |                                  | SessionManager.update(sess)  |
  |                                  |                              |
  |                                  | emit recognizer_loop:utterance ->
  |                                  |   context.session = sess.serialize()
  |                                  |                              |
  |                                  |              (pipeline runs)
  |                                  |                              |
  |                                  |<--- speak (utt #1, session)  |
  |                                  |  query.responses.append      |
  |                                  |  _extend_timeout = True      |
  |                                  |                              |
  |                                  |<--- speak (utt #2, session)  |
  |                                  |  query.responses.append      |
  |                                  |                              |
  |                                  |<--- ovos.utterance.handled    |
  |                                  |  query.handled.set()         |
  |                                  |                              |
  |<--- AgentMessage(ASSISTANT, ...) |                              |
```

## Cross-turn `Session` reuse

The interesting story is what happens **between** turns.

Turn 1 (`session_id="kitchen"`):

1. Agent reads `SessionManager.sessions["kitchen"]` — absent → creates
   `Session(session_id="kitchen")` and registers it.
2. Emits utterance with that Session attached.
3. A skill (say, "weather") activates itself and calls `get_response`. It
   mutates the Session: adds itself to `active_skills`, enters response-mode,
   writes entity context.
4. Every reply message the skill emits carries the mutated Session in
   `context.session`.
5. The agent's `_on_speak` callback calls `SessionManager.get(message)`, which
   calls `Session.from_message` and writes the updated Session back into
   `SessionManager.sessions["kitchen"]`.

Turn 2 (`session_id="kitchen"`):

1. Agent reads `SessionManager.sessions["kitchen"]` — **the mutated Session
   from turn 1**.
2. Emits the new utterance with that Session attached.
3. The "weather" skill sees its own `active_skills` entry and its
   `response-mode` flag, treats the new utterance as a follow-up, and resolves
   the conversation.

This is the whole reason `OVOSMessagebusChatAgent` is a `ChatEngine` and not a
single-shot solver. The agent owns none of this state — `SessionManager` does
— but by looking up by `session_id` instead of minting a fresh UUID, the
plugin lets every multi-turn OVOS feature work transparently.

## End-of-turn detection

The OVOS pipeline emits exactly one `ovos.utterance.handled` per utterance,
after every skill that wanted to respond has spoken. The agent uses that as
the turn-complete signal.

Multi-`speak` responses are handled by the rolling timeout:

```
speak           -> _extend_timeout = True
speak           -> _extend_timeout = True
... pause ...
(timeout slice elapses with _extend_timeout=True → wait once more)
ovos.utterance.handled -> _extend_timeout = False, handled.set()
```

The wait loop only exits when either `handled` is set or a full `timeout`
slice elapses with no further `speak` activity. This means a skill that
streams sentences one at a time over several seconds still completes cleanly.

## Streaming

`stream_sentences` yields each `speak` content as it arrives instead of
joining at the end. Same end-of-turn detection; same rolling timeout. The
yield ordering matches the OVOS bus emission order, which is the order skills
emitted their `speak` calls.

## What does *not* flow through this plugin

- Binary payloads (audio data) — different OVOS subsystem entirely.
- Wake-word activation, STT, TTS — the agent's input is already text and its
  output is text.
- Pipeline routing decisions (which skill handles what) — owned by OVOS.
- `mycroft.session.update` direct events — already consumed by
  `SessionManager` before the agent sees them.
