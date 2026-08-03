import { describe, expect, it, vi } from 'vitest';

import type { VerdictCache } from '../src/cache.ts';
import type { Scenario } from '../src/datasets.ts';
import type { Verdict } from '../src/judge.ts';
import { runEvaluation } from '../src/runner.ts';
import { scenario, verdict } from './helpers.ts';

function memoryCache(seed: Record<string, Verdict> = {}): VerdictCache & { store: Map<string, Verdict> } {
  const store = new Map<string, Verdict>(Object.entries(seed));
  return {
    store,
    async get(key: string): Promise<Verdict | undefined> {
      return store.get(key);
    },
    async set(key: string, value: Verdict): Promise<void> {
      store.set(key, value);
    },
  };
}

const scenarios: Scenario[] = [scenario('a'), scenario('b'), scenario('c')];

describe('runEvaluation', () => {
  it('scores every scenario and keeps dataset order', async () => {
    const judge = vi.fn(async (target: Scenario) =>
      verdict({ passed: target.id !== 'b', score: target.id === 'b' ? 0 : 1 }),
    );

    const run = await runEvaluation(scenarios, { judge });

    expect(run.totalScenarios).toBe(3);
    expect(run.results.map((r) => r.scenarioId)).toEqual(['a', 'b', 'c']);
    expect(run.results.map((r) => r.passed)).toEqual([true, false, true]);
    expect(judge).toHaveBeenCalledTimes(3);
  });

  it('records a judge failure as an errored result without aborting the run', async () => {
    const judge = vi.fn(async (target: Scenario) => {
      if (target.id === 'b') throw new Error('judge API responded 401: invalid key');
      return verdict();
    });

    const run = await runEvaluation(scenarios, { judge });

    expect(run.results.map((r) => r.status)).toEqual(['scored', 'error', 'scored']);
    expect(run.results[1]?.error).toMatch(/401/);
    expect(run.results[1]?.passed).toBe(false);
  });

  it('serves cached verdicts without calling the judge', async () => {
    const cache = memoryCache({ 'key-a': verdict({ reasoning: 'from cache' }) });
    const judge = vi.fn(async () => verdict());

    const run = await runEvaluation([scenario('a')], {
      judge,
      cache,
      cacheKey: (target) => `key-${target.id}`,
    });

    expect(judge).not.toHaveBeenCalled();
    expect(run.results[0]).toMatchObject({ cached: true, reasoning: 'from cache' });
    expect(run.results[0]?.promptTokens).toBe(0);
  });

  it('writes fresh verdicts back to the cache', async () => {
    const cache = memoryCache();
    const judge = vi.fn(async () => verdict({ reasoning: 'fresh' }));

    await runEvaluation([scenario('a')], { judge, cache, cacheKey: (target) => `key-${target.id}` });

    expect(cache.store.get('key-a')?.reasoning).toBe('fresh');
  });
});
