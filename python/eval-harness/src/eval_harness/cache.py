import asyncio
import dataclasses
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .datasets import Scenario
from .judge import Verdict


class VerdictCache(Protocol):
    async def get(self, key: str) -> Verdict | None: ...

    async def set(self, key: str, verdict: Verdict) -> None: ...


def verdict_cache_key(*, scenario: Scenario, model: str, prompt_version: str) -> str:
    """
    A verdict is only reusable for the exact scenario content, judge model and
    prompt template that produced it — all three go into the key.
    """
    digest = hashlib.sha256()
    for part in [
        scenario.id,
        model,
        prompt_version,
        scenario.rubric,
        scenario.response,
        json.dumps([dataclasses.asdict(message) for message in scenario.messages]),
    ]:
        digest.update(part.encode("utf8"))
        digest.update(b" ")
    return digest.hexdigest()


def _is_verdict(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return isinstance(value.get("passed"), bool) and isinstance(value.get("score"), (int, float))


class FileCache:
    def __init__(self, directory: str) -> None:
        self._directory = Path(directory)

    def _file_for(self, key: str) -> Path:
        return self._directory / f"{key}.json"

    async def get(self, key: str) -> Verdict | None:
        try:
            contents = await asyncio.to_thread(self._file_for(key).read_text, encoding="utf8")
        except OSError:
            return None

        try:
            entry: Any = json.loads(contents)
        except ValueError:
            return None

        stored = entry.get("verdict") if isinstance(entry, dict) else None
        if not isinstance(stored, dict) or not _is_verdict(stored):
            return None
        return Verdict(**stored)

    async def set(self, key: str, verdict: Verdict) -> None:
        entry = {
            "key": key,
            "createdAt": datetime.now(UTC).isoformat(),
            "verdict": dataclasses.asdict(verdict),
        }
        await asyncio.to_thread(self._directory.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            self._file_for(key).write_text, json.dumps(entry, indent=2) + "\n", encoding="utf8"
        )


def create_file_cache(directory: str) -> VerdictCache:
    return FileCache(directory)


class NullCache:
    async def get(self, key: str) -> Verdict | None:
        return None

    async def set(self, key: str, verdict: Verdict) -> None:
        pass  # no-op


null_cache: VerdictCache = NullCache()
