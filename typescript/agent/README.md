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

### Credentials

The model is Claude Sonnet 4.5 on **Amazon Bedrock** via `ChatBedrockConverse`.
Credentials come from the AWS SDK default provider chain (`AWS_PROFILE`, SSO,
env vars, instance role) — never from `.env`. You need Bedrock model access for
the inference profile in `AGENT_MODEL`.

Copy `.env.example` to `.env` to override the model or region.

## Layout

```
src/coursePages.ts  one course and its three hard-coded pages, the "backend"
src/tools.ts        the three tool definitions
src/agent.ts        model, system prompt, and the StateGraph
src/cli.ts          readline REPL that keeps the history between turns
```

`pnpm typecheck` runs `tsc --noEmit`.
