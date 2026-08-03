import { describe, expect, it } from 'vitest';

import { formatReport, summarize } from '../src/report.ts';
import type { RunSummary, ScenarioResult } from '../src/runner.ts';

function result(overrides: Partial<ScenarioResult> & { scenarioId: string }): ScenarioResult {
  return {
    status: 'scored',
    passed: true,
    score: 1,
    reasoning: '',
    cached: false,
    promptTokens: 100,
    completionTokens: 10,
    ...overrides,
  };
}

function run(results: ScenarioResult[]): RunSummary {
  return { totalScenarios: results.length, results };
}

describe('summarize', () => {
  it('computes the pass rate over graded scenarios', () => {
    const summary = summarize(
      run([
        result({ scenarioId: 'a' }),
        result({ scenarioId: 'b' }),
        result({ scenarioId: 'c' }),
        result({ scenarioId: 'd', passed: false, score: 0 }),
      ]),
    );

    expect(summary).toMatchObject({ total: 4, scored: 4, errored: 0, passed: 3, failed: 1 });
    expect(summary.passRate).toBeCloseTo(0.75);
  });

  it('counts errored scenarios separately from failures', () => {
    const summary = summarize(
      run([
        result({ scenarioId: 'a' }),
        result({ scenarioId: 'b', passed: false, score: 0 }),
        result({ scenarioId: 'c', status: 'error', passed: false, score: 0, error: 'boom' }),
      ]),
    );

    expect(summary.scored).toBe(2);
    expect(summary.errored).toBe(1);
    expect(summary.passed).toBe(1);
    expect(summary.failed).toBe(1);
  });

  it('reports a zero pass rate for an empty run', () => {
    expect(summarize(run([])).passRate).toBe(0);
  });

  it('totals cache hits and judge tokens', () => {
    const summary = summarize(
      run([
        result({ scenarioId: 'a', cached: true, promptTokens: 0, completionTokens: 0 }),
        result({ scenarioId: 'b', promptTokens: 250, completionTokens: 12 }),
      ]),
    );

    expect(summary.cacheHits).toBe(1);
    expect(summary.promptTokens).toBe(250);
    expect(summary.completionTokens).toBe(12);
  });
});

describe('formatReport', () => {
  it('prints the headline numbers', () => {
    const text = formatReport(
      run([result({ scenarioId: 'a' }), result({ scenarioId: 'b', passed: false, score: 0 })]),
    );

    expect(text).toContain('Scenarios       2');
    expect(text).toContain('Passed          1');
    expect(text).toContain('Pass rate       50.0%');
  });

  it('lists failures and errors with their detail', () => {
    const text = formatReport(
      run([
        result({ scenarioId: 'ok' }),
        result({ scenarioId: 'bad', passed: false, score: 0, reasoning: 'missed the rubric' }),
        result({ scenarioId: 'broken', status: 'error', passed: false, score: 0, error: 'timeout' }),
      ]),
    );

    expect(text).toContain('FAIL  bad — missed the rubric');
    expect(text).toContain('ERROR broken — timeout');
    expect(text).not.toMatch(/(FAIL|ERROR) {1,2}ok\b/);
  });
});
