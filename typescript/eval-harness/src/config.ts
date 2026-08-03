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
}

export interface HarnessConfig {
  judge: JudgeConfig;
  cacheEnabled: boolean;
  cacheDir: string;
}

export const DEFAULT_JUDGE_MODEL = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0';
export const DEFAULT_REGION = 'us-east-1';

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
 * Bedrock credentials are never read here — the AWS SDK default provider chain
 * resolves them (environment, shared profile, SSO, container or instance role).
 */
export function loadConfig(env: Env = process.env): HarnessConfig {
  return {
    judge: {
      model: readString(env, ['JUDGE_MODEL'], DEFAULT_JUDGE_MODEL),
      region: readString(env, ['JUDGE_AWS_REGION', 'AWS_REGION', 'AWS_DEFAULT_REGION'], DEFAULT_REGION),
      promptVersion: readString(env, ['JUDGE_PROMPT_VERSION'], 'v1'),
      temperature: readNumber(env, 'JUDGE_TEMPERATURE', 0),
      maxOutputTokens: readNumber(env, 'JUDGE_MAX_OUTPUT_TOKENS', 512),
      requestTimeoutMs: readNumber(env, 'JUDGE_TIMEOUT_MS', 30_000),
      maxRetries: readNumber(env, 'JUDGE_MAX_RETRIES', 3),
      retryBaseDelayMs: readNumber(env, 'JUDGE_RETRY_BASE_MS', 250),
    },
    cacheEnabled: readBoolean(env, 'JUDGE_CACHE_ENABLED', true),
    cacheDir: readString(env, ['JUDGE_CACHE_DIR'], '.eval-cache'),
  };
}
