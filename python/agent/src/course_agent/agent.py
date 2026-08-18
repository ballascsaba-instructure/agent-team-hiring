import os

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from .tools import TOOLS

#: Cross-region inference profile for Claude Sonnet 4.5 on Bedrock.
DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_REGION = "us-east-1"

SYSTEM_PROMPT = " ".join(
    [
        "You are a course assistant. You can list the pages in a course, read a single page, and update one.",
        "Find a page with list_course_pages when you do not already know its url — never guess a url.",
        "Read a page with get_course_page before you rewrite its body, so you do not discard content.",
        "Keep answers short and concrete.",
    ]
)


class AgentState(MessagesState):
    """
    The agent's state is just the running message history. ``MessagesState``
    supplies the reducer that appends each node's returned messages to it.
    """


model = ChatBedrockConverse(
    model=os.environ.get("AGENT_MODEL") or DEFAULT_MODEL,
    region_name=os.environ.get("AGENT_AWS_REGION")
    or os.environ.get("AWS_REGION")
    or DEFAULT_REGION,
    temperature=0,
).bind_tools(TOOLS)


def call_model(state: AgentState) -> dict[str, list[AnyMessage]]:
    print("Thinking...")

    response = model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])

    # Return only the new message — the reducer appends it to the history.
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


agent = (
    StateGraph(AgentState)
    .add_node("agent", call_model)
    .add_node("tools", ToolNode(TOOLS))
    .add_edge(START, "agent")
    .add_edge("tools", "agent")
    .add_conditional_edges("agent", should_continue, ["tools", END])
    .compile()
)
