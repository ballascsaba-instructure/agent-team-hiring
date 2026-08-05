import process from 'node:process';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { log } from '../src/log.ts';

const lines: string[] = [];

afterEach(() => {
  lines.length = 0;
  delete process.env['LOG_LEVEL'];
  vi.restoreAllMocks();
});

function captureStderr(level: string): void {
  process.env['LOG_LEVEL'] = level;
  vi.spyOn(process.stderr, 'write').mockImplementation((chunk) => !!lines.push(String(chunk)));
}

describe('log', () => {
  it('writes one JSON object per record to stderr', () => {
    captureStderr('info');
    log.info('starting run', { scenarios: 3 });

    expect(lines).toHaveLength(1);
    expect(JSON.parse(lines[0] ?? '')).toEqual({
      level: 'info',
      message: 'starting run',
      scenarios: 3,
    });
  });

  it('drops records below the configured level', () => {
    captureStderr('warn');
    log.debug('noise');
    log.info('progress');
    log.warn('retrying judge call');
    log.error('scenario could not be scored');

    expect(lines.map((line) => JSON.parse(line).level)).toEqual(['warn', 'error']);
  });
});
