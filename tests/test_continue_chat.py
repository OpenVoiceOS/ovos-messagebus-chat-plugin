"""End-to-end tests for OVOSMessagebusChatAgent.continue_chat."""

import pytest
from ovos_bus_client.session import SessionManager
from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole

from tests.conftest import _pipeline_reply


def _user(content):
    return AgentMessage(role=MessageRole.USER, content=content)


def _assistant(content):
    return AgentMessage(role=MessageRole.ASSISTANT, content=content)


class TestSingleTurn:
    def test_returns_assistant_message_with_joined_speaks(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["it is 9am", "in your timezone"])

        reply = agent.continue_chat([_user("what time is it?")], session_id="kitchen")

        assert reply.role == MessageRole.ASSISTANT
        assert reply.content == "it is 9am\nin your timezone"

    def test_empty_response_yields_empty_content(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", [])

        reply = agent.continue_chat([_user("hello")], session_id="kitchen")

        assert reply.role == MessageRole.ASSISTANT
        assert reply.content == ""

    def test_raises_when_no_user_message_in_history(self, agent):
        with pytest.raises(ValueError):
            agent.continue_chat([_assistant("hi there")], session_id="kitchen")

    def test_accepts_and_ignores_tools_kwarg(self, agent, fake_bus):
        """continue_chat must match the base ChatEngine contract, which
        accepts a `tools` keyword (ovos_plugin_manager.templates.agents.
        ChatEngine.continue_chat). This engine has no native tool-calling
        (supports_tools stays False) but must not blow up when a caller
        passes tools= by keyword, e.g. an agentic loop probing every engine
        uniformly before falling back to its own ReAct loop.
        """
        _pipeline_reply(fake_bus, "kitchen", ["ok"])

        reply = agent.continue_chat([_user("hi")], session_id="kitchen", tools=None)

        assert reply.role == MessageRole.ASSISTANT
        assert reply.content == "ok"

    def test_uses_last_user_message(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["got it"])
        messages = [
            _user("first question"),
            _assistant("first answer"),
            _user("latest question"),
        ]
        agent.continue_chat(messages, session_id="kitchen")

        emitted = [m for m in fake_bus.emitted_msgs if m.msg_type == "recognizer_loop:utterance"]
        assert emitted[-1].data["utterances"] == ["latest question"]


class TestSessionAttachment:
    def test_session_is_serialized_into_message_context(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["ok"])

        agent.continue_chat([_user("hi")], session_id="kitchen")

        emitted = [m for m in fake_bus.emitted_msgs if m.msg_type == "recognizer_loop:utterance"][0]
        assert "session" in emitted.context
        assert emitted.context["session"]["session_id"] == "kitchen"

    def test_lang_override_propagates_to_session(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["ok"])

        agent.continue_chat([_user("hi")], session_id="kitchen", lang="pt-pt")

        emitted = [m for m in fake_bus.emitted_msgs if m.msg_type == "recognizer_loop:utterance"][0]
        assert emitted.data["lang"] == "pt-pt"
        assert emitted.context["session"]["lang"] == "pt-pt"

    def test_source_name_defaults_and_is_overridable(self, fake_bus):
        from ovos_messagebus_chat_plugin import OVOSMessagebusChatAgent

        custom = OVOSMessagebusChatAgent(bus=fake_bus, config={"timeout": 2, "source_name": "test-bot"})
        _pipeline_reply(fake_bus, "kitchen", ["ok"])

        custom.continue_chat([_user("hi")], session_id="kitchen")

        emitted = [m for m in fake_bus.emitted_msgs if m.msg_type == "recognizer_loop:utterance"][0]
        assert emitted.context["source"] == "test-bot"


class TestTimeoutAndUnbound:
    def test_unbound_agent_raises(self):
        from ovos_messagebus_chat_plugin import OVOSMessagebusChatAgent
        agent = OVOSMessagebusChatAgent(config={"timeout": 1})
        with pytest.raises(RuntimeError):
            agent.continue_chat([_user("hi")], session_id="x")

    def test_returns_whatever_was_collected_on_timeout(self, agent, fake_bus):
        # don't emit ovos.utterance.handled — the agent should bail after its timeout
        # and return whatever speaks it collected (here: none)
        reply = agent.continue_chat([_user("hi")], session_id="kitchen")
        assert reply.role == MessageRole.ASSISTANT
        assert reply.content == ""

    def test_query_is_removed_after_completion(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "kitchen", ["ok"])
        agent.continue_chat([_user("hi")], session_id="kitchen")
        assert "kitchen" not in agent.queries
