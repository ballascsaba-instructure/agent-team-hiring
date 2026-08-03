import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { createFileCache, nullCache, verdictCacheKey } from '../src/cache.ts';
import { scenario, verdict } from './helpers.ts';

let directory: string;

beforeEach(async () => {
  directory = await mkdtemp(path.join(tmpdir(), 'eval-harness-cache-'));
});

afterEach(async () => {
  await rm(directory, { recursive: true, force: true });
});

describe('verdictCacheKey', () => {
  it('gives different scenarios different keys', () => {
    const a = verdictCacheKey({ scenario: scenario('a'), model: 'm', promptVersion: 'v1' });
    const b = verdictCacheKey({ scenario: scenario('b'), model: 'm', promptVersion: 'v1' });

    expect(a).not.toBe(b);
  });

  it('is stable for the same inputs', () => {
    const input = { scenario: scenario('a'), model: 'm', promptVersion: 'v1' };

    expect(verdictCacheKey(input)).toBe(verdictCacheKey({ ...input, scenario: scenario('a') }));
  });
});

describe('createFileCache', () => {
  it('returns undefined for an unknown key', async () => {
    const cache = createFileCache(directory);

    await expect(cache.get('missing')).resolves.toBeUndefined();
  });

  it('round-trips a verdict through disk', async () => {
    const cache = createFileCache(directory);
    const stored = verdict({ passed: false, score: 0, reasoning: 'nope' });

    await cache.set('some-key', stored);

    await expect(cache.get('some-key')).resolves.toMatchObject({
      passed: false,
      score: 0,
      reasoning: 'nope',
    });
  });

  it('creates the cache directory on demand', async () => {
    const nested = path.join(directory, 'deep', 'deeper');
    const cache = createFileCache(nested);

    await cache.set('k', verdict());

    await expect(cache.get('k')).resolves.toBeDefined();
  });

  it('treats corrupt entries as a miss', async () => {
    const cache = createFileCache(directory);
    await cache.set('k', verdict());
    await writeFile(path.join(directory, 'k.json'), '{ not json', 'utf8');

    await expect(cache.get('k')).resolves.toBeUndefined();
  });
});

describe('nullCache', () => {
  it('never returns anything', async () => {
    await nullCache.set('k', verdict());

    await expect(nullCache.get('k')).resolves.toBeUndefined();
  });
});
