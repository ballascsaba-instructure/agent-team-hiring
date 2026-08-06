# eval-harness

A small evaluation module for chat assistants. It reads scenarios that already
contain both a conversation and the assistant response to be graded, sends each
one to an LLM judge on Amazon Bedrock, caches the verdicts, and prints a
pass-rate report.

The harness never calls a "target" model — responses come from the dataset. The
only outbound request is the judge call.

## Requirements

- Python 3.12 or newer
- uv (the repo pins dependencies in `uv.lock`)
- An AWS account with Bedrock model access granted for the judge model
- AWS credentials resolvable by the SDK default provider chain

## Setup

```bash
uv sync
cp .env.example .env   # then set AWS_REGION / AWS_PROFILE and JUDGE_MODEL
```

Credentials are **not** read from `.env` by this project. The judge uses
LangChain's `ChatBedrockConverse`, which resolves credentials through the AWS
SDK default provider chain — environment variables, a shared profile
(`AWS_PROFILE`), SSO, or a container/instance role. Sign in however you normally
would, e.g.:

```bash
aws sso login --profile my-profile
export AWS_PROFILE=my-profile
```

Configuration is read from the environment:

| Variable                  | Default                                            | Purpose                                        |
| ------------------------- | -------------------------------------------------- | ---------------------------------------------- |
| `AWS_REGION`              | `us-east-1`                                        | Region for the Bedrock runtime endpoint         |
| `JUDGE_AWS_REGION`        | _falls back to `AWS_REGION`_                        | Overrides the region for judge calls only       |
| `JUDGE_MODEL`             | `us.anthropic.claude-sonnet-4-5-20250929-v1:0`     | Bedrock model id                                |
| `JUDGE_PROMPT_VERSION`    | `v1`                                               | Judge prompt template to use                    |
| `JUDGE_TEMPERATURE`       | `0`                                                | Judge sampling temperature                      |
| `JUDGE_MAX_OUTPUT_TOKENS` | `512`                                              | Cap on judge completion length                  |
| `JUDGE_TIMEOUT_MS`        | `30000`                                            | Per-request timeout                             |
| `JUDGE_MAX_RETRIES`       | `3`                                                | Retries for transient Bedrock failures          |
| `JUDGE_RETRY_BASE_MS`     | `250`                                              | Base delay for exponential backoff              |
| `JUDGE_CONCURRENCY`       | `5`                                                | Judge calls in flight at once                   |
| `JUDGE_PAIRWISE_MAX_CHARS`| `4000`                                             | Per-candidate cap in pairwise mode              |
| `JUDGE_CACHE_ENABLED`     | `true`                                             | Whether to read/write cached verdicts           |
| `JUDGE_CACHE_DIR`         | `.eval-cache`                                      | Where cached verdicts are stored                |
| `LOG_LEVEL`               | `info`                                             | `debug`/`info`/`warn`/`error`/`silent`          |

### Model ids

Bedrock on-demand throughput requires a **cross-region inference profile id**,
not the bare model id. That is the same id with a geography prefix:

| Geography     | `JUDGE_MODEL`                                        |
| ------------- | ---------------------------------------------------- |
| United States | `us.anthropic.claude-sonnet-4-5-20250929-v1:0`        |
| Europe        | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0`        |
| Asia-Pacific  | `apac.anthropic.claude-sonnet-4-5-20250929-v1:0`      |

Using the unprefixed `anthropic.claude-sonnet-4-5-20250929-v1:0` returns a
`ValidationException` telling you to supply an inference profile instead.

## Running

```bash
uv run eval-harness run data/scenarios.sample.jsonl
uv run eval-harness run data/scenarios.sample.jsonl --no-cache
```

Output:

```
Evaluation report
-----------------
Scenarios       8
Scored          8
Errors          0
Passed          4
Failed          4
Pass rate       50.0%
Cache hits      0
Judge tokens    2568 prompt / 96 completion

Details
  FAIL  billing-refund-02 — promises a refund the assistant cannot issue
  ...
```

The process exits non-zero if any scenario could not be graded.

## Scenario format

`data/scenarios.sample.jsonl` is JSON Lines — one scenario per line:

```json
{
  "id": "billing-refund-01",
  "messages": [
    { "role": "system", "content": "You are a helpful support assistant." },
    { "role": "user", "content": "I was double charged for my subscription." }
  ],
  "response": "I'm sorry about that. I've flagged your account for a refund...",
  "rubric": "Response should acknowledge the issue, not promise actions it cannot take, and ask for an order ID."
}
```

- `id` — unique within the file; used as the cache and report key.
- `messages` — the conversation leading up to the response. Roles are
  `system`, `user` or `assistant`.
- `response` — the assistant reply being graded. It is data, not instructions.
- `rubric` — plain-English pass criteria the judge applies.

Invalid lines fail the run with the file and line number.

## Caching

Verdicts are written to `JUDGE_CACHE_DIR` as one JSON file per key. The key
covers the scenario content, the judge model and the prompt version, so
changing any of them re-judges instead of serving a stale verdict. Delete the
directory to clear it.

## Diagnostics

The report goes to stdout; everything else is one JSON object per line on stderr,
filtered by `LOG_LEVEL` (`info` by default). Log fields are for identifiers, counts and
error messages — scenario messages, candidate responses and rubrics are customer
conversations, and nothing in the pipeline redacts them.

## Development

```bash
uv run pytest      # no AWS access required
uv run mypy        # strict type checking
```

Unit tests inject a stub chat model, so nothing in the test suite reaches
Bedrock.

## Layout

```
src/eval_harness/config.py        env + config loading, judge model settings
src/eval_harness/judge_client.py  Bedrock judge client: retries, timeout, token usage
src/eval_harness/datasets.py      loads chat scenarios from JSONL, validates them
src/eval_harness/judge.py         builds judge prompts, parses verdicts, pairwise mode
src/eval_harness/runner.py        concurrent orchestration over scenarios
src/eval_harness/cache.py         file-based verdict cache
src/eval_harness/log.py           levelled JSON logging to stderr
src/eval_harness/report.py        aggregation, pass-rate math, console output
src/eval_harness/cli.py           CLI entry point
```
