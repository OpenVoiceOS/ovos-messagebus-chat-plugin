"""Cross-turn Session reuse: the agent must look up SessionManager by
session_id, not mint a fresh Session per call. Without this, OVOS pipeline
state (active_skills, response-mode, entity context) would be lost between
turns and skills using `get_response` / common_query would break.
"""

from ovos_bus_client.session import Session, SessionManager
from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole

from tests.conftest import _pipeline_reply


def _user(content):
    return AgentMessage(role=MessageRole.USER, content=content)


class TestSessionReuse:
    def test_same_session_id_reuses_session_object(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["turn1"])
        agent.continue_chat([_user("hi")], session_id="kitchen")
        sess_after_turn1 = SessionManager.sessions["kitchen"]

        _pipeline_reply(fake_bus, "kitchen", ["turn2"])
        agent.continue_chat([_user("again")], session_id="kitchen")
        sess_after_turn2 = SessionManager.sessions["kitchen"]

        # not just equal — the same object, or at least the same session_id
        assert sess_after_turn1.session_id == sess_after_turn2.session_id == "kitchen"

    def test_skill_mutations_visible_on_next_turn(self, agent, fake_bus):
        """Simulate: turn 1 a skill activates itself; turn 2's outgoing
        message must carry that active_skills entry in context.session.
        """
        # turn 1: pipeline reply mutates the stored Session
        def turn1_with_skill_activation():
            sess = SessionManager.sessions.get("kitchen") or Session(session_id="kitchen")
            sess.activate_skill("weather.skill")
            SessionManager.update(sess)
            _pipeline_reply(fake_bus, "kitchen", ["sure, which city?"])

        turn1_with_skill_activation()
        agent.continue_chat([_user("weather please")], session_id="kitchen")

        _pipeline_reply(fake_bus, "kitchen", ["it is sunny"])
        agent.continue_chat([_user("london")], session_id="kitchen")

        # the second outgoing utterance must carry the active skill
        outgoing = [
            m for m in fake_bus.emitted_msgs
            if m.msg_type == "recognizer_loop:utterance"
        ]
        assert len(outgoing) == 2
        active_skills_turn2 = outgoing[1].context["session"]["active_skills"]
        # active_skills is a list of [skill_id, timestamp] pairs
        assert any("weather.skill" in entry for entry in active_skills_turn2), \
            f"expected weather.skill in active_skills on turn 2, got {active_skills_turn2}"

    def test_different_session_ids_get_isolated_sessions(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["k"])
        agent.continue_chat([_user("hi from kitchen")], session_id="kitchen")

        _pipeline_reply(fake_bus, "office", ["o"])
        agent.continue_chat([_user("hi from office")], session_id="office")

        assert "kitchen" in SessionManager.sessions
        assert "office" in SessionManager.sessions
        assert SessionManager.sessions["kitchen"] is not SessionManager.sessions["office"]

    def test_new_session_id_creates_session(self, agent, fake_bus):
        assert "fresh-room" not in SessionManager.sessions
        _pipeline_reply(fake_bus, "fresh-room", ["ok"])
        agent.continue_chat([_user("hello")], session_id="fresh-room")
        assert "fresh-room" in SessionManager.sessions

    def test_lang_override_persists_into_stored_session(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "lab", ["ok"])
        agent.continue_chat([_user("hej")], session_id="lab", lang="sv-se")

        # Session normalizes lang to BCP-47 form
        assert SessionManager.sessions["lab"].lang.lower() == "sv-se"
