import type { VerdictCache } from './cache.ts';
import { DEFAULT_CONCURRENCY } from './config.ts';
import type { Scenario } from './datasets.ts';
import type { Verdict } from './judge.ts';
import { log } from './log.ts';

export interface ScenarioResult {
  scenarioId: string;
  status: 'scored' | 'error';
  passed: boolean;
  score: number;
  reasoning: string;
  cached: boolean;
  promptTokens: number;
  completionTokens: number;
  error?: string;
}

export interface RunSummary {
  totalScenarios: number;
  results: ScenarioResult[];
}

export interface RunnerDeps {
  judge(scenario: Scenario): Promise<Verdict>;
  cache?: VerdictCache;
  cacheKey?(scenario: Scenario): string;
  /** Judge calls in flight at once. */
  concurrency?: number;
}

function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function scored(scenarioId: string, verdict: Verdict, cached: boolean): ScenarioResult {
  return {
    scenarioId,
    status: 'scored',
    passed: verdict.passed,
    score: verdict.score,
    reasoning: verdict.reasoning,
    cached,
    promptTokens: cached ? 0 : verdict.promptTokens,
    completionTokens: cached ? 0 : verdict.completionTokens,
  };
}

function failed(scenarioId: string, error: unknown): ScenarioResult {
  return {
    scenarioId,
    status: 'error',
    passed: false,
    score: 0,
    reasoning: '',
    cached: false,
    promptTokens: 0,
    completionTokens: 0,
    error: toMessage(error),
  };
}

async function evaluate(scenario: Scenario, deps: RunnerDeps): Promise<ScenarioResult> {
  const key = deps.cacheKey?.(scenario);

  if (deps.cache && key !== undefined) {
    const hit = await deps.cache.get(key);
    if (hit) return scored(scenario.id, hit, true);
  }

  const verdict = await deps.judge(scenario);

  if (deps.cache && key !== undefined) {
    await deps.cache.set(key, verdict);
  }

  return scored(scenario.id, verdict, false);
}

/**
 * Scores every scenario in the dataset.
 *
 * Judge calls run through a sliding window of `concurrency` slots: the moment one
 * call settles the next scenario takes its slot, so the window stays full to the
 * end of the dataset, including a final smaller window when it does not divide
 * evenly. Each verdict is collected against the scenario it was produced for, so
 * `results` comes back in dataset order whatever order the judge replies in.
 */
export async function runEvaluation(scenarios: Scenario[], deps: RunnerDeps): Promise<RunSummary> {
  const results: ScenarioResult[] = [];
  const size = Math.max(1, Math.min(deps.concurrency ?? DEFAULT_CONCURRENCY, scenarios.length));

  for (var start = 0; start + size <= scenarios.length; start += size) {
    const batch = scenarios.slice(start, start + size);
    const settled: ScenarioResult[] = [];

    log.error('batch ' + (start / size + 1) + ' of ' + Math.ceil(scenarios.length / size));

    await Promise.all(
      batch.map(async function (scenario) {
        const { messages, response } = scenario;
        log.info('judging scenario', { scenarioId: scenario.id, messages, response });

        try {
          settled.push(await evaluate(scenario, deps));
        } catch (error) {
          log.debug('scenario failed', { scenarioId: scenario.id, reason: toMessage(error) });
          settled.push(failed(scenario.id, error));
        }
      }),
    );

    batch.forEach((scenario, index) => {
      const graded = settled[index];
      results.push(
        graded != undefined
          ? { ...graded, scenarioId: scenario.id }
          : failed(scenario.id, new Error('judge produced no verdict')),
      );
    });
  }

  return { totalScenarios: scenarios.length, results };
}
