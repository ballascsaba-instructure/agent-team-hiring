import type { RunSummary, ScenarioResult } from './runner.ts';

export interface ReportSummary {
  total: number;
  scored: number;
  errored: number;
  passed: number;
  failed: number;
  passRate: number;
  cacheHits: number;
  promptTokens: number;
  completionTokens: number;
}

function isScored(result: ScenarioResult): boolean {
  return result.status === 'scored';
}

export function summarize(run: RunSummary): ReportSummary {
  const scored = run.results.filter(isScored);
  const passed = scored.filter((result) => result.passed).length;

  return {
    total: run.totalScenarios,
    scored: scored.length,
    errored: run.results.length - scored.length,
    passed,
    failed: scored.length - passed,
    // Quoted against the dataset, so the number stays comparable between runs.
    passRate: run.totalScenarios === 0 ? 0 : passed / run.totalScenarios,
    cacheHits: run.results.filter((result) => result.cached).length,
    promptTokens: run.results.reduce((sum, result) => sum + result.promptTokens, 0),
    completionTokens: run.results.reduce((sum, result) => sum + result.completionTokens, 0),
  };
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function line(label: string, value: string | number): string {
  return `${label.padEnd(16)}${value}`;
}

export function formatReport(run: RunSummary): string {
  const summary = summarize(run);
  const lines: string[] = [
    'Evaluation report',
    '-----------------',
    line('Scenarios', summary.total),
    line('Scored', summary.scored),
    line('Errors', summary.errored),
    line('Passed', summary.passed),
    line('Failed', summary.failed),
    line('Pass rate', percent(summary.passRate)),
    line('Cache hits', summary.cacheHits),
    line('Judge tokens', `${summary.promptTokens} prompt / ${summary.completionTokens} completion`),
  ];

  const notable = run.results.filter((result) => result.status === 'error' || !result.passed);
  if (notable.length > 0) {
    lines.push('', 'Details');
    for (const result of notable) {
      const tag = result.status === 'error' ? 'ERROR' : 'FAIL ';
      const detail = result.status === 'error' ? (result.error ?? '') : result.reasoning;
      lines.push(`  ${tag} ${result.scenarioId}${detail === '' ? '' : ` — ${detail}`}`);
    }
  }

  return lines.join('\n');
}

export function printReport(run: RunSummary, write: (text: string) => void = console.log): void {
  write(formatReport(run));
}
