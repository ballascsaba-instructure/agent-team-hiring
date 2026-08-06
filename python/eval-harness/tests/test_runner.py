from eval_harness.datasets import Scenario
from eval_harness.judge import Verdict
from eval_harness.runner import RunnerDeps, run_evaluation
from helpers import scenario, verdict


class MemoryCache:
    def __init__(self, seed: dict[str, Verdict] | None = None) -> None:
        self.store: dict[str, Verdict] = dict(seed or {})

    async def get(self, key: str) -> Verdict | None:
        return self.store.get(key)

    async def set(self, key: str, value: Verdict) -> None:
        self.store[key] = value


class RecordingJudge:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, target: Scenario) -> Verdict:
        self.calls.append(target.id)
        return verdict(passed=target.id != "b", score=0 if target.id == "b" else 1)


SCENARIOS = [scenario("a"), scenario("b"), scenario("c")]


async def test_scores_every_scenario_and_keeps_dataset_order() -> None:
    judge = RecordingJudge()

    run = await run_evaluation(SCENARIOS, RunnerDeps(judge=judge))

    assert run.total_scenarios == 3
    assert [r.scenario_id for r in run.results] == ["a", "b", "c"]
    assert [r.passed for r in run.results] == [True, False, True]
    assert len(judge.calls) == 3


async def test_records_a_judge_failure_as_an_errored_result_without_aborting_the_run() -> None:
    async def judge(target: Scenario) -> Verdict:
        if target.id == "b":
            raise RuntimeError("judge API responded 401: invalid key")
        return verdict()

    run = await run_evaluation(SCENARIOS, RunnerDeps(judge=judge))

    assert [r.status for r in run.results] == ["scored", "error", "scored"]
    assert "401" in (run.results[1].error or "")
    assert run.results[1].passed is False


async def test_serves_cached_verdicts_without_calling_the_judge() -> None:
    cache = MemoryCache({"key-a": verdict(reasoning="from cache")})
    judge = RecordingJudge()

    run = await run_evaluation(
        [scenario("a")],
        RunnerDeps(judge=judge, cache=cache, cache_key=lambda target: f"key-{target.id}"),
    )

    assert judge.calls == []
    assert run.results[0].cached is True
    assert run.results[0].reasoning == "from cache"
    assert run.results[0].prompt_tokens == 0


async def test_writes_fresh_verdicts_back_to_the_cache() -> None:
    cache = MemoryCache()

    async def judge(target: Scenario) -> Verdict:
        return verdict(reasoning="fresh")

    await run_evaluation(
        [scenario("a")],
        RunnerDeps(judge=judge, cache=cache, cache_key=lambda target: f"key-{target.id}"),
    )

    assert cache.store["key-a"].reasoning == "fresh"
