import dataclasses

import pytest
from eval_harness.config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_REGION,
    ConfigError,
    load_config,
)


def test_falls_back_to_the_built_in_defaults() -> None:
    config = load_config({})

    assert config.judge.model == DEFAULT_JUDGE_MODEL
    assert config.judge.region == DEFAULT_REGION
    assert config.judge.prompt_version == "v1"
    assert config.judge.temperature == 0
    assert config.judge.max_retries == 3
    assert config.cache_enabled is True
    assert config.cache_dir == ".eval-cache"


def test_reads_the_region_from_aws_region_and_lets_judge_aws_region_win() -> None:
    assert load_config({"AWS_REGION": "eu-west-1"}).judge.region == "eu-west-1"
    assert load_config({"AWS_DEFAULT_REGION": "ap-south-1"}).judge.region == "ap-south-1"
    assert (
        load_config({"AWS_REGION": "eu-west-1", "JUDGE_AWS_REGION": "us-west-2"}).judge.region
        == "us-west-2"
    )


def test_ignores_blank_environment_values() -> None:
    config = load_config({"AWS_REGION": "   ", "JUDGE_PROMPT_VERSION": ""})

    assert config.judge.region == DEFAULT_REGION
    assert config.judge.prompt_version == "v1"


def test_parses_numeric_settings() -> None:
    config = load_config(
        {
            "JUDGE_TIMEOUT_MS": "1500",
            "JUDGE_MAX_RETRIES": "0",
            "JUDGE_TEMPERATURE": "0.2",
            "JUDGE_MAX_OUTPUT_TOKENS": "128",
        }
    )

    assert config.judge.request_timeout_ms == 1500
    assert config.judge.max_retries == 0
    assert config.judge.temperature == 0.2
    assert config.judge.max_output_tokens == 128


def test_rejects_non_numeric_and_non_boolean_settings() -> None:
    with pytest.raises(ConfigError):
        load_config({"JUDGE_TIMEOUT_MS": "soon"})
    with pytest.raises(ConfigError):
        load_config({"JUDGE_CACHE_ENABLED": "maybe"})


def test_does_not_read_aws_credentials_itself() -> None:
    config = load_config({"AWS_ACCESS_KEY_ID": "AKIA-nope", "AWS_SECRET_ACCESS_KEY": "nope"})

    assert "nope" not in str(dataclasses.asdict(config))
