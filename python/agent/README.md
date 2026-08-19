# course-agent (Python)

A deliberately minimal LangChain / LangGraph agent: one model, one tool loop,
three dummy course page tools. A port of `typescript/agent`, mirroring it
module for module.

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

State is `MessagesState`, whose `add_messages` reducer appends each node's output.

## The tools

All three are dummies in `src/course_agent/tools.py`, backed by one hard-coded
course and three hard-coded pages in `course_pages.py`.

| Tool | Behaviour |
| --- | --- |
| `list_course_pages` | Returns the three pages (url, title, published, updated_at). Takes an optional `published_only` filter. |
| `get_course_page` | Returns one page's full body. Accepts a url (`final-project`) or a title (`Syllabus`). |
| `update_course_page` | **Dry run.** Prints the changes it would make and returns a success-shaped result. Nothing is ever written. |

`update_course_page` does not advertise itself as a dry run — the model treats it
as a real write. Each tool's model-facing text is passed as `description=`, which
overrides the docstring, so the docstrings can stay honest about what the
functions really do.

There is no course-discovery tool, so all three operate on a single implicit
course (`COURSE` in `course_pages.py`).

## Running it

Requires Python >= 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run course-agent
```

That starts a line-based REPL. Type a message, press enter, Ctrl-D or Ctrl-C to quit.

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

### Reaching a model

Two ways, and the agent picks between them on its own. Copy `.env.example` to
`.env` to configure either — `cli.py` loads it before building the model.

**Through the interview proxy — no AWS account, no credentials.** Set
`AIET_PROXY_URL` and `AIET_TOKEN` and the agent routes there instead of Bedrock.
Your interviewer supplies the token; it lasts an hour.

```sh
export AIET_TOKEN=<the token you were given>
uv run course-agent
```

`proxy_model.py` turns SigV4 signing off and rewrites each request onto the proxy
with botocore's `before-send` hook, so `ChatBedrockConverse` cannot tell the
difference. It is adapted from `test/try_proxy.py` in
instructure/advance-development.

The proxy allows `sonnet-5`, `sonnet-4.5` and `haiku-4.5`, caps output at 4096
tokens and bodies at 32 KB, and permits 10 requests per 60 seconds with **one
request in flight at a time** — so don't run two conversations at once.

**Straight to Bedrock.** Used whenever `AIET_TOKEN` is unset. Credentials come
from the AWS SDK default provider chain (`AWS_PROFILE`, SSO, env vars, instance
role) — never from `.env`.

Your interviewer mints the token — see the repository
[README](../../README.md) for how.

## Layout

```
src/course_agent/course_pages.py  one course and its three pages, the "backend"
src/course_agent/tools.py         the three tool definitions
src/course_agent/agent.py         model, system prompt, and the StateGraph
src/course_agent/proxy_model.py   redirects boto3 onto the interview proxy
src/course_agent/cli.py           REPL that keeps the history between turns
```

`uv run mypy` typechecks in strict mode.
