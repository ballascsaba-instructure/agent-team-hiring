# course-agent

A deliberately minimal LangChain / LangGraph agent: one model, one tool loop,
three dummy course page tools. It exists to show the shape of a LangGraph
agent, not to do anything useful.

This is a 1:1 port of `typescript/agent` — same graph, same system prompt, same
tool names, schemas and payloads.

## The graph

```
__start__ -> agent -> (tool_calls?) -> tools -> agent -> ... -> __end__
```

`src/course_agent/agent.py` builds this by hand with `StateGraph` rather than
using the prebuilt `create_react_agent`, so every edge is visible:

- **agent** calls the model with the system prompt plus the running history.
- **tools** is LangGraph's `ToolNode`, which executes whatever the model asked for.
- A conditional edge routes back to `tools` while the last message has tool
  calls, and to `END` when it does not.

State is just the message list (`AgentState(MessagesState)`); `MessagesState`
supplies the `add_messages` reducer that appends each node's output.

## The tools

All three are dummies in `src/course_agent/tools.py`, backed by one hard-coded
course and three hard-coded pages in `src/course_agent/course_pages.py`.

| Tool | Behaviour |
| --- | --- |
| `list_course_pages` | Returns the three pages (url, title, published, updatedAt). Takes an optional `publishedOnly` filter. |
| `get_course_page` | Returns one page's full body. Accepts a url (`final-project`) or a title (`Syllabus`). |
| `update_course_page` | **Dry run.** Prints the changes it would make to the console and returns a success-shaped result. Nothing is ever written. |

Note that `update_course_page` does not advertise itself as a dry run — neither
its description nor its return value mentions it, so the model treats it as a
real write. The console output is for whoever is watching the demo.

There is no course-discovery tool, so all three operate on a single implicit
course (`COURSE` in `src/course_agent/course_pages.py`).

Tool arguments and JSON payloads keep the TypeScript port's camelCase
(`publishedOnly`, `pageUrl`, `updatedAt`) — those names are part of the
model-facing contract, so both agents look identical to the model.

## Running it

Requires Python 3.12 or newer and uv (dependencies are pinned in `uv.lock`).

```sh
uv sync
uv run dev
```

`uv run dev` is the counterpart to the TypeScript agent's `pnpm dev`; it starts
a line-based REPL. Type a message, press enter, Ctrl-C or Ctrl-D to quit.

```
You: what pages are in the course?
Thinking...

Agent: Three: Syllabus, Observing the Night Sky, and Final Project Guidelines.
The last one is unpublished.

You: publish it
Thinking...
Thinking...

[update_course_page] would update "Final Project Guidelines" (final-project):
  - published: true
[update_course_page] dry run only, nothing was written.
```

`uv run course-agent` and `uv run python -m course_agent` do the same thing.

### Credentials

The model is Claude Sonnet 4.5 on **Amazon Bedrock** via `ChatBedrockConverse`.
Credentials come from the AWS SDK default provider chain (`AWS_PROFILE`, SSO,
env vars, instance role) — never from `.env`. You need Bedrock model access for
the inference profile in `AGENT_MODEL`.

Copy `.env.example` to `.env` to override the model or region.

| Variable          | Default                                        | Purpose                                       |
| ----------------- | ---------------------------------------------- | --------------------------------------------- |
| `AGENT_MODEL`     | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Bedrock inference profile for the chat model   |
| `AGENT_AWS_REGION`| _falls back to `AWS_REGION`, then `us-east-1`_ | Region to call Bedrock in                      |

## Layout

```
src/course_agent/course_pages.py  one course and its three hard-coded pages, the "backend"
src/course_agent/tools.py         the three tool definitions
src/course_agent/agent.py         model, system prompt, and the StateGraph
src/course_agent/cli.py           stdin REPL that keeps the history between turns
```

`uv run mypy` type-checks `src` in strict mode.
