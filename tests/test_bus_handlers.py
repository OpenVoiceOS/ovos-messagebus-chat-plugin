"""Bus handler registration and routing."""

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager

from ovos_messagebus_chat_plugin import OVOSMessagebusChatAgent


class TestBusHandlerRegistration:
    def test_speak_is_listened_to(self, fake_bus):
        OVOSMessagebusChatAgent(bus=fake_bus, config={"timeout": 1})
        listeners = fake_bus.ee.listeners("speak")
        assert any(getattr(l, "__name__", "") == "_on_speak"
                   or getattr(getattr(l, "__func__", l), "__name__", "") == "_on_speak"
                   for l in listeners)

    def test_turn_end_is_listened_to(self, fake_bus):
        OVOSMessagebusChatAgent(bus=fake_bus, config={"timeout": 1})
        listeners = fake_bus.ee.listeners("ovos.utterance.handled")
        assert any(getattr(l, "__name__", "") == "_on_turn_end"
                   or getattr(getattr(l, "__func__", l), "__name__", "") == "_on_turn_end"
                   for l in listeners)


class TestBusRoutingByntsession:
    def test_speak_for_wrong_session_is_ignored(self, agent, fake_bus):
        """A speak addressed to a different session_id must not pollute our query."""
        # set up an in-flight query manually so we can assert isolation
        sess_mine = Session(session_id="mine")
        SessionManager.update(sess_mine)
        from ovos_messagebus_chat_plugin import _Query
        import threading
        q = _Query(utterance="x", session=sess_mine, responses=[],
                   handled=threading.Event())
        agent.queries["mine"] = q

        # someone else's session emits a speak — must not land in our responses
        other = Session(session_id="other-session")
        SessionManager.update(other)
        fake_bus.emit(Message("speak", {"utterance": "not for me"},
                              {"session": other.serialize()}))

        assert q.responses == []

    def test_turn_end_for_wrong_session_is_ignored(self, agent, fake_bus):
        sess = Session(session_id="mine")
        SessionManager.update(sess)
        from ovos_messagebus_chat_plugin import _Query
        import threading
        q = _Query(utterance="x", session=sess, responses=[],
                   handled=threading.Event())
        agent.queries["mine"] = q

        other = Session(session_id="other-session")
        SessionManager.update(other)
        fake_bus.emit(Message("ovos.utterance.handled", {},
                              {"session": other.serialize()}))

        assert not q.handled.is_set()
