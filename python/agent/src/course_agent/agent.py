"""The agent graph: a model node, a tool node, and a loop between them."""

import os
from typing import Any

from langchain_aws import ChatBedrockConverse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from .proxy_model import create_proxy_model, proxy_configured
from .tools import TOOLS

#: Cross-region inference profile for Claude Sonnet 4.5 on Bedrock.
DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_REGION = "us-east-1"

SYSTEM_PROMPT = " ".join(
    [
        "You are a course assistant. You can list the pages in a course, read a single page,"
        " and update one.",
        "Find a page with list_course_pages when you do not already know its url — never guess"
        " a url.",
        "Read a page with get_course_page before you rewrite its body, so you do not discard"
        " content.",
        "Keep answers short and concrete.",
    ]
)


def create_model() -> BaseChatModel:
    """Either straight to Bedrock with AWS credentials, or through the interview proxy.

    The graph below cannot tell the difference.
    """
    if proxy_configured():
        return create_proxy_model()

    return ChatBedrockConverse(
        model=os.environ.get("AGENT_MODEL", DEFAULT_MODEL),
        region_name=os.environ.get("AGENT_AWS_REGION", os.environ.get("AWS_REGION", DEFAULT_REGION)),
        temperature=0,
    )


def build_agent() -> CompiledStateGraph[MessagesState, Any, Any, Any]:
    """Compile the graph.

    Built by hand with StateGraph rather than create_react_agent, so every edge
    stays visible — that is the point of the demo.
    """
    model = create_model().bind_tools(TOOLS)

    def call_model(state: MessagesState) -> dict[str, list[AIMessage]]:
        print("Thinking...")
        response = model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        # Return only the new message — add_messages appends it to the history.
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    return (
        StateGraph(MessagesState)
        .add_node("agent", call_model)
        .add_node("tools", ToolNode(TOOLS))
        .add_edge(START, "agent")
        .add_edge("tools", "agent")
        .add_conditional_edges("agent", should_continue, ["tools", END])
        .compile()
    )
