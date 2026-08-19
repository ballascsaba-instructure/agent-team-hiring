"""Route the agent through the ai-engineer-test Bedrock proxy.

A candidate then needs no AWS account and no credentials — just the proxy URL
and a short-lived JWT.

boto3 cannot reach the proxy as-is: it signs with SigV4 and POSTs to
``bedrock-runtime.<region>.amazonaws.com/model/<modelId>/converse``, whereas the
proxy wants a bearer token, a flat URL, and ``model`` inside the body. So we turn
signing off entirely and rewrite the request on its way out with botocore's
``before-send`` hook. Everything after that is real botocore, which means
``ChatBedrockConverse`` cannot tell the difference.

Adapted from ``test/try_proxy.py`` in instructure/advance-development, so the two
clients stay recognisably the same solution.
"""

import json
import os
import re
from typing import Any
from urllib.parse import unquote, urlsplit

import boto3
from botocore import UNSIGNED
from botocore.client import BaseClient
from botocore.config import Config
from langchain_aws import ChatBedrockConverse

#: The proxy lives here and nowhere else.
PROXY_REGION = "us-west-2"

#: Only the proxy's allowlist. Anything else comes back as 400 model_not_allowed.
DEFAULT_MODEL = "sonnet-4.5"

#: Headers SigV4 leaves behind that would confuse the proxy.
_STALE_HEADERS = (
    "Authorization",
    "Content-Length",
    "Host",
    "X-Amz-Date",
    "X-Amz-Security-Token",
    "X-Amz-Content-SHA256",
)


def proxy_configured() -> bool:
    """True when the environment is configured to talk to the proxy."""
    return bool(os.environ.get("AIET_TOKEN") and os.environ.get("AIET_PROXY_URL"))


def bedrock_via_proxy(token: str, url: str, region: str = PROXY_REGION) -> BaseClient:
    """A real boto3 bedrock-runtime client whose Converse calls go via the proxy."""
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(signature_version=UNSIGNED, retries={"max_attempts": 1}),
    )

    def rewrite(request: Any, **_: Any) -> None:
        found = re.search(r"/model/([^/]+)/converse", urlsplit(request.url).path)
        if not found:
            return

        body = json.loads(request.body or b"{}")
        body["model"] = unquote(found.group(1))
        payload = json.dumps(body).encode()

        request.url = url
        request.body = payload
        for header in _STALE_HEADERS:
            if header in request.headers:
                del request.headers[header]
        request.headers["Authorization"] = f"Bearer {token.strip()}"
        request.headers["Content-Type"] = "application/json"
        request.headers["Content-Length"] = str(len(payload))

    def reshape_error(response_dict: dict[str, Any] | None = None, **_: Any) -> None:
        """Translate the proxy's error shape into the one botocore expects.

        botocore's rest-json parser looks for ``__type``/``message``; without this
        a 400 arrives as a ClientError with an empty message.
        """
        if not response_dict or response_dict.get("status_code", 200) < 400:
            return
        try:
            body = json.loads(response_dict["body"] or b"{}")
        except ValueError:
            return

        if isinstance(body.get("error"), dict):
            error = body["error"]
            response_dict["body"] = json.dumps(
                {
                    "__type": error.get("type", "ProxyError"),
                    "message": error.get("message", ""),
                }
            ).encode()
        elif "Reason" in body:  # Lambda's own concurrency throttle, not our limiter.
            response_dict["body"] = json.dumps(
                {
                    "__type": body["Reason"],
                    "message": "Lambda concurrency limit, not the rate limiter. Retry.",
                }
            ).encode()

    client.meta.events.register("before-send.bedrock-runtime.Converse", rewrite)
    client.meta.events.register("before-parse.bedrock-runtime.Converse", reshape_error)
    return client


def create_proxy_model() -> ChatBedrockConverse:
    """A ChatBedrockConverse whose traffic is redirected to the proxy."""
    url = os.environ.get("AIET_PROXY_URL")
    token = os.environ.get("AIET_TOKEN")
    if not url or not token:
        raise RuntimeError("Set AIET_PROXY_URL and AIET_TOKEN to use the proxy.")

    return ChatBedrockConverse(
        model=os.environ.get("AGENT_MODEL", DEFAULT_MODEL),
        region_name=PROXY_REGION,
        temperature=0,
        # The proxy clamps output to 4096 and bills input by body size.
        max_tokens=2048,
        # The proxy exposes Converse but not ConverseStream. Saying so explicitly
        # keeps langchain-aws from warning about the short model name.
        disable_streaming=True,
        client=bedrock_via_proxy(token, url),
    )
