import asyncio
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .config import JudgeConfig
from .log import log


@dataclass(frozen=True)
class JudgeMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    messages: list[JudgeMessage]
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class CompletionResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class JudgeClient(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResult: ...


class ModelResponse(Protocol):
    content: Any
    usage_metadata: Any
    response_metadata: Any


class ChatModelLike(Protocol):
    """
    The slice of a LangChain chat model this module depends on. Keeping it narrow
    lets tests supply a stub instead of reaching Bedrock.
    """

    async def ainvoke(self, input: Sequence[BaseMessage]) -> ModelResponse: ...


class JudgeApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        code: str | None = None,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


# Bedrock surfaces transient conditions as named exceptions. Everything else
# (validation errors, denied access, an unknown model id) is a caller problem
# and is surfaced immediately instead of being retried.
RETRYABLE_BEDROCK_ERRORS: frozenset[str] = frozenset(
    {
        "InternalServerException",
        "ModelNotReadyException",
        "ModelTimeoutException",
        "ServiceUnavailableException",
        "ThrottlingException",
        "TooManyRequestsException",
        "RequestTimeout",
        "RequestTimeoutException",
        "TimeoutError",
    }
)


def _aws_response(error: BaseException) -> dict[str, Any] | None:
    response = getattr(error, "response", None)
    return response if isinstance(response, dict) else None


def _error_code(error: BaseException) -> str | None:
    response = _aws_response(error)
    if response is None:
        return None
    code = response.get("Error", {}).get("Code")
    return code if isinstance(code, str) else None


def _error_status(error: BaseException) -> int | None:
    response = _aws_response(error)
    if response is None:
        return None
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status if isinstance(status, int) else None


def is_retryable_judge_error(error: BaseException) -> bool:
    code = _error_code(error)
    if code is not None and code in RETRYABLE_BEDROCK_ERRORS:
        return True

    status = _error_status(error)
    if status is not None:
        return status == 429 or status >= 500

    # No AWS metadata at all: a socket hang-up or DNS blip rather than a rejected request.
    return code is None


async def _sleep(ms: float) -> None:
    await asyncio.sleep(ms / 1000)


def _backoff_delay_ms(attempt: int, base_delay_ms: float) -> float:
    exponential: float = base_delay_ms * 2**attempt
    return exponential + random.random() * base_delay_ms


def _to_langchain_messages(messages: Sequence[JudgeMessage]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for message in messages:
        if message.role == "system":
            converted.append(SystemMessage(message.content))
        elif message.role == "assistant":
            converted.append(AIMessage(message.content))
        else:
            converted.append(HumanMessage(message.content))
    return converted


def _extract_text(content: Any) -> str:
    """Bedrock replies with either a plain string or a list of content parts."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict):
            text = part.get("text")
            parts.append(text if isinstance(text, str) else "")
    return "".join(parts)


def create_bedrock_model(config: JudgeConfig) -> ChatModelLike:
    return ChatBedrockConverse(
        model=config.model,
        region_name=config.region,
        temperature=config.temperature,
        max_tokens=config.max_output_tokens,
        # Retry policy lives in this module, so the SDK's own retries stay out of the way.
        max_retries=0,
    )


@dataclass(frozen=True)
class BedrockJudgeClient:
    config: JudgeConfig
    model: ChatModelLike

    async def _attempt(self, request: CompletionRequest) -> CompletionResult:
        try:
            response = await asyncio.wait_for(
                self.model.ainvoke(_to_langchain_messages(request.messages)),
                timeout=self.config.request_timeout_ms / 1000,
            )
        except TimeoutError as cause:
            raise JudgeApiError(
                f"judge request timed out after {self.config.request_timeout_ms}ms",
                code="TimeoutError",
                retryable=True,
            ) from cause
        except Exception as cause:
            raise JudgeApiError(
                f"judge request failed: {cause}",
                code=_error_code(cause),
                status=_error_status(cause),
                retryable=is_retryable_judge_error(cause),
            ) from cause

        content = _extract_text(response.content)
        if content.strip() == "":
            raise JudgeApiError("judge returned an empty response", retryable=False)

        usage = response.usage_metadata or {}
        model_id = (response.response_metadata or {}).get("model_id")

        return CompletionResult(
            content=content,
            model=model_id if isinstance(model_id, str) else self.config.model,
            prompt_tokens=usage.get("input_tokens") or 0,
            completion_tokens=usage.get("output_tokens") or 0,
        )

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        tries = 0
        while True:
            try:
                return await self._attempt(request)
            except Exception as error:
                api_error = (
                    error
                    if isinstance(error, JudgeApiError)
                    else JudgeApiError(str(error), retryable=False)
                )

                if not api_error.retryable or tries >= self.config.max_retries:
                    raise api_error from None

                log.warn("retrying judge call", attempt=tries + 1, code=api_error.code)
                await _sleep(_backoff_delay_ms(tries, self.config.retry_base_delay_ms))
                tries += 1


def create_judge_client(config: JudgeConfig, model: ChatModelLike | None = None) -> JudgeClient:
    return BedrockJudgeClient(config, create_bedrock_model(config) if model is None else model)
