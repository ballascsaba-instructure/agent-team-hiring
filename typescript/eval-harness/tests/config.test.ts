import { describe, expect, it } from 'vitest';

import { ConfigError, DEFAULT_JUDGE_MODEL, DEFAULT_REGION, loadConfig } from '../src/config.ts';

describe('loadConfig', () => {
  it('falls back to the built-in defaults', () => {
    const config = loadConfig({});

    expect(config.judge.model).toBe(DEFAULT_JUDGE_MODEL);
    expect(config.judge.region).toBe(DEFAULT_REGION);
    expect(config.judge.promptVersion).toBe('v1');
    expect(config.judge.temperature).toBe(0);
    expect(config.judge.maxRetries).toBe(3);
    expect(config.cacheEnabled).toBe(true);
    expect(config.cacheDir).toBe('.eval-cache');
  });

  it('reads the region from AWS_REGION and lets JUDGE_AWS_REGION win', () => {
    expect(loadConfig({ AWS_REGION: 'eu-west-1' }).judge.region).toBe('eu-west-1');
    expect(loadConfig({ AWS_DEFAULT_REGION: 'ap-south-1' }).judge.region).toBe('ap-south-1');
    expect(
      loadConfig({ AWS_REGION: 'eu-west-1', JUDGE_AWS_REGION: 'us-west-2' }).judge.region,
    ).toBe('us-west-2');
  });

  it('ignores blank environment values', () => {
    const config = loadConfig({ AWS_REGION: '   ', JUDGE_PROMPT_VERSION: '' });

    expect(config.judge.region).toBe(DEFAULT_REGION);
    expect(config.judge.promptVersion).toBe('v1');
  });

  it('parses numeric settings', () => {
    const config = loadConfig({
      JUDGE_TIMEOUT_MS: '1500',
      JUDGE_MAX_RETRIES: '0',
      JUDGE_TEMPERATURE: '0.2',
      JUDGE_MAX_OUTPUT_TOKENS: '128',
    });

    expect(config.judge.requestTimeoutMs).toBe(1500);
    expect(config.judge.maxRetries).toBe(0);
    expect(config.judge.temperature).toBe(0.2);
    expect(config.judge.maxOutputTokens).toBe(128);
  });

  it('rejects non-numeric and non-boolean settings', () => {
    expect(() => loadConfig({ JUDGE_TIMEOUT_MS: 'soon' })).toThrow(ConfigError);
    expect(() => loadConfig({ JUDGE_CACHE_ENABLED: 'maybe' })).toThrow(ConfigError);
  });

  it('does not read AWS credentials itself', () => {
    const config = loadConfig({ AWS_ACCESS_KEY_ID: 'AKIA-nope', AWS_SECRET_ACCESS_KEY: 'nope' });

    expect(JSON.stringify(config)).not.toContain('nope');
  });
});
