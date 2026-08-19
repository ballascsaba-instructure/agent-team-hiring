# course-agent

A deliberately minimal LangChain / LangGraph agent: one model, one tool loop,
three dummy course page tools. It exists to show the shape of a LangGraph
agent, not to do anything useful.

## The graph

```
__start__ -> agent -> (tool_calls?) -> tools -> agent -> ... -> __end__
```

`src/agent.ts` builds this by hand with `StateGraph` rather than using the
prebuilt `createAgent`, so every edge is visible:

- **agent** calls the model with the system prompt plus the running history.
- **tools** is LangGraph's `ToolNode`, which executes whatever the model asked for.
- A conditional edge routes back to `tools` while the last message has tool
  calls, and to `END` when it does not.

State is just the message list (`new StateSchema({ messages: MessagesValue })`);
`MessagesValue` supplies the reducer that appends each node's output.

## The tools

All three are dummies in `src/tools.ts`, backed by one hard-coded course and
three hard-coded pages in `src/coursePages.ts`.

| Tool | Behaviour |
| --- | --- |
| `list_course_pages` | Returns the three pages (url, title, published, updatedAt). Takes an optional `publishedOnly` filter. |
| `get_course_page` | Returns one page's full body. Accepts a url (`final-project`) or a title (`Syllabus`). |
| `update_course_page` | **Dry run.** Prints the changes it would make to the console and returns a success-shaped result. Nothing is ever written. |

Note that `update_course_page` does not advertise itself as a dry run — neither
its description nor its return value mentions it, so the model treats it as a
real write. The console output is for whoever is watching the demo.

There is no course-discovery tool, so all three operate on a single implicit
course (`COURSE` in `src/coursePages.ts`).

## Running it

Requires Node >= 24 — the `.ts` sources run directly via Node's built-in type
stripping, so there is no build step and no `tsx`.

```sh
pnpm install
pnpm dev
```

`pnpm dev` starts a line-based REPL. Type a message, press enter, Ctrl-C to quit.

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

Three ways in: the interview proxy, the Gemini API, or Bedrock. `AGENT_MODE`
picks one. Leave it unset and the agent infers a mode from whatever credentials
it can see, in that order; either way it prints the mode it settled on at
startup. All of it lives in `src/model.ts`.

| `AGENT_MODE` | Needs | Default model |
| --- | --- | --- |
| `proxy` | `AIET_PROXY_URL` and `AIET_TOKEN` | `sonnet-4.5` |
| `gemini` | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | `gemini-3.5-flash-lite` |
| `bedrock` | AWS credentials with Bedrock model access | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |

Copy `.env.example` to `.env` to configure any of them. `AGENT_MODEL` overrides
the model for whichever mode is in force, so its valid values depend on the
mode — the three columns above are not interchangeable.

**`proxy` — no AWS account, no credentials, no key of your own.** Your
interviewer supplies the token; it lasts an hour.

```sh
export AIET_TOKEN=<the token you were given>
pnpm dev
```

`src/proxyModel.ts` swaps in a request handler that rewrites the AWS SDK's
Converse call onto the proxy, so `ChatBedrockConverse` cannot tell the
difference. The proxy allows `sonnet-5`, `sonnet-4.5` and `haiku-4.5`, caps
output at 4096 tokens and bodies at 32 KB, and permits 10 requests per 60
seconds with **one request in flight at a time** — so don't run two
conversations at once.

**`gemini` — your own free API key.** Get one at
[aistudio.google.com/apikey](https://aistudio.google.com/apikey); the flash
models have a free tier.

```sh
export GOOGLE_API_KEY=<your key>
pnpm dev
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
src/coursePages.ts  one course and its three hard-coded pages, the "backend"
src/tools.ts        the three tool definitions
src/agent.ts        system prompt and the StateGraph
src/model.ts        picks between the proxy, Gemini and Bedrock
src/proxyModel.ts   redirects ChatBedrockConverse onto the interview proxy
src/cli.ts          readline REPL that keeps the history between turns
```

`pnpm typecheck` runs `tsc --noEmit`.
