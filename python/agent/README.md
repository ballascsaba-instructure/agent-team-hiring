# course-agent (Python)

A deliberately minimal LangChain / LangGraph agent: one model, one tool loop,
three course page tools over a directory of markdown files.

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

The three tools in `src/course_agent/tools.py` sit on top of the file storage in
`course_pages.py` — one implicit course, and one markdown file per page.

| Tool | Behaviour |
| --- | --- |
| `list_course_pages` | Returns every page (url, title, published, updated_at), ordered by url. Takes an optional `published_only` filter. |
| `get_course_page` | Returns one page's full body. Accepts a url (`final-project`) or a title (`Syllabus`). |
| `update_course_page` | Writes the supplied fields back to the page's file. Omitted fields keep their current value; `updated_at` is stamped with today's date. |

Each tool's model-facing text is passed as `description=`, which overrides the
docstring, so the docstrings are free to explain how the thing actually works.

There is no course-discovery tool, so all three operate on a single implicit
course (`COURSE` in `course_pages.py`).

## The storage

Pages live as markdown files in `_data/`, one file per page, named after the
page url. `_data/` is git ignored; it is created and seeded with the three
example pages from `seed.py` the first time anything reads or writes a
page, so a fresh clone has something to talk about. Delete the directory to get
the examples back.

```
---
title: Syllabus
published: true
updated_at: 2026-07-14
---

# Syllabus
...
```

The frontmatter parser is a few lines of `key: value` splitting rather than
YAML — enough for these three fields. Every call re-reads the directory, so
files you edit by hand show up on the agent's next turn. A page's url is its
file name and never changes, even when its title does.

`_data/` sits next to `pyproject.toml` regardless of the working directory; set
`COURSE_DATA_DIR` to put it somewhere else.

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

[update_course_page] updated "Final Project Guidelines" (final-project):
  - published: true
```

### Reaching a model

Three ways in: the interview proxy, the Gemini API, or Bedrock. `AGENT_MODE`
picks one. Leave it unset and the agent infers a mode from whatever credentials
it can see, in that order; either way it prints the mode it settled on at
startup. All of it lives in `model.py`.

| `AGENT_MODE` | Needs | Default model |
| --- | --- | --- |
| `proxy` | `AIET_PROXY_URL` and `AIET_TOKEN` | `sonnet-4.5` |
| `gemini` | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | `gemini-3.5-flash-lite` |
| `bedrock` | AWS credentials with Bedrock model access | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |

Copy `.env.example` to `.env` to configure any of them — `cli.py` loads it before
building the model. `AGENT_MODEL` overrides the model for whichever mode is in
force, so its valid values depend on the mode; the three columns above are not
interchangeable.

**`proxy` — no AWS account, no credentials, no key of your own.** Your
interviewer supplies the token; it lasts an hour.

```sh
export AIET_TOKEN=<the token you were given>
uv run course-agent
```

`proxy_model.py` turns SigV4 signing off and rewrites each request onto the proxy
with botocore's `before-send` hook, so `ChatBedrockConverse` cannot tell the
difference. It is adapted from `test/try_proxy.py` in
instructure/advance-development. The proxy allows `sonnet-5`, `sonnet-4.5` and
`haiku-4.5`, caps output at 4096 tokens and bodies at 32 KB, and permits 10
requests per 60 seconds with **one request in flight at a time** — so don't run
two conversations at once.

**`gemini` — your own free API key.** Get one at
[aistudio.google.com/apikey](https://aistudio.google.com/apikey); the flash
models have a free tier.

```sh
export GOOGLE_API_KEY=<your key>
uv run course-agent
```

The free tier is rate limited per minute and per day, so a long session can
start returning 429s. The default is `gemini-3.5-flash-lite`; set `AGENT_MODEL`
to `gemini-3.7-flash` if the lite model handles the tool loop poorly.

**`bedrock` — your own AWS credentials.** Credentials come from the AWS SDK
default provider chain (`AWS_PROFILE`, SSO, env vars, instance role) — never
from `.env`. You need Bedrock model access for the inference profile in
`AGENT_MODEL`.

Your interviewer mints the proxy token — see the repository
[README](../../README.md) for how.

## Layout

```
src/course_agent/course_pages.py  markdown file storage under _data/, the "backend"
src/course_agent/seed.py          the pages a fresh _data/ is seeded with
src/course_agent/tools.py         the three tool definitions
src/course_agent/agent.py         system prompt and the StateGraph
src/course_agent/model.py         picks between the proxy, Gemini and Bedrock
src/course_agent/proxy_model.py   redirects boto3 onto the interview proxy
src/course_agent/cli.py           REPL that keeps the history between turns
```

`uv run mypy` typechecks in strict mode.
