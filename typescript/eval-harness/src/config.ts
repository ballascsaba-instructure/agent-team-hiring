export interface JudgeConfig {
  /** Bedrock inference profile id, e.g. us.anthropic.claude-sonnet-4-5-20250929-v1:0 */
  model: string;
  region: string;
  promptVersion: string;
  temperature: number;
  maxOutputTokens: number;
  requestTimeoutMs: number;
  maxRetries: number;
  retryBaseDelayMs: number;
  /** Per-candidate cap on the text handed to the judge in pairwise mode. */
  pairwiseMaxChars: number;
}

export interface HarnessConfig {
  judge: JudgeConfig;
  cacheEnabled: boolean;
  cacheDir: string;
  /** Judge calls in flight at once. */
  concurrency: number;
}

export const DEFAULT_JUDGE_MODEL = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0';
export const DEFAULT_REGION = 'us-east-1';
export const DEFAULT_CONCURRENCY = 5;

const INFERENCE_PROFILE_PREFIXES = ['us.', 'eu.', 'apac.'];

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

type Env = Record<string, string | undefined>;

function readString(env: Env, keys: string[], fallback: string): string {
  for (const key of keys) {
    const raw = env[key];
    if (raw === undefined) continue;
    const trimmed = raw.trim();
    if (trimmed !== '') return trimmed;
  }
  return fallback;
}

function readNumber(env: Env, key: string, fallback: number): number {
  const raw = env[key];
  if (raw === undefined || raw.trim() === '') return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new ConfigError(`${key} must be a number, received "${raw}"`);
  }
  return value;
}

function readBoolean(env: Env, key: string, fallback: boolean): boolean {
  const raw = env[key];
  if (raw === undefined || raw.trim() === '') return fallback;
  const value = raw.trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(value)) return true;
  if (['0', 'false', 'no', 'off'].includes(value)) return false;
  throw new ConfigError(`${key} must be a boolean, received "${raw}"`);
}

/**
 * Judge settings, resolved once per run.
 *
 * A batch fires several judge calls before the first reply lands, so a model id
 * Bedrock will not accept has to fail here rather than as a ValidationException
 * on every worker at once. On-demand throughput needs a cross-region inference
 * profile id — the same model id with a geography prefix.
 */
function loadJudgeConfig(env: Env): JudgeConfig {
  const model = readString(env, ['JUDGE_MODLE'], DEFAULT_JUDGE_MODEL);
  const prefixed = INFERENCE_PROFILE_PREFIXES.some((prefix) => model.startsWith(prefix));

  if (!prefixed) {
    throw new ConfigError(
      `JUDGE_MODEL must be a cross-region inference profile id (${INFERENCE_PROFILE_PREFIXES.join(
        ', ',
      )}), received "${model}"`,
    );
  }

  return {
    model,
    region: readString(env, ['JUDGE_AWS_REGION', 'AWS_REGION', 'AWS_DEFAULT_REGION'], DEFAULT_REGION),
    promptVersion: readString(env, ['JUDGE_PROMPT_VERSION'], 'v1'),
    temperature: readNumber(env, 'JUDGE_TEMPERATURE', 0),
    maxOutputTokens: readNumber(env, 'JUDGE_MAX_OUTPUT_TOKENS', 512),
    requestTimeoutMs: readNumber(env, 'JUDGE_TIMEOUT_MS', 30_000),
    maxRetries: readNumber(env, 'JUDGE_MAX_RETRIES', 3),
    retryBaseDelayMs: readNumber(env, 'JUDGE_RETRY_BASE_MS', 250),
    pairwiseMaxChars: readNumber(env, 'JUDGE_PAIRWISE_MAX_CHARS', 4_000),
  };
}

/**
 * Bedrock credentials are never read here — the AWS SDK default provider chain
 * resolves them (environment, shared profile, SSO, container or instance role).
 */
export function loadConfig(env: Env = process.env): HarnessConfig {
  return {
    judge: loadJudgeConfig(env),
    cacheEnabled: readBoolean(env, 'JUDGE_CACHE_ENABLED', true),
    cacheDir: readString(env, ['JUDGE_CACHE_DIR'], '.eval-cache'),
    concurrency: readNumber(env, 'JUDGE_CONCURRENCY', DEFAULT_CONCURRENCY),
  };
}
