"""A line-based REPL over the agent, keeping history between turns."""

import sys

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage


def run() -> None:
    # Load .env before building the model — it decides proxy versus Bedrock.
    load_dotenv()

    from .agent import build_agent
    from .pages import ensure_data_dir

    # Creates _data/ and seeds the example pages on a fresh checkout.
    try:
        print(f"Pages: {ensure_data_dir()}")
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    agent = build_agent()
    history: list[BaseMessage] = []

    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

        if not line:
            continue

        history = [*history, HumanMessage(line)]

        try:
            final_state = agent.invoke({"messages": history})
        except Exception as error:  # noqa: BLE001 — a REPL should survive any failure.
            print(f"\nError: {error}\n", file=sys.stderr)
            history.pop()
            continue

        reply = final_state["messages"][-1]
        if reply.text:
            print(f"\nAgent: {reply.text}\n")

        history = final_state["messages"]
