from pathlib import Path

from eval_harness.cache import create_file_cache, null_cache, verdict_cache_key
from helpers import scenario, verdict


def test_gives_different_scenarios_different_keys() -> None:
    a = verdict_cache_key(scenario=scenario("a"), model="m", prompt_version="v1")
    b = verdict_cache_key(scenario=scenario("b"), model="m", prompt_version="v1")

    assert a != b


def test_is_stable_for_the_same_inputs() -> None:
    first = verdict_cache_key(scenario=scenario("a"), model="m", prompt_version="v1")
    second = verdict_cache_key(scenario=scenario("a"), model="m", prompt_version="v1")

    assert first == second


async def test_returns_none_for_an_unknown_key(tmp_path: Path) -> None:
    cache = create_file_cache(str(tmp_path))

    assert await cache.get("missing") is None


async def test_round_trips_a_verdict_through_disk(tmp_path: Path) -> None:
    cache = create_file_cache(str(tmp_path))
    stored = verdict(passed=False, score=0, reasoning="nope")

    await cache.set("some-key", stored)

    loaded = await cache.get("some-key")
    assert loaded is not None
    assert (loaded.passed, loaded.score, loaded.reasoning) == (False, 0, "nope")


async def test_creates_the_cache_directory_on_demand(tmp_path: Path) -> None:
    cache = create_file_cache(str(tmp_path / "deep" / "deeper"))

    await cache.set("k", verdict())

    assert await cache.get("k") is not None


async def test_treats_corrupt_entries_as_a_miss(tmp_path: Path) -> None:
    cache = create_file_cache(str(tmp_path))
    await cache.set("k", verdict())
    (tmp_path / "k.json").write_text("{ not json", encoding="utf8")

    assert await cache.get("k") is None


async def test_null_cache_never_returns_anything() -> None:
    await null_cache.set("k", verdict())

    assert await null_cache.get("k") is None
