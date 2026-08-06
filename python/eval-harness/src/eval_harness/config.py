import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

Env = Mapping[str, str]


@dataclass(frozen=True)
class JudgeConfig:
    #: Bedrock inference profile id, e.g. us.anthropic.claude-sonnet-4-5-20250929-v1:0
    model: str
    region: str
    prompt_version: str
    temperature: float
    max_output_tokens: int
    request_timeout_ms: int
    max_retries: int
    retry_base_delay_ms: int


@dataclass(frozen=True)
class HarnessConfig:
    judge: JudgeConfig
    cache_enabled: bool
    cache_dir: str


DEFAULT_JUDGE_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_REGION = "us-east-1"


class ConfigError(Exception):
    pass


def _read_string(env: Env, keys: Sequence[str], fallback: str) -> str:
    for key in keys:
        raw = env.get(key)
        if raw is None:
            continue
        trimmed = raw.strip()
        if trimmed != "":
            return trimmed
    return fallback


def _read_number(env: Env, key: str, fallback: float) -> float:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return fallback
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f'{key} must be a number, received "{raw}"') from None
    if not math.isfinite(value):
        raise ConfigError(f'{key} must be a number, received "{raw}"')
    return value


def _read_int(env: Env, key: str, fallback: int) -> int:
    return int(_read_number(env, key, fallback))


def _read_boolean(env: Env, key: str, fallback: bool) -> bool:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return fallback
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f'{key} must be a boolean, received "{raw}"')


def load_config(env: Env | None = None) -> HarnessConfig:
    """
    Bedrock credentials are never read here — the AWS SDK default provider chain
    resolves them (environment, shared profile, SSO, container or instance role).
    """
    env = os.environ if env is None else env

    return HarnessConfig(
        judge=JudgeConfig(
            model=_read_string(env, ["JUDGE_MODEL"], DEFAULT_JUDGE_MODEL),
            region=_read_string(
                env, ["JUDGE_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"], DEFAULT_REGION
            ),
            prompt_version=_read_string(env, ["JUDGE_PROMPT_VERSION"], "v1"),
            temperature=_read_number(env, "JUDGE_TEMPERATURE", 0),
            max_output_tokens=_read_int(env, "JUDGE_MAX_OUTPUT_TOKENS", 512),
            request_timeout_ms=_read_int(env, "JUDGE_TIMEOUT_MS", 30_000),
            max_retries=_read_int(env, "JUDGE_MAX_RETRIES", 3),
            retry_base_delay_ms=_read_int(env, "JUDGE_RETRY_BASE_MS", 250),
        ),
        cache_enabled=_read_boolean(env, "JUDGE_CACHE_ENABLED", True),
        cache_dir=_read_string(env, ["JUDGE_CACHE_DIR"], ".eval-cache"),
    )
