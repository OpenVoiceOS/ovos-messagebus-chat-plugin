"""The agent itself stores no conversation state.

History lives in the caller's `messages` arg. Cross-turn OVOS state lives in
SessionManager. The agent's job is to forward one utterance per call.
"""

from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole

from tests.conftest import _pipeline_reply


def _user(c):
    return AgentMessage(role=MessageRole.USER, content=c)


def _assistant(c):
    return AgentMessage(role=MessageRole.ASSISTANT, content=c)


class TestAgentIsStateless:
    def test_history_in_messages_is_ignored(self, agent, fake_bus):
        """Only the latest user message is forwarded; prior history is not."""
        _pipeline_reply(fake_bus, "k", ["ok"])

        agent.continue_chat([
            _user("first question"),
            _assistant("first answer"),
            _user("second question"),
            _assistant("second answer"),
            _user("current question"),
        ], session_id="k")

        outgoing = [
            m for m in fake_bus.emitted_msgs
            if m.msg_type == "recognizer_loop:utterance"
        ]
        # only the current question is sent on the bus
        assert outgoing[0].data["utterances"] == ["current question"]
        # no history is leaked into context
        assert "messages" not in outgoing[0].context
        assert "history" not in outgoing[0].context

    def test_agent_holds_no_history_between_calls(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "k", ["a"])
        agent.continue_chat([_user("one")], session_id="k")
        _pipeline_reply(fake_bus, "k", ["b"])
        agent.continue_chat([_user("two")], session_id="k")

        # the agent itself stores nothing turn-to-turn except in-flight queries
        # (which get popped on completion)
        assert agent.queries == {}

    def test_each_call_is_a_one_shot_query(self, agent, fake_bus):
        """No matter how rich `messages` is, exactly one utterance hits the bus."""
        _pipeline_reply(fake_bus, "k", ["ok"])
        agent.continue_chat([
            AgentMessage(role=MessageRole.SYSTEM, content="be terse"),
            _user("q1"),
            _assistant("a1"),
            _user("q2"),
        ], session_id="k")

        outgoing = [
            m for m in fake_bus.emitted_msgs
            if m.msg_type == "recognizer_loop:utterance"
        ]
        assert len(outgoing) == 1
