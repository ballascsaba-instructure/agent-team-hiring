import json
from pathlib import Path
from typing import Any

import pytest
from eval_harness.datasets import DatasetError, load_scenarios, parse_scenarios

VALID_LINE = json.dumps(
    {
        "id": "a",
        "messages": [{"role": "user", "content": "hi"}],
        "response": "hello",
        "rubric": "be polite",
    }
)

SAMPLE_DATASET = str(Path(__file__).parent.parent / "data" / "scenarios.sample.jsonl")


def _valid(**overrides: Any) -> str:
    return json.dumps({**json.loads(VALID_LINE), **overrides})


def test_parses_one_scenario_per_line_and_ignores_blank_lines() -> None:
    other = json.dumps(
        {
            "id": "b",
            "messages": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hi"},
            ],
            "response": "hey",
            "rubric": "be brief",
        }
    )

    scenarios = parse_scenarios(f"{VALID_LINE}\n\n{other}\n")

    assert [s.id for s in scenarios] == ["a", "b"]
    assert len(scenarios[1].messages) == 2


def test_reports_the_line_number_of_invalid_json() -> None:
    with pytest.raises(DatasetError, match=r"ds\.jsonl:2"):
        parse_scenarios(f"{VALID_LINE}\nnot json\n", "ds.jsonl")


def test_rejects_missing_or_empty_required_fields() -> None:
    no_rubric = json.dumps(
        {"id": "a", "messages": [{"role": "user", "content": "hi"}], "response": "x"}
    )

    with pytest.raises(DatasetError, match='"rubric"'):
        parse_scenarios(no_rubric)
    with pytest.raises(DatasetError, match='"response"'):
        parse_scenarios(_valid(response="  "))


def test_rejects_unknown_message_roles_and_empty_conversations() -> None:
    with pytest.raises(DatasetError, match='"role"'):
        parse_scenarios(_valid(messages=[{"role": "tool", "content": "x"}]))
    with pytest.raises(DatasetError, match='"messages"'):
        parse_scenarios(_valid(messages=[]))


def test_rejects_duplicate_ids_and_empty_datasets() -> None:
    with pytest.raises(DatasetError, match='duplicate scenario id "a"'):
        parse_scenarios(f"{VALID_LINE}\n{VALID_LINE}")
    with pytest.raises(DatasetError, match="no scenarios"):
        parse_scenarios("\n\n")


async def test_loads_the_bundled_sample_dataset() -> None:
    scenarios = await load_scenarios(SAMPLE_DATASET)

    assert len(scenarios) >= 8
    for scenario in scenarios:
        assert scenario.rubric != ""
        assert len(scenario.messages) > 0


async def test_wraps_filesystem_errors() -> None:
    with pytest.raises(DatasetError):
        await load_scenarios("./does-not-exist.jsonl")
