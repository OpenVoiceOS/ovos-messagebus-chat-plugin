"""stream_sentences yields speaks as they arrive."""

import pytest
from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole

from tests.conftest import _pipeline_reply


def _user(c):
    return AgentMessage(role=MessageRole.USER, content=c)


class TestStreamSentences:
    def test_yields_each_speak_in_order(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "k", ["one", "two", "three"])
        out = list(agent.stream_sentences([_user("hi")], session_id="k"))
        assert out == ["one", "two", "three"]

    def test_no_speaks_yields_nothing(self, agent, fake_bus):
        _pipeline_reply(fake_bus, "k", [])
        out = list(agent.stream_sentences([_user("hi")], session_id="k"))
        assert out == []

    def test_raises_when_no_user_message(self, agent):
        with pytest.raises(ValueError):
            list(agent.stream_sentences([
                AgentMessage(role=MessageRole.ASSISTANT, content="hi"),
            ], session_id="k"))
