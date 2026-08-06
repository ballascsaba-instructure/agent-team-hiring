import json

import pytest
from eval_harness.log import log


def test_writes_one_json_object_per_record_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "info")

    log.info("starting run", scenarios=3)

    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"level": "info", "message": "starting run", "scenarios": 3}


def test_drops_records_below_the_configured_level(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "warn")

    log.debug("noise")
    log.info("progress")
    log.warn("retrying judge call")
    log.error("scenario could not be scored")

    lines = capsys.readouterr().err.splitlines()
    assert [json.loads(line)["level"] for line in lines] == ["warn", "error"]
