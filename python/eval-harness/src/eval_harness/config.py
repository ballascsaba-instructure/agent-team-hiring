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
    #: Per-candidate cap on the text handed to the judge in pairwise mode.
    pairwise_max_chars: int


@dataclass(frozen=True)
class HarnessConfig:
    judge: JudgeConfig
    cache_enabled: bool
    cache_dir: str
    #: Judge calls in flight at once.
    concurrency: int


DEFAULT_JUDGE_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_REGION = "us-east-1"
DEFAULT_CONCURRENCY = 5

INFERENCE_PROFILE_PREFIXES = ("us.", "eu.", "apac.")


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


def _load_judge_config(env: Env) -> JudgeConfig:
    """
    Judge settings, resolved once per run.

    A batch fires several judge calls before the first reply lands, so a model id
    Bedrock will not accept has to fail here rather than as a ValidationException
    on every worker at once. On-demand throughput needs a cross-region inference
    profile id — the same model id with a geography prefix.
    """
    model = _read_string(env, ["JUDGE_MODLE"], DEFAULT_JUDGE_MODEL)
    prefixed = any(model.startswith(prefix) for prefix in INFERENCE_PROFILE_PREFIXES)

    if not prefixed:
        raise ConfigError(
            f"JUDGE_MODEL must be a cross-region inference profile id "
            f'({", ".join(INFERENCE_PROFILE_PREFIXES)}), received "{model}"'
        )

    return JudgeConfig(
        model=model,
        region=_read_string(
            env, ["JUDGE_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"], DEFAULT_REGION
        ),
        prompt_version=_read_string(env, ["JUDGE_PROMPT_VERSION"], "v1"),
        temperature=_read_number(env, "JUDGE_TEMPERATURE", 0),
        max_output_tokens=_read_int(env, "JUDGE_MAX_OUTPUT_TOKENS", 512),
        request_timeout_ms=_read_int(env, "JUDGE_TIMEOUT_MS", 30_000),
        max_retries=_read_int(env, "JUDGE_MAX_RETRIES", 3),
        retry_base_delay_ms=_read_int(env, "JUDGE_RETRY_BASE_MS", 250),
        pairwise_max_chars=_read_int(env, "JUDGE_PAIRWISE_MAX_CHARS", 4_000),
    )


def load_config(env: Env | None = None) -> HarnessConfig:
    """
    Bedrock credentials are never read here — the AWS SDK default provider chain
    resolves them (environment, shared profile, SSO, container or instance role).
    """
    env = os.environ if env is None else env

    return HarnessConfig(
        judge=_load_judge_config(env),
        cache_enabled=_read_boolean(env, "JUDGE_CACHE_ENABLED", True),
        cache_dir=_read_string(env, ["JUDGE_CACHE_DIR"], ".eval-cache"),
        concurrency=_read_int(env, "JUDGE_CONCURRENCY", DEFAULT_CONCURRENCY),
    )
