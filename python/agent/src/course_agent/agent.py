"""The agent graph: a model node, a tool node, and a loop between them."""

from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from .model import create_model
from .tools import TOOLS

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


def build_agent() -> CompiledStateGraph[MessagesState, Any, Any, Any]:
    """Compile the graph.

    Built by hand with StateGraph rather than create_react_agent, so every edge
    stays visible — that is the point of the demo.

    The model comes from the proxy, Gemini or Bedrock — see ``model.py``.
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
