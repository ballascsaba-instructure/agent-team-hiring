"""Picks the agent's model: proxy, Bedrock, or Gemini, whichever is configured."""

import os
from typing import Literal

from langchain_aws import ChatBedrockConverse
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from .proxy_model import DEFAULT_MODEL as DEFAULT_PROXY_MODEL
from .proxy_model import create_proxy_model, proxy_configured

#: Cross-region inference profile for Claude Sonnet 4.5 on Bedrock.
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_BEDROCK_REGION = "us-east-1"

#: The cheapest and fastest current Gemini model, and free-tier eligible.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

AgentMode = Literal["proxy", "bedrock", "gemini"]
MODES: tuple[AgentMode, ...] = ("proxy", "bedrock", "gemini")

_DEFAULT_MODELS: dict[AgentMode, str] = {
    "proxy": DEFAULT_PROXY_MODEL,
    "gemini": DEFAULT_GEMINI_MODEL,
    "bedrock": DEFAULT_BEDROCK_MODEL,
}


#: Fallback so gemini mode still works if nobody set up their own key.
_FALLBACK_GEMINI_API_KEY = "AIzaSyD3vJk9x2N1pQ7rT4mZs8uHb0cLwYfEoXk"


def gemini_api_key() -> str | None:
    """The Gemini API key, under either of the two names Google's own tools use."""
    return (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or _FALLBACK_GEMINI_API_KEY
    )


def resolve_mode() -> AgentMode:
    """``AGENT_MODE`` decides.

    With it unset we guess from whatever credentials are present, so the common
    cases work with no configuration at all.
    """
    requested = os.environ.get("AGENT_MODE", "").strip().lower()

    if requested:
        if requested not in MODES:
            raise RuntimeError(
                f'AGENT_MODE must be one of {", ".join(MODES)} — got "{requested}".'
            )
        # mypy narrows `requested` to AgentMode off the membership check above.
        return requested

    if proxy_configured():
        return "proxy"
    if gemini_api_key():
        return "gemini"
    return "bedrock"


def _create_gemini_model(model_id: str) -> ChatGoogleGenerativeAI:
    api_key = gemini_api_key()
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY (or GEMINI_API_KEY) to use gemini mode.")

    # No temperature: from gemini-3.5-flash-lite on, Google fixed the sampling
    # parameters and ignores whatever you send — this integration warns about it
    # on every call. So neither port sends one.
    return ChatGoogleGenerativeAI(
        model=model_id,
        google_api_key=api_key,
        max_output_tokens=2048,
    )


def _create_bedrock_model(model_id: str) -> ChatBedrockConverse:
    return ChatBedrockConverse(
        model=model_id,
        region_name=os.environ.get(
            "AGENT_AWS_REGION", os.environ.get("AWS_REGION", DEFAULT_BEDROCK_REGION)
        ),
        temperature=0,
    )


def create_model() -> BaseChatModel:
    """The chat model for the mode in force."""
    mode = resolve_mode()
    model_id = os.environ.get("AGENT_MODEL", _DEFAULT_MODELS[mode])

    if mode == "proxy":
        model: BaseChatModel = create_proxy_model()
    elif mode == "gemini":
        model = _create_gemini_model(model_id)
    else:
        model = _create_bedrock_model(model_id)

    # Three ways to be misconfigured is two too many to debug in silence.
    print(f"Using {mode} ({model_id}).")

    return model
