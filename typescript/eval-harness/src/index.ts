#!/usr/bin/env node
import process from 'node:process';

import { createFileCache, nullCache, verdictCacheKey } from './cache.ts';
import { loadConfig } from './config.ts';
import { loadScenarios } from './datasets.ts';
import { judgeScenario } from './judge.ts';
import { createJudgeClient } from './judgeClient.ts';
import { formatReport, summarize } from './report.ts';
import { runEvaluation } from './runner.ts';

const USAGE = `eval-harness run <dataset.jsonl> [options]

Options:
  --no-cache        ignore cached verdicts and re-judge every scenario
  -h, --help        show this message
`;

interface Args {
  datasetPath: string;
  useCache: boolean;
}

function parseArgs(argv: string[]): Args | undefined {
  if (argv[0] !== 'run') return undefined;

  let datasetPath: string | undefined;
  let useCache = true;

  for (const arg of argv.slice(1)) {
    if (arg === '--no-cache') {
      useCache = false;
    } else if (arg === '-h' || arg === '--help') {
      return undefined;
    } else if (arg.startsWith('-')) {
      throw new Error(`unknown option "${arg}"`);
    } else if (datasetPath === undefined) {
      datasetPath = arg;
    } else {
      throw new Error(`unexpected argument "${arg}"`);
    }
  }

  return datasetPath === undefined ? undefined : { datasetPath, useCache };
}

async function main(argv: string[]): Promise<number> {
  const args = parseArgs(argv);
  if (args === undefined) {
    process.stdout.write(USAGE);
    return 2;
  }

  const config = loadConfig();
  const scenarios = await loadScenarios(args.datasetPath);
  const client = createJudgeClient(config.judge);
  const cache =
    args.useCache && config.cacheEnabled ? createFileCache(config.cacheDir) : nullCache;

  process.stderr.write(
    `Scoring ${scenarios.length} scenarios with ${config.judge.model} in ${config.judge.region}\n`,
  );

  const run = await runEvaluation(scenarios, {
    judge: (scenario) => judgeScenario(client, scenario, config.judge),
    cache,
    cacheKey: (scenario) =>
      verdictCacheKey({
        scenario,
        model: config.judge.model,
        promptVersion: config.judge.promptVersion,
      }),
  });

  process.stdout.write(`${formatReport(run)}\n`);
  return summarize(run).errored > 0 ? 1 : 0;
}

try {
  process.exitCode = await main(process.argv.slice(2));
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
