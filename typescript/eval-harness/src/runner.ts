import type { VerdictCache } from './cache.ts';
import type { Scenario } from './datasets.ts';
import type { Verdict } from './judge.ts';

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

export async function runEvaluation(
  scenarios: Scenario[],
  deps: RunnerDeps,
): Promise<RunSummary> {
  const results: ScenarioResult[] = [];

  for (const scenario of scenarios) {
    try {
      results.push(await evaluate(scenario, deps));
    } catch (error) {
      results.push(failed(scenario.id, error));
    }
  }

  return { totalScenarios: scenarios.length, results };
}
