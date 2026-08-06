from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from .cache import VerdictCache
from .datasets import Scenario
from .judge import Verdict
from .log import log


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    status: Literal["scored", "error"]
    passed: bool
    score: float
    reasoning: str
    cached: bool
    prompt_tokens: int
    completion_tokens: int
    error: str | None = None


@dataclass(frozen=True)
class RunSummary:
    total_scenarios: int
    results: list[ScenarioResult]


@dataclass(frozen=True)
class RunnerDeps:
    judge: Callable[[Scenario], Awaitable[Verdict]]
    cache: VerdictCache | None = None
    cache_key: Callable[[Scenario], str] | None = field(default=None)


def _to_message(error: BaseException) -> str:
    return str(error)


def _scored(scenario_id: str, verdict: Verdict, cached: bool) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        status="scored",
        passed=verdict.passed,
        score=verdict.score,
        reasoning=verdict.reasoning,
        cached=cached,
        prompt_tokens=0 if cached else verdict.prompt_tokens,
        completion_tokens=0 if cached else verdict.completion_tokens,
    )


def _failed(scenario_id: str, error: BaseException) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        status="error",
        passed=False,
        score=0,
        reasoning="",
        cached=False,
        prompt_tokens=0,
        completion_tokens=0,
        error=_to_message(error),
    )


async def _evaluate(scenario: Scenario, deps: RunnerDeps) -> ScenarioResult:
    key = deps.cache_key(scenario) if deps.cache_key is not None else None

    if deps.cache is not None and key is not None:
        hit = await deps.cache.get(key)
        if hit is not None:
            return _scored(scenario.id, hit, True)

    verdict = await deps.judge(scenario)

    if deps.cache is not None and key is not None:
        await deps.cache.set(key, verdict)

    return _scored(scenario.id, verdict, False)


async def run_evaluation(scenarios: list[Scenario], deps: RunnerDeps) -> RunSummary:
    results: list[ScenarioResult] = []

    for scenario in scenarios:
        try:
            results.append(await _evaluate(scenario, deps))
        except Exception as error:
            log.error(
                "scenario could not be scored",
                scenario_id=scenario.id,
                reason=_to_message(error),
            )
            results.append(_failed(scenario.id, error))

    return RunSummary(total_scenarios=len(scenarios), results=results)
