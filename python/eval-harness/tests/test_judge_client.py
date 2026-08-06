from collections.abc import Sequence
from typing import Any

import pytest
from eval_harness.judge_client import (
    CompletionRequest,
    JudgeApiError,
    JudgeMessage,
    create_judge_client,
    is_retryable_judge_error,
)
from helpers import StubResponse, ai_message, bedrock_error, judge_config
from langchain_core.messages import BaseMessage

REQUEST = CompletionRequest(messages=[JudgeMessage(role="user", content="grade this")])


class StubModel:
    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.calls: list[Sequence[BaseMessage]] = []

    async def ainvoke(self, input: Sequence[BaseMessage], **kwargs: Any) -> Any:
        self.calls.append(input)
        reply = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        if isinstance(reply, BaseException):
            raise reply
        return reply


async def test_invokes_the_model_and_returns_the_text_plus_token_usage() -> None:
    model = StubModel(
        ai_message("VERDICT: PASS\nREASON: fine", {"input_tokens": 321, "output_tokens": 12})
    )
    client = create_judge_client(judge_config(), model)

    result = await client.complete(REQUEST)

    assert result.content == "VERDICT: PASS\nREASON: fine"
    assert result.prompt_tokens == 321
    assert result.completion_tokens == 12
    assert result.model == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    assert len(model.calls) == 1


async def test_maps_roles_onto_langchain_message_types() -> None:
    model = StubModel(ai_message("VERDICT: PASS"))
    client = create_judge_client(judge_config(), model)

    await client.complete(
        CompletionRequest(
            messages=[
                JudgeMessage(role="system", content="you grade responses"),
                JudgeMessage(role="user", content="grade this"),
            ]
        )
    )

    messages = model.calls[0]
    assert [message.type for message in messages] == ["system", "human"]
    assert messages[1].content == "grade this"


async def test_accepts_a_plain_string_content_payload() -> None:
    client = create_judge_client(judge_config(), StubModel(StubResponse("VERDICT: FAIL")))

    result = await client.complete(REQUEST)

    assert result.content == "VERDICT: FAIL"
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


async def test_retries_a_throttling_exception_and_then_succeeds() -> None:
    model = StubModel(
        bedrock_error("ThrottlingException", 429),
        ai_message("VERDICT: FAIL\nREASON: nope"),
    )
    client = create_judge_client(judge_config(), model)

    result = await client.complete(REQUEST)

    assert result.content == "VERDICT: FAIL\nREASON: nope"
    assert len(model.calls) == 2


async def test_gives_up_after_max_retries_attempts() -> None:
    model = StubModel(bedrock_error("ServiceUnavailableException", 503))
    client = create_judge_client(judge_config(max_retries=2), model)

    with pytest.raises(JudgeApiError):
        await client.complete(REQUEST)
    assert len(model.calls) == 3


async def test_rejects_an_empty_model_response() -> None:
    client = create_judge_client(judge_config(), StubModel(StubResponse("   ")))

    with pytest.raises(JudgeApiError, match="empty response"):
        await client.complete(REQUEST)


def test_treats_throttling_timeouts_and_server_faults_as_retryable() -> None:
    assert is_retryable_judge_error(bedrock_error("ThrottlingException", 429)) is True
    assert is_retryable_judge_error(bedrock_error("ModelTimeoutException", 408)) is True
    assert is_retryable_judge_error(bedrock_error("InternalServerException", 500)) is True
    assert is_retryable_judge_error(bedrock_error("ServiceUnavailableException", 503)) is True


def test_treats_a_bare_network_failure_as_retryable() -> None:
    assert is_retryable_judge_error(Exception("socket hang up")) is True
