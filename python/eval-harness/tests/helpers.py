import dataclasses
from typing import Any

from eval_harness.config import JudgeConfig
from eval_harness.datasets import ChatMessage, Scenario
from eval_harness.judge import Verdict


def judge_config(**overrides: Any) -> JudgeConfig:
    base = JudgeConfig(
        model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region="us-east-1",
        prompt_version="v1",
        temperature=0,
        max_output_tokens=256,
        request_timeout_ms=1_000,
        max_retries=3,
        retry_base_delay_ms=1,
    )
    return dataclasses.replace(base, **overrides)


def scenario(id: str, **overrides: Any) -> Scenario:
    base = Scenario(
        id=id,
        messages=[ChatMessage(role="user", content=f"question for {id}")],
        response=f"answer for {id}",
        rubric=f"rubric for {id}",
    )
    return dataclasses.replace(base, **overrides)


def verdict(**overrides: Any) -> Verdict:
    base = Verdict(
        passed=True,
        score=1,
        reasoning="looks fine",
        raw="VERDICT: PASS\nREASON: looks fine",
        prompt_tokens=10,
        completion_tokens=5,
    )
    return dataclasses.replace(base, **overrides)


class StubResponse:
    """Shape of a Bedrock Converse reply, as the LangChain model surfaces it."""

    def __init__(
        self,
        content: Any,
        usage_metadata: dict[str, int] | None = None,
        response_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.content = content
        self.usage_metadata = usage_metadata
        self.response_metadata = response_metadata


def ai_message(text: str, usage: dict[str, int] | None = None) -> StubResponse:
    return StubResponse(
        content=[{"type": "text", "text": text}],
        usage_metadata=usage or {"input_tokens": 10, "output_tokens": 5},
        response_metadata={"model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"},
    )


def bedrock_error(name: str, http_status_code: int | None = None) -> Exception:
    """Builds an error shaped like the ones the Bedrock SDK throws."""
    error = Exception(f"{name}: simulated failure")
    error.response = {  # type: ignore[attr-defined]
        "Error": {"Code": name, "Message": "simulated failure"},
        "ResponseMetadata": {"HTTPStatusCode": http_status_code},
    }
    return error
