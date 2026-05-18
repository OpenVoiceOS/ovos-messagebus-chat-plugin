"""OVOS messagebus chat agent plugin.

A `ChatEngine` plugin that proxies user utterances to a connected OVOS
messagebus and returns the synthesized response. Cross-turn state (entity
context, active skills, response-mode, language) is preserved by reusing the
same `Session` from `SessionManager` per `session_id`, so OVOS skills that rely
on multi-turn dialog (`get_response`, common_query disambiguation,
context-managed intents) keep working as conversations evolve.
"""
import threading
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from ovos_bus_client import MessageBusClient
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovos_plugin_manager.templates.agents import (AgentMessage, ChatEngine,
                                                  MessageRole)
from ovos_utils.log import LOG
from pyee import EventEmitter

from ovos_messagebus_chat_plugin.version import __version__


@dataclass
class _Query:
    """Tracks an in-flight question for a single turn on a given session."""
    utterance: str
    session: Session
    responses: List[str] = field(default_factory=list)
    handled: threading.Event = field(default_factory=threading.Event)
    _extend_timeout: bool = False


class OVOSMessagebusChatAgent(ChatEngine):
    """Chat engine that runs each turn through the OVOS messagebus pipeline.

    Entry point group: ``opm.agents.chat``.

    Configuration keys:

    - ``autoconnect`` (bool, default ``False``): if ``True``, the plugin opens
      its own ``MessageBusClient`` on init.
    - ``host`` (str, default ``"127.0.0.1"``): OVOS messagebus host.
    - ``port`` (int, default ``8181``): OVOS messagebus port.
    - ``timeout`` (int, default ``30``): per-utterance wait timeout, refreshed
      on each ``speak`` so multi-utterance responses don't truncate.
    - ``source_name`` (str, default ``"messagebus_chat_agent"``): value placed
      on the outgoing message ``context.source``; useful for routing rules.

    Sessions are not owned by the plugin. ``SessionManager.sessions`` is the
    single source of truth, keyed by the ``session_id`` passed to
    ``continue_chat``. Subsequent turns with the same ``session_id`` reuse the
    Session — including any state OVOS skills have written into it.
    """

    def __init__(self, config: Optional[Dict] = None,
                 bus: Optional[MessageBusClient] = None):
        super().__init__(config=config or {})
        self.bus: Optional[MessageBusClient] = bus
        self.queries: Dict[str, _Query] = {}
        self._queries_lock = threading.Lock()

        if self.bus is None and self.config.get("autoconnect"):
            host = self.config.get("host", "127.0.0.1")
            port = self.config.get("port", 8181)
            self.bus = MessageBusClient(host=host, port=port, emitter=EventEmitter())
            self.bus.run_in_thread()
            self.bus.connected_event.wait()

        if self.bus is not None:
            self.bind(self.bus)

    def bind(self, bus: MessageBusClient) -> None:
        """Attach this agent to an already-connected messagebus."""
        self.bus = bus
        self.bus.on("speak", self._on_speak)
        self.bus.on("ovos.utterance.handled", self._on_turn_end)

    def _on_speak(self, message: Message) -> None:
        utt = message.data.get("utterance")
        if not utt:
            return
        sess = SessionManager.get(message)
        with self._queries_lock:
            query = self.queries.get(sess.session_id)
        if query is not None:
            query.responses.append(utt)
            query._extend_timeout = True

    def _on_turn_end(self, message: Message) -> None:
        sess = SessionManager.get(message)
        with self._queries_lock:
            query = self.queries.get(sess.session_id)
        if query is not None:
            query._extend_timeout = False
            query.handled.set()

    def _session_for(self, session_id: str,
                     lang: Optional[str] = None,
                     units: Optional[str] = None) -> Session:
        """Get-or-create the Session for a chat session_id.

        The Session lives in ``SessionManager.sessions`` so it survives across
        turns and so any state OVOS writes to it (active skills, entity
        context, response-mode flags) is visible to the next call.
        """
        sess = SessionManager.sessions.get(session_id)
        if sess is None:
            sess = Session(session_id=session_id)
        if lang:
            sess.lang = lang
        if units:
            sess.system_unit = units
        SessionManager.update(sess)
        return sess

    def continue_chat(self,
                      messages: List[AgentMessage],
                      session_id: str = "default",
                      lang: Optional[str] = None,
                      units: Optional[str] = None) -> AgentMessage:
        """Run the latest user utterance through the OVOS pipeline."""
        if self.bus is None:
            raise RuntimeError("OVOSMessagebusChatAgent is not bound to a bus")

        last_user = next(
            (m for m in reversed(messages) if m.role == MessageRole.USER),
            None,
        )
        if last_user is None:
            raise ValueError("no user message in history")

        sess = self._session_for(session_id, lang=lang, units=units)

        query = _Query(utterance=last_user.content, session=sess)
        with self._queries_lock:
            self.queries[session_id] = query
        try:
            self.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": [last_user.content], "lang": sess.lang},
                {
                    "session": sess.serialize(),
                    "source": self.config.get("source_name", "messagebus_chat_agent"),
                },
            ))
            timeout = self.config.get("timeout", 30)
            query.handled.wait(timeout=timeout)
            while query._extend_timeout:
                query._extend_timeout = False
                query.handled.wait(timeout=timeout)

            content = "\n".join(query.responses)
            return AgentMessage(role=MessageRole.ASSISTANT, content=content)
        finally:
            with self._queries_lock:
                self.queries.pop(session_id, None)

    def stream_sentences(self,
                         messages: List[AgentMessage],
                         session_id: str = "default",
                         lang: Optional[str] = None,
                         units: Optional[str] = None) -> Iterable[str]:
        """Yield each `speak` utterance as it arrives.

        Useful for downstream TTS that wants to start vocalising before the
        whole turn is complete.
        """
        if self.bus is None:
            raise RuntimeError("OVOSMessagebusChatAgent is not bound to a bus")

        last_user = next(
            (m for m in reversed(messages) if m.role == MessageRole.USER),
            None,
        )
        if last_user is None:
            raise ValueError("no user message in history")

        sess = self._session_for(session_id, lang=lang, units=units)
        query = _Query(utterance=last_user.content, session=sess)
        with self._queries_lock:
            self.queries[session_id] = query
        try:
            self.bus.emit(Message(
                "recognizer_loop:utterance",
                {"utterances": [last_user.content], "lang": sess.lang},
                {
                    "session": sess.serialize(),
                    "source": self.config.get("source_name", "messagebus_chat_agent"),
                },
            ))

            timeout = self.config.get("timeout", 30)
            while not query.handled.is_set():
                query.handled.wait(timeout=0.5)
                while query.responses:
                    yield query.responses.pop(0)
                if not query.handled.is_set() and not query._extend_timeout:
                    query.handled.wait(timeout=timeout)
                    if not query.responses and not query._extend_timeout:
                        break

            while query.responses:
                yield query.responses.pop(0)
        finally:
            with self._queries_lock:
                self.queries.pop(session_id, None)


__all__ = ["OVOSMessagebusChatAgent", "__version__"]
