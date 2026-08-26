# agent-team-hiring

Interview material for the AI engineering team. Two small projects, each written
twice — once in TypeScript, once in Python — so you can work in whichever
language you prefer. The two ports of a project mirror each other closely.

| Project | What it is |
| --- | --- |
| [`typescript/agent`](typescript/agent) · [`python/agent`](python/agent) | A minimal LangChain/LangGraph agent: one model, one tool loop, and three simple page tools. |
| [`typescript/eval-harness`](typescript/eval-harness) · [`python/eval-harness`](python/eval-harness) | A small LLM-judge eval harness that scores chat scenarios and reports pass rates. |

Each package stands alone — its own `package.json` or `pyproject.toml`, its own
lockfile, no workspace wiring. The TypeScript side needs Node >= 24 and pnpm; the
Python side needs 3.12+ and [uv](https://docs.astral.sh/uv/). Start with the
README inside whichever package you are working in; it covers setup, how to run
things, and how the code is laid out.

## Interviewers

Round structure, what to look for, and how to prepare — including generating the
model-access token for the applicant — are on Confluence:
[AI Engineering, Code Review and Technical QA](https://instructure.atlassian.net/wiki/spaces/IA2/pages/88847581250/AI+Engineering+Code+Review+and+Technical+QA).
