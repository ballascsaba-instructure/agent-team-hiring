from collections.abc import Callable
from dataclasses import dataclass

from .runner import RunSummary, ScenarioResult


@dataclass(frozen=True)
class ReportSummary:
    total: int
    scored: int
    errored: int
    passed: int
    failed: int
    pass_rate: float
    cache_hits: int
    prompt_tokens: int
    completion_tokens: int


def _is_scored(result: ScenarioResult) -> bool:
    return result.status == "scored"


def summarize(run: RunSummary) -> ReportSummary:
    scored = [result for result in run.results if _is_scored(result)]
    passed = len([result for result in scored if result.passed])

    return ReportSummary(
        total=run.total_scenarios,
        scored=len(scored),
        errored=len(run.results) - len(scored),
        passed=passed,
        failed=len(scored) - passed,
        # Only responses the judge actually graded can contribute to a pass rate;
        # transport failures are reported separately rather than counted as fails.
        pass_rate=0 if len(scored) == 0 else passed / len(scored),
        cache_hits=len([result for result in run.results if result.cached]),
        prompt_tokens=sum(result.prompt_tokens for result in run.results),
        completion_tokens=sum(result.completion_tokens for result in run.results),
    )


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _line(label: str, value: str | int) -> str:
    return f"{label:<16}{value}"


def format_report(run: RunSummary) -> str:
    summary = summarize(run)
    lines: list[str] = [
        "Evaluation report",
        "-----------------",
        _line("Scenarios", summary.total),
        _line("Scored", summary.scored),
        _line("Errors", summary.errored),
        _line("Passed", summary.passed),
        _line("Failed", summary.failed),
        _line("Pass rate", _percent(summary.pass_rate)),
        _line("Cache hits", summary.cache_hits),
        _line(
            "Judge tokens",
            f"{summary.prompt_tokens} prompt / {summary.completion_tokens} completion",
        ),
    ]

    notable = [result for result in run.results if result.status == "error" or not result.passed]
    if len(notable) > 0:
        lines.extend(["", "Details"])
        for result in notable:
            tag = "ERROR" if result.status == "error" else "FAIL "
            detail = (result.error or "") if result.status == "error" else result.reasoning
            lines.append(f"  {tag} {result.scenario_id}{'' if detail == '' else f' — {detail}'}")

    return "\n".join(lines)


def print_report(run: RunSummary, write: Callable[[str], None] = print) -> None:
    write(format_report(run))
