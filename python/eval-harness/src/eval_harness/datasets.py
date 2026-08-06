import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

ChatRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True)
class Scenario:
    """
    One evaluation case. The response is already present in the dataset — the
    harness never generates it, it only scores it.
    """

    id: str
    messages: list[ChatMessage]
    response: str
    rubric: str


class DatasetError(Exception):
    pass


CHAT_ROLES: tuple[str, ...] = get_args(ChatRole)


def _is_record(value: object) -> bool:
    return isinstance(value, dict)


def _require_string(value: object, field: str, where: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise DatasetError(f'{where}: "{field}" must be a non-empty string')
    return value


def _validate_messages(value: object, where: str) -> list[ChatMessage]:
    if not isinstance(value, list) or len(value) == 0:
        raise DatasetError(f'{where}: "messages" must be a non-empty array')

    messages: list[ChatMessage] = []
    for index, entry in enumerate(value):
        at = f"{where} messages[{index}]"
        if not _is_record(entry):
            raise DatasetError(f"{at}: must be an object")
        role = entry.get("role")
        if not isinstance(role, str) or role not in CHAT_ROLES:
            raise DatasetError(f'{at}: "role" must be one of {", ".join(CHAT_ROLES)}')
        content = entry.get("content")
        if not isinstance(content, str):
            raise DatasetError(f'{at}: "content" must be a string')
        messages.append(ChatMessage(role=role, content=content))  # type: ignore[arg-type]

    return messages


def _validate_scenario(value: object, where: str) -> Scenario:
    if not _is_record(value):
        raise DatasetError(f"{where}: each line must be a JSON object")

    record: dict[str, Any] = value  # type: ignore[assignment]
    return Scenario(
        id=_require_string(record.get("id"), "id", where),
        messages=_validate_messages(record.get("messages"), where),
        response=_require_string(record.get("response"), "response", where),
        rubric=_require_string(record.get("rubric"), "rubric", where),
    )


def parse_scenarios(contents: str, source: str = "<inline>") -> list[Scenario]:
    scenarios: list[Scenario] = []
    seen: set[str] = set()
    lines = contents.split("\n")

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line == "":
            continue

        where = f"{source}:{index + 1}"
        try:
            parsed = json.loads(line)
        except ValueError as cause:
            raise DatasetError(f"{where}: invalid JSON ({cause})") from cause

        scenario = _validate_scenario(parsed, where)
        if scenario.id in seen:
            raise DatasetError(f'{where}: duplicate scenario id "{scenario.id}"')
        seen.add(scenario.id)
        scenarios.append(scenario)

    if len(scenarios) == 0:
        raise DatasetError(f"{source}: dataset contains no scenarios")

    return scenarios


async def load_scenarios(file_path: str) -> list[Scenario]:
    try:
        contents = await asyncio.to_thread(Path(file_path).read_text, encoding="utf8")
    except OSError as cause:
        raise DatasetError(f'could not read dataset "{file_path}": {cause}') from cause
    return parse_scenarios(contents, file_path)
