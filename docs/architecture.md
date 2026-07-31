# Architecture

```
                    +------------------------+
                    |   ChatEngine consumer  |
                    | (ovos-persona, pipeline|
                    |  matchers, tests, ...) |
                    +-----------+------------+
                                |
              continue_chat(messages, session_id, lang, units)
                                |
                                v
                    +------------------------+
                    | OVOSMessagebusChatAgent|       opm.agents.chat
                    | (this package)         |       entry point
                    +-----------+------------+
                                |
                  recognizer_loop:utterance + context.session
                                |
                                v
                       +-----------------+
                       |   OVOS bus      |
                       +--------+--------+
                                |
              speak ... speak ... ovos.utterance.handled
                                |
                                v
                       (responses collected,
                        Session state mutated
                        by skills/pipeline)
```

## Responsibilities

`OVOSMessagebusChatAgent` does three things, nothing more:

1. **Looks up the `Session`** for the call's `session_id` from
   `SessionManager.sessions`. If absent, creates a fresh one and registers it.
2. **Emits one `recognizer_loop:utterance`** on the OVOS bus, with the latest
   user utterance from the `messages` argument and the serialized `Session`
   attached to `context.session`.
3. **Collects `speak` messages** addressed to that `session_id` until the
   pipeline emits `ovos.utterance.handled`, then returns the joined content as
   an `AgentMessage(role=ASSISTANT, ...)`.

It does **not** own:

- The `Session` lifecycle. `SessionManager` does. Every bus message that comes
  back updates `SessionManager.sessions[session_id]` via
  `Session.from_message`, so the next turn sees mutations OVOS skills made to
  the Session.
- TTS, STT, audio output. Those live elsewhere in the OVOS stack.
- Conversation history. The caller passes `messages` on every call. The agent
  reads only the latest user message and lets OVOS handle the rest through the
  reused Session.
- Multi-skill orchestration, common_query disambiguation, dialog flow. The
  OVOS pipeline owns all of this. The agent just hands the utterance over.

## The `SessionManager` interplay

This is the load-bearing detail. `SessionManager` (in `ovos-bus-client`) is a
class-level singleton with a `sessions: Dict[str, Session]` map. Its `get()`
method:

```python
msg_sess = Session.from_message(message)
if msg_sess and msg_sess.session_id != "default":
    SessionManager.sessions[msg_sess.session_id] = msg_sess
    return msg_sess
```

Every incoming bus message that carries a `Session` automatically refreshes
the stored copy. The agent does not need to listen for Session updates. It
does not need its own Session cache, and it does not need to merge fields. It
just reads `SessionManager.sessions[session_id]` at the start of each turn
and trusts it to be current.

## Multi-turn semantics

Each `continue_chat` call:

1. Reads `SessionManager.sessions[session_id]` (or creates a Session with that
   id and registers it via `SessionManager.update`).
2. Sends the utterance with that exact Session attached.
3. OVOS skills mutate the Session: they activate themselves, write to
   `IntentContextManager`, enter response-mode, and change `lang`. They emit
   those mutations back through `context.session` on every reply message.
4. `SessionManager.get(message)` writes the updated Session back into
   `SessionManager.sessions[session_id]`.
5. The next `continue_chat` with the same `session_id` picks up the updated
   Session.

This is what makes `MycroftSkill.get_response()`, common_query
disambiguation, and context-managed intent matching work across turns. The
fresh-`Session(uuid4())`-per-call pattern explicitly does not. Every turn
looks like a brand-new conversation to OVOS.

## Layering: this agent is stateless, memory plugins are a no-op

`OVOSMessagebusChatAgent` treats every `continue_chat` call as a **one-off
query**. It reads only the latest `MessageRole.USER` entry from `messages`
and ignores the rest. It does not store history, summarize prior turns,
embed anything, or carry conversation context across calls in its own state.

This is intentional. AgentMemory plugins (`opm.agents.memory`,
`AgentContextManager` and friends) exist to augment the `messages` list:
prepend recall, inject summaries, retrieve embeddings, all **before** a
`ChatEngine` sees it. Layering one in front of this agent is supported and
recommended for LLM-style memory. As far as this agent is concerned, that
layering has **no effect on how the OVOS pipeline behaves**. The agent only
forwards the most recent user utterance to the bus, exactly as if it arrived
from a microphone.

What makes multi-turn conversations work is not memory at the agent layer.
It is **OVOS itself tracking state per `session_id`** through `SessionManager`:

- `active_skills`, response-mode flags, intent-context entities, and language
  all live on the `Session` object.
- `SessionManager.sessions[session_id]` is the canonical store.
- Every bus message refreshes that store automatically.

The agent's only contribution is the one-line lookup that ensures successive
turns with the same `session_id` reuse the same `Session`. If a caller
changes `session_id` between turns, OVOS sees a brand-new conversation. That
is the correct, documented behavior, not a bug.

In short:

| Concern                                            | Lives where                                     |
|----------------------------------------------------|-------------------------------------------------|
| Conversation history fed to an LLM                 | `opm.agents.memory` plugin (separate package)   |
| OVOS pipeline state (skills, context, dialog flow) | `Session` in `SessionManager` (in bus-client)   |
| Forwarding a turn to the OVOS bus                  | This plugin                                     |

The three layers compose cleanly because they own disjoint slices of state.

## Threading

- The OVOS `MessageBusClient` (when autoconnected) runs its own background
  thread.
- `_on_speak` and `_on_turn_end` execute on the bus thread.
- `continue_chat` and `stream_sentences` execute on the caller's thread and
  block on `query.handled.wait()`.
- An internal `Lock` guards `self.queries` because the bus thread and the
  caller thread both touch it.

## End-of-turn signal

The plugin treats `ovos.utterance.handled` as authoritative for "this turn is
done." Skills emit zero or more `speak` messages, then the pipeline emits
exactly one `ovos.utterance.handled`. A rolling timeout
(`_extend_timeout`) protects against pipelines that pause between speaks
without the agent giving up too early.

If `ovos.utterance.handled` never arrives, the configured `timeout` bounds
the wait and the agent returns whatever it has.

---
[Home](README.md) · [Configuration →](configuration.md)
