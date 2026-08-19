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

There are two ways, and the agent picks between them on its own. Copy
`.env.example` to `.env` to configure either.

**Through the interview proxy — no AWS account, no credentials.** Set
`AIET_PROXY_URL` and `AIET_TOKEN` and the agent routes there instead of Bedrock.
Your interviewer supplies the token; it lasts an hour.

```sh
export AIET_TOKEN=<the token you were given>
pnpm dev
```

The proxy allows `sonnet-5`, `sonnet-4.5` and `haiku-4.5`, caps output at 4096
tokens and bodies at 32 KB, and permits 10 requests per 60 seconds with **one
request in flight at a time** — so don't run two conversations at once.

**Straight to Bedrock.** Used whenever `AIET_TOKEN` is unset. The model is
Claude Sonnet 4.5 via `ChatBedrockConverse`, and credentials come from the AWS
SDK default provider chain (`AWS_PROFILE`, SSO, env vars, instance role) — never
from `.env`. You need Bedrock model access for the inference profile in
`AGENT_MODEL`.

### For the interviewer: minting a candidate token

Not a candidate step. This calls a token generator Lambda in the inseng account,
so it only works from **an assumed role that is allowed to invoke it**. Assume
first, every time; the session lasts an hour, same as the token. The three ways
it fails are worth telling apart:

| Error | Meaning |
| --- | --- |
| `Unable to locate credentials` | You never assumed anything |
| `ExpiredToken` | You did, but the hour lapsed — assume again |
| `AccessDeniedException` | Wrong role; it can't invoke the generator |

```sh
assume inseng-power-user -r us-west-2

t=$(mktemp) && aws lambda invoke --region us-west-2 \
  --function-name rzana-ai-engineer-test-jwt-token-generator \
  --cli-binary-format raw-in-base64-out --payload '{"duration": 3600}' "$t" >/dev/null \
  && jq -r 'sub(".*token=";"")' "$t"; rm -f "$t"
```

Hand the printed token to the candidate along with `AIET_PROXY_URL`. Mint one per
candidate — the rate-limit bucket is per token.

Two quirks worth knowing. `duration` must be 900–3600 seconds; outside that the
generator returns `{"error": …}` rather than a token, which is why you should
eyeball the output instead of piping it straight into a variable. And it answers
with a URL aimed at a decommissioned load balancer, so only the part after
`token=` still means anything — hence the `jq`.

## Layout

```
src/coursePages.ts  one course and its three hard-coded pages, the "backend"
src/tools.ts        the three tool definitions
src/agent.ts        model, system prompt, and the StateGraph
src/proxyModel.ts   redirects ChatBedrockConverse onto the interview proxy
src/cli.ts          readline REPL that keeps the history between turns
```

`pnpm typecheck` runs `tsc --noEmit`.
