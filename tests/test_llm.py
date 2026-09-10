from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from openrouter.errors import TooManyRequestsResponseError

from llm_connections.llm import AIChat, ChatUsage


class TestChatUsage:
    def test_to_dict(self):
        usage = ChatUsage(
            latency=1.25,
            input_tokens=100,
            output_tokens=40,
            total_cost=0.002,
        )
        assert usage.to_dict() == {
            "latency": 1.25,
            "input_tokens": 100,
            "output_tokens": 40,
            "total_cost": 0.002,
        }


class TestAIChat:
    def test_includes_system_prompt_and_schema(self):
        chat = AIChat(
            model="openai/gpt-4.1",
            system_prompt="Solve it",
            response_schema={"type": "object"},
        )

        assert chat.messages == [{"role": "system", "content": "Solve it"}]
        assert chat.response_schema["type"] == "json_schema"
        assert chat.response_schema["json_schema"]["strict"] is True

    def test_send_appends_messages_and_returns_usage(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content='{"guess":[]}'))],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, cost=0.003),
        )
        open_router = MagicMock()
        open_router.__enter__.return_value = open_router
        open_router.__exit__.return_value = None
        open_router.chat.send.return_value = response

        chat = AIChat(model="openai/gpt-4.1", system_prompt="sys")
        with (
            patch("llm_connections.llm.OpenRouter", return_value=open_router),
            patch("llm_connections.llm.time.perf_counter", side_effect=[1.0, 1.5]),
        ):
            content, usage = chat.send("hello")

        assert content == '{"guess":[]}'
        assert usage.latency == pytest.approx(0.5)
        assert usage.input_tokens == 11
        assert usage.output_tokens == 7
        assert usage.total_cost == 0.003
        assert chat.messages[1] == {"role": "user", "content": "hello"}
        assert chat.messages[2]["role"] == "assistant"
        assert chat.messages[2]["content"] == '{"guess":[]}'

    def test_send_retries_after_rate_limit(self):
        usage = ChatUsage(latency=0.1, input_tokens=1, output_tokens=1, total_cost=0)
        rate_limit = TooManyRequestsResponseError.__new__(TooManyRequestsResponseError)
        chat = AIChat(model="openai/gpt-4.1")

        with (
            patch.object(
                chat,
                "_send_messages",
                side_effect=[rate_limit, ("ok", usage)],
            ),
            patch("llm_connections.llm.time.sleep") as sleep,
        ):
            content, result = chat.send("retry me")

        sleep.assert_called_once_with(30)
        assert content == "ok"
        assert result is usage
        assert chat.messages[-1] == {"role": "user", "content": "retry me"}
