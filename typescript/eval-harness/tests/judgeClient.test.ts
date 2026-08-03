import { describe, expect, it, vi } from 'vitest';

import {
  createJudgeClient,
  isRetryableJudgeError,
  JudgeApiError,
  type ChatModelLike,
} from '../src/judgeClient.ts';
import { aiMessage, bedrockError, judgeConfig } from './helpers.ts';

const request = { messages: [{ role: 'user' as const, content: 'grade this' }] };

function stubModel(invoke: ChatModelLike['invoke']): { model: ChatModelLike; invoke: typeof invoke } {
  return { model: { invoke }, invoke };
}

describe('createJudgeClient', () => {
  it('invokes the model and returns the text plus token usage', async () => {
    const invoke = vi.fn(async () =>
      aiMessage('VERDICT: PASS\nREASON: fine', { input_tokens: 321, output_tokens: 12 }),
    );
    const client = createJudgeClient(judgeConfig(), stubModel(invoke).model);

    const result = await client.complete(request);

    expect(result.content).toBe('VERDICT: PASS\nREASON: fine');
    expect(result.promptTokens).toBe(321);
    expect(result.completionTokens).toBe(12);
    expect(result.model).toBe('us.anthropic.claude-sonnet-4-5-20250929-v1:0');
    expect(invoke).toHaveBeenCalledTimes(1);
  });

  it('maps roles onto LangChain message types and passes an abort signal', async () => {
    const invoke = vi.fn(async () => aiMessage('VERDICT: PASS'));
    const client = createJudgeClient(judgeConfig(), stubModel(invoke).model);

    await client.complete({
      messages: [
        { role: 'system', content: 'you grade responses' },
        { role: 'user', content: 'grade this' },
      ],
    });

    const [messages, options] = invoke.mock.calls[0] as unknown as [
      Array<{ _getType(): string; content: unknown }>,
      { signal?: AbortSignal },
    ];
    expect(messages.map((message) => message._getType())).toEqual(['system', 'human']);
    expect(messages[1]?.content).toBe('grade this');
    expect(options.signal).toBeInstanceOf(AbortSignal);
  });

  it('accepts a plain string content payload', async () => {
    const invoke = vi.fn(async () => ({ content: 'VERDICT: FAIL' }));
    const client = createJudgeClient(judgeConfig(), stubModel(invoke).model);

    await expect(client.complete(request)).resolves.toMatchObject({
      content: 'VERDICT: FAIL',
      promptTokens: 0,
      completionTokens: 0,
    });
  });

  it('retries a throttling exception and then succeeds', async () => {
    const invoke = vi
      .fn()
      .mockRejectedValueOnce(bedrockError('ThrottlingException', 429))
      .mockResolvedValueOnce(aiMessage('VERDICT: FAIL\nREASON: nope'));

    const client = createJudgeClient(judgeConfig(), { invoke });

    await expect(client.complete(request)).resolves.toMatchObject({
      content: 'VERDICT: FAIL\nREASON: nope',
    });
    expect(invoke).toHaveBeenCalledTimes(2);
  });

  it('gives up after maxRetries attempts', async () => {
    const invoke = vi.fn(async () => {
      throw bedrockError('ServiceUnavailableException', 503);
    });
    const client = createJudgeClient(judgeConfig({ maxRetries: 2 }), { invoke });

    await expect(client.complete(request)).rejects.toBeInstanceOf(JudgeApiError);
    expect(invoke).toHaveBeenCalledTimes(3);
  });

  it('rejects an empty model response', async () => {
    const invoke = vi.fn(async () => ({ content: '   ' }));
    const client = createJudgeClient(judgeConfig(), { invoke });

    await expect(client.complete(request)).rejects.toThrow(/empty response/);
  });
});

describe('isRetryableJudgeError', () => {
  it('treats throttling, timeouts and server faults as retryable', () => {
    expect(isRetryableJudgeError(bedrockError('ThrottlingException', 429))).toBe(true);
    expect(isRetryableJudgeError(bedrockError('ModelTimeoutException', 408))).toBe(true);
    expect(isRetryableJudgeError(bedrockError('InternalServerException', 500))).toBe(true);
    expect(isRetryableJudgeError(bedrockError('ServiceUnavailableException', 503))).toBe(true);
  });

  it('treats a bare network failure as retryable', () => {
    expect(isRetryableJudgeError(new Error('socket hang up'))).toBe(true);
  });
});
