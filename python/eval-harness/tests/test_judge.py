from eval_harness.datasets import ChatMessage
from eval_harness.judge import build_judge_prompt, judge_scenario, parse_verdict
from eval_harness.judge_client import CompletionRequest, CompletionResult
from helpers import judge_config, scenario


class StubClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls.append(request)
        return CompletionResult(
            content=self.content, model="judge-model-a", prompt_tokens=42, completion_tokens=7
        )


def test_sends_a_system_instruction_plus_a_single_user_turn() -> None:
    messages = build_judge_prompt(scenario("s1"), "v1")

    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[1].role == "user"


def test_includes_the_conversation_the_response_under_test_and_the_rubric() -> None:
    target = scenario(
        "s1",
        messages=[
            ChatMessage(role="system", content="be terse"),
            ChatMessage(role="user", content="how do I reset my password?"),
        ],
        response="Use the reset link on the sign-in page.",
        rubric="Must point at the reset link.",
    )

    prompt = build_judge_prompt(target, "v1")[1].content

    assert "how do I reset my password?" in prompt
    assert "Use the reset link on the sign-in page." in prompt
    assert "Must point at the reset link." in prompt


def test_reads_the_verdict_and_reason() -> None:
    assert parse_verdict("VERDICT: PASS\nREASON: covers the rubric") == (
        True,
        "covers the rubric",
    )
    assert parse_verdict("VERDICT: FAIL\nREASON: promises a refund") == (
        False,
        "promises a refund",
    )


async def test_maps_a_judge_completion_onto_a_verdict() -> None:
    client = StubClient("VERDICT: PASS\nREASON: good enough")

    result = await judge_scenario(client, scenario("s1"), judge_config())

    assert (result.passed, result.score, result.reasoning) == (True, 1, "good enough")
    assert result.prompt_tokens == 42
    assert result.completion_tokens == 7
    assert len(client.calls[0].messages) == 2


async def test_scores_a_failing_verdict_as_zero() -> None:
    client = StubClient("VERDICT: FAIL\nREASON: unsafe")

    result = await judge_scenario(client, scenario("s1"), judge_config())

    assert result.passed is False
    assert result.score == 0
