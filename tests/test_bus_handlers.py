"""Bus handler registration and routing."""

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager

from ovos_messagebus_chat_plugin import OVOSMessagebusChatAgent


def _handler_names(listeners):
    """Collect handler names from a bus's listeners for a topic.

    FakeBus wraps handlers on migrated (namespaced) topics in a closure that
    dedups the legacy/ovos.* mirror, so the registered callable is an opaque
    ``wrapped`` function. Unwrap ``__closure__`` cells to recover the name of
    the original bound method.
    """
    names = set()

    def _add(obj):
        names.add(getattr(obj, "__name__", ""))
        func = getattr(obj, "__func__", None)
        if func is not None:
            names.add(getattr(func, "__name__", ""))

    for listener in listeners:
        _add(listener)
        for cell in getattr(listener, "__closure__", None) or ():
            try:
                _add(cell.cell_contents)
            except ValueError:
                continue
    return names


class TestBusHandlerRegistration:
    def test_speak_is_listened_to(self, fake_bus):
        OVOSMessagebusChatAgent(bus=fake_bus, config={"timeout": 1})
        listeners = fake_bus.ee.listeners("speak")
        assert "_on_speak" in _handler_names(listeners)

    def test_turn_end_is_listened_to(self, fake_bus):
        OVOSMessagebusChatAgent(bus=fake_bus, config={"timeout": 1})
        listeners = fake_bus.ee.listeners("ovos.utterance.handled")
        assert "_on_turn_end" in _handler_names(listeners)


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
