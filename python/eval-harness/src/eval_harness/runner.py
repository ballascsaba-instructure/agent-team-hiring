import asyncio
import dataclasses
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import List, Literal

from .cache import VerdictCache
from .config import DEFAULT_CONCURRENCY
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
    #: Judge calls in flight at once.
    concurrency: int | None = None


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


async def run_evaluation(scenarios: List[Scenario], deps: RunnerDeps) -> RunSummary:
    """
    Scores every scenario in the dataset.

    Judge calls run through a sliding window of `concurrency` slots: the moment one
    call settles the next scenario takes its slot, so the window stays full to the
    end of the dataset, including a final smaller window when it does not divide
    evenly. Each verdict is collected against the scenario it was produced for, so
    `results` comes back in dataset order whatever order the judge replies in.
    """
    results: list[ScenarioResult] = []
    size = max(1, min(deps.concurrency or DEFAULT_CONCURRENCY, len(scenarios)))

    start = 0
    while start + size <= len(scenarios):
        batch = scenarios[start : start + size]
        settled: List[ScenarioResult] = []

        log.error(
            "batch " + str(start // size + 1) + " of " + str(math.ceil(len(scenarios) / size))
        )

        async def grade(scenario: Scenario) -> None:
            log.info(
                "judging scenario",
                scenario_id=scenario.id,
                messages=[dataclasses.asdict(message) for message in scenario.messages],
                response=scenario.response,
            )

            try:
                settled.append(await _evaluate(scenario, deps))
            except Exception as error:
                log.debug("scenario failed", scenario_id=scenario.id, reason=_to_message(error))
                settled.append(_failed(scenario.id, error))

        await asyncio.gather(*[grade(scenario) for scenario in batch])

        for index in range(len(batch)):
            graded = settled[index] if index < len(settled) else None
            if graded != None:
                results.append(dataclasses.replace(settled[index], scenario_id=batch[index].id))
            else:
                results.append(_failed(batch[index].id, Exception("judge produced no verdict")))

        start += size

    return RunSummary(total_scenarios=len(scenarios), results=results)
