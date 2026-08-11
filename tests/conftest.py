import threading

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovos_utils.fakebus import FakeBus

from ovos_messagebus_chat_plugin import OVOSMessagebusChatAgent


class CapturingFakeBus(FakeBus):
    """FakeBus that records every emitted Message for assertion."""

    def __init__(self):
        super().__init__()
        self.emitted_msgs = []

    def emit(self, message):
        self.emitted_msgs.append(message)
        super().emit(message)


@pytest.fixture(autouse=True)
def reset_session_manager():
    """Isolate SessionManager state between tests."""
    default = SessionManager.default_session
    SessionManager.sessions = {"default": default}
    yield
    SessionManager.sessions = {"default": default}


@pytest.fixture
def fake_bus():
    return CapturingFakeBus()


@pytest.fixture
def agent(fake_bus):
    return OVOSMessagebusChatAgent(bus=fake_bus, config={"timeout": 2})


def _pipeline_reply(bus: FakeBus, session_id: str, utterances,
                    session_mutator=None):
    """Simulate the OVOS pipeline responding to the *next* utterance.

    Registers a one-shot handler on `recognizer_loop:utterance` that, when
    triggered, optionally mutates the session (`session_mutator`) the way core
    would, then fires the configured speaks followed by
    `ovos.utterance.handled`. Replies are emitted on a separate thread so
    the agent's blocking `continue_chat` call can return.
    """
    fired = threading.Event()

    def _on_utterance(_msg):
        if fired.is_set():
            return
        fired.set()

        def _respond():
            sess = SessionManager.sessions.get(session_id) or Session(session_id=session_id)
            if session_mutator is not None:
                # core mutated the session while handling the turn (a skill
                # activated itself, set a response mode, ...)
                session_mutator(sess)
            ctx = {"session": sess.serialize()}
            for utt in utterances:
                bus.emit(Message("speak", {"utterance": utt}, ctx))
            bus.emit(Message("ovos.utterance.handled", {}, ctx))

        threading.Thread(target=_respond, daemon=True).start()

    bus.on("recognizer_loop:utterance", _on_utterance)
