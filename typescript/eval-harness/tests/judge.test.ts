import { describe, expect, it } from 'vitest';

import { buildJudgePrompt, buildPairwisePrompt } from '../src/judge.ts';
import { compareResponses, judgeScenario, parseVerdict } from '../src/judge.ts';
import type { CompletionRequest, CompletionResult, JudgeClient } from '../src/judgeClient.ts';
import { judgeConfig, scenario } from './helpers.ts';

function stubClient(content: string): { client: JudgeClient; calls: CompletionRequest[] } {
  const calls: CompletionRequest[] = [];
  const client: JudgeClient = {
    async complete(request: CompletionRequest): Promise<CompletionResult> {
      calls.push(request);
      return { content, model: 'judge-model-a', promptTokens: 42, completionTokens: 7 };
    },
  };
  return { client, calls };
}

describe('buildJudgePrompt', () => {
  it('sends a system instruction plus a single user turn', () => {
    const messages = buildJudgePrompt(scenario('s1'), 'v1');

    expect(messages).toHaveLength(2);
    expect(messages[0]?.role).toBe('system');
    expect(messages[1]?.role).toBe('user');
  });

  it('includes the conversation, the response under test and the rubric', () => {
    const target = scenario('s1', {
      messages: [
        { role: 'system', content: 'be terse' },
        { role: 'user', content: 'how do I reset my password?' },
      ],
      response: 'Use the reset link on the sign-in page.',
      rubric: 'Must point at the reset link.',
    });

    const prompt = buildJudgePrompt(target, 'v1')[1]?.content ?? '';

    expect(prompt).toContain('how do I reset my password?');
    expect(prompt).toContain('Use the reset link on the sign-in page.');
    expect(prompt).toContain('Must point at the reset link.');
  });
});

describe('parseVerdict', () => {
  it('reads the verdict and reason', () => {
    expect(parseVerdict('VERDICT: PASS\nREASON: covers the rubric')).toEqual({
      passed: true,
      reasoning: 'covers the rubric',
    });
    expect(parseVerdict('VERDICT: FAIL\nREASON: promises a refund')).toEqual({
      passed: false,
      reasoning: 'promises a refund',
    });
  });
});

describe('judgeScenario', () => {
  it('maps a judge completion onto a verdict', async () => {
    const { client, calls } = stubClient('VERDICT: PASS\nREASON: good enough');

    const verdict = await judgeScenario(client, scenario('s1'), judgeConfig());

    expect(verdict).toMatchObject({ passed: true, score: 1, reasoning: 'good enough' });
    expect(verdict.promptTokens).toBe(42);
    expect(verdict.completionTokens).toBe(7);
    expect(calls[0]?.messages).toHaveLength(2);
  });

  it('scores a failing verdict as zero', async () => {
    const { client } = stubClient('VERDICT: FAIL\nREASON: unsafe');

    await expect(judgeScenario(client, scenario('s1'), judgeConfig())).resolves.toMatchObject({
      passed: false,
      score: 0,
    });
  });
});

describe('pairwise comparison', () => {
  it('builds a prompt with both candidates', () => {
    const messages = buildPairwisePrompt(scenario('p1'), 'the other reply', judgeConfig());

    expect(messages).toHaveLength(2);
    expect(messages[1]?.content).toContain('Response A:');
    expect(messages[1]?.content).toContain('Response B:');
  });

  it('returns a winner', async () => {
    const { client } = stubClient('WINNER: A\nREASON: more specific');
    const result = await compareResponses(client, scenario('p2'), 'other', judgeConfig());

    expect(result.winner).toBeDefined();
  });
});
