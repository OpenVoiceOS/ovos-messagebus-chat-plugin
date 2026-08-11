"""The plugin must not impose its *own* configuration on core.

A `Session` constructed client side is filled in from the client's local ovos
configuration: lang, pipeline, blacklisted_skills, location, units, date/time
formats. Serializing that onto the wire overrides core's configuration for the
turn. A chat client configured with `lang: pt-PT` talking to an English core
made core resolve every utterance as Portuguese, so nothing ever matched and
`continue_chat` returned empty content.

On a session core has not told us about yet, the outgoing message therefore
carries only the session identity (plus whatever the caller explicitly asked
for). Once core replies, its Session is adopted and echoed back in full.
"""

from unittest.mock import patch

from ovos_bus_client.session import Session, SessionManager
from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole

from tests.conftest import _pipeline_reply


def _user(content):
    return AgentMessage(role=MessageRole.USER, content=content)


def _outgoing(fake_bus):
    return [m for m in fake_bus.emitted_msgs
            if m.msg_type == "recognizer_loop:utterance"]


class TestClientConfigIsNotImposed:
    def test_first_turn_sends_identity_only(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["ok"])
        agent.continue_chat([_user("what time is it")], session_id="kitchen")

        sess = _outgoing(fake_bus)[0].context["session"]
        assert sess == {"session_id": "kitchen"}, \
            f"client-side config leaked onto the wire: {sorted(sess)}"

    def test_first_turn_does_not_pin_client_lang(self, agent, fake_bus):
        """No caller lang -> no lang on the wire, so core uses its own."""
        _pipeline_reply(fake_bus, "kitchen", ["ok"])
        agent.continue_chat([_user("what time is it")], session_id="kitchen")

        assert "lang" not in _outgoing(fake_bus)[0].data

    def test_caller_lang_is_still_honoured(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["ok"])
        agent.continue_chat([_user("que horas sao")], session_id="kitchen",
                            lang="pt-pt")

        out = _outgoing(fake_bus)[0]
        assert out.data["lang"].lower() == "pt-pt"
        assert out.context["session"]["lang"].lower() == "pt-pt"

    def test_second_turn_echoes_the_session_core_sent(self, agent, fake_bus):
        """Core owns session state; once it replies we send its Session back."""
        def core_side(sess):
            sess.lang = "en-US"
            sess.pipeline = ["padatious_high", "fallback_low"]

        _pipeline_reply(fake_bus, "kitchen", ["ok"], session_mutator=core_side)
        agent.continue_chat([_user("hi")], session_id="kitchen")

        _pipeline_reply(fake_bus, "kitchen", ["ok"])
        agent.continue_chat([_user("and now")], session_id="kitchen")

        sess = _outgoing(fake_bus)[1].context["session"]
        assert sess["lang"] == "en-US"
        assert sess["pipeline"] == ["padatious_high", "fallback_low"]
        assert _outgoing(fake_bus)[1].data["lang"] == "en-US"
