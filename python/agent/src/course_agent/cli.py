import sys
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.pregel.protocol import PregelProtocol

#: The compiled graph, as much of its type as the CLI cares about.
Agent = PregelProtocol[Any, Any, Any, Any]


def chat(agent: Agent, history: list[AnyMessage], text: str) -> list[AnyMessage]:
    """One turn: returns the history to carry into the next one."""
    if not text:
        return history

    history = [*history, HumanMessage(text)]

    try:
        final_state = agent.invoke({"messages": history})
        messages: list[AnyMessage] = final_state["messages"]
        reply = messages[-1] if messages else None

        if reply is not None and reply.text:
            print(f"\nAgent: {reply.text}\n")

        return messages
    except Exception as error:  # a bad turn should not kill the REPL
        print(f"\nError: {str(error) or 'Unknown error'}\n", file=sys.stderr)
        return history[:-1]


def run() -> None:
    # Load .env before importing the agent module, which reads AGENT_MODEL and
    # AGENT_AWS_REGION when it builds the model at import time.
    load_dotenv()

    from .agent import agent

    history: list[AnyMessage] = []

    try:
        sys.stdout.write("You: ")
        sys.stdout.flush()

        for line in sys.stdin:
            history = chat(agent, history, line.strip())
            sys.stdout.write("You: ")
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass

    print("\nGoodbye!")
    sys.exit(0)
