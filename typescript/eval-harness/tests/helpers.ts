import type { JudgeConfig } from '../src/config.ts';
import type { Scenario } from '../src/datasets.ts';
import type { Verdict } from '../src/judge.ts';

export function judgeConfig(overrides: Partial<JudgeConfig> = {}): JudgeConfig {
  return {
    model: 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
    region: 'us-east-1',
    promptVersion: 'v1',
    temperature: 0,
    maxOutputTokens: 256,
    requestTimeoutMs: 1_000,
    maxRetries: 3,
    retryBaseDelayMs: 1,
    ...overrides,
  };
}

export function scenario(id: string, overrides: Partial<Scenario> = {}): Scenario {
  return {
    id,
    messages: [{ role: 'user', content: `question for ${id}` }],
    response: `answer for ${id}`,
    rubric: `rubric for ${id}`,
    ...overrides,
  };
}

export function verdict(overrides: Partial<Verdict> = {}): Verdict {
  return {
    passed: true,
    score: 1,
    reasoning: 'looks fine',
    raw: 'VERDICT: PASS\nREASON: looks fine',
    promptTokens: 10,
    completionTokens: 5,
    ...overrides,
  };
}

/** Shape of a Bedrock Converse reply, as the LangChain model surfaces it. */
export function aiMessage(
  text: string,
  usage: { input_tokens: number; output_tokens: number } = { input_tokens: 10, output_tokens: 5 },
): {
  content: unknown;
  usage_metadata: { input_tokens: number; output_tokens: number };
  response_metadata: Record<string, unknown>;
} {
  return {
    content: [{ type: 'text', text }],
    usage_metadata: usage,
    response_metadata: { model_id: 'us.anthropic.claude-sonnet-4-5-20250929-v1:0' },
  };
}

/** Builds an error shaped like the ones the Bedrock SDK throws. */
export function bedrockError(name: string, httpStatusCode?: number): Error {
  const error = new Error(`${name}: simulated failure`);
  error.name = name;
  Object.assign(error, { $metadata: { httpStatusCode } });
  return error;
}
