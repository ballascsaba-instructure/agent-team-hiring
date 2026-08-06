from typing import Any

from eval_harness.report import format_report, summarize
from eval_harness.runner import RunSummary, ScenarioResult


def result(scenario_id: str, **overrides: Any) -> ScenarioResult:
    defaults: dict[str, Any] = {
        "status": "scored",
        "passed": True,
        "score": 1,
        "reasoning": "",
        "cached": False,
        "prompt_tokens": 100,
        "completion_tokens": 10,
    }
    return ScenarioResult(scenario_id=scenario_id, **{**defaults, **overrides})


def run(results: list[ScenarioResult]) -> RunSummary:
    return RunSummary(total_scenarios=len(results), results=results)


def test_computes_the_pass_rate_over_graded_scenarios() -> None:
    summary = summarize(
        run([result("a"), result("b"), result("c"), result("d", passed=False, score=0)])
    )

    assert (summary.total, summary.scored, summary.errored) == (4, 4, 0)
    assert (summary.passed, summary.failed) == (3, 1)
    assert summary.pass_rate == 0.75


def test_counts_errored_scenarios_separately_from_failures() -> None:
    summary = summarize(
        run(
            [
                result("a"),
                result("b", passed=False, score=0),
                result("c", status="error", passed=False, score=0, error="boom"),
            ]
        )
    )

    assert summary.scored == 2
    assert summary.errored == 1
    assert summary.passed == 1
    assert summary.failed == 1


def test_reports_a_zero_pass_rate_for_an_empty_run() -> None:
    assert summarize(run([])).pass_rate == 0


def test_totals_cache_hits_and_judge_tokens() -> None:
    summary = summarize(
        run(
            [
                result("a", cached=True, prompt_tokens=0, completion_tokens=0),
                result("b", prompt_tokens=250, completion_tokens=12),
            ]
        )
    )

    assert summary.cache_hits == 1
    assert summary.prompt_tokens == 250
    assert summary.completion_tokens == 12


def test_prints_the_headline_numbers() -> None:
    text = format_report(run([result("a"), result("b", passed=False, score=0)]))

    assert "Scenarios       2" in text
    assert "Passed          1" in text
    assert "Pass rate       50.0%" in text


def test_lists_failures_and_errors_with_their_detail() -> None:
    text = format_report(
        run(
            [
                result("ok"),
                result("bad", passed=False, score=0, reasoning="missed the rubric"),
                result("broken", status="error", passed=False, score=0, error="timeout"),
            ]
        )
    )

    assert "FAIL  bad — missed the rubric" in text
    assert "ERROR broken — timeout" in text
    assert "FAIL  ok" not in text
    assert "ERROR ok" not in text
