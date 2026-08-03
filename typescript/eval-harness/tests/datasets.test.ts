import { describe, expect, it } from 'vitest';

import { DatasetError, loadScenarios, parseScenarios } from '../src/datasets.ts';

const validLine = JSON.stringify({
  id: 'a',
  messages: [{ role: 'user', content: 'hi' }],
  response: 'hello',
  rubric: 'be polite',
});

describe('parseScenarios', () => {
  it('parses one scenario per line and ignores blank lines', () => {
    const other = JSON.stringify({
      id: 'b',
      messages: [
        { role: 'system', content: 'be brief' },
        { role: 'user', content: 'hi' },
      ],
      response: 'hey',
      rubric: 'be brief',
    });

    const scenarios = parseScenarios(`${validLine}\n\n${other}\n`);

    expect(scenarios.map((s) => s.id)).toEqual(['a', 'b']);
    expect(scenarios[1]?.messages).toHaveLength(2);
  });

  it('reports the line number of invalid JSON', () => {
    expect(() => parseScenarios(`${validLine}\nnot json\n`, 'ds.jsonl')).toThrow(/ds\.jsonl:2/);
  });

  it('rejects missing or empty required fields', () => {
    const noRubric = JSON.stringify({ id: 'a', messages: [{ role: 'user', content: 'hi' }], response: 'x' });
    const emptyResponse = JSON.stringify({ ...JSON.parse(validLine), response: '  ' });

    expect(() => parseScenarios(noRubric)).toThrow(/"rubric"/);
    expect(() => parseScenarios(emptyResponse)).toThrow(/"response"/);
  });

  it('rejects unknown message roles and empty conversations', () => {
    const badRole = JSON.stringify({ ...JSON.parse(validLine), messages: [{ role: 'tool', content: 'x' }] });
    const noMessages = JSON.stringify({ ...JSON.parse(validLine), messages: [] });

    expect(() => parseScenarios(badRole)).toThrow(/"role"/);
    expect(() => parseScenarios(noMessages)).toThrow(/"messages"/);
  });

  it('rejects duplicate ids and empty datasets', () => {
    expect(() => parseScenarios(`${validLine}\n${validLine}`)).toThrow(/duplicate scenario id "a"/);
    expect(() => parseScenarios('\n\n')).toThrow(/no scenarios/);
  });
});

describe('loadScenarios', () => {
  it('loads the bundled sample dataset', async () => {
    const scenarios = await loadScenarios(new URL('../data/scenarios.sample.jsonl', import.meta.url).pathname);

    expect(scenarios.length).toBeGreaterThanOrEqual(8);
    for (const scenario of scenarios) {
      expect(scenario.rubric).not.toBe('');
      expect(scenario.messages.length).toBeGreaterThan(0);
    }
  });

  it('wraps filesystem errors', async () => {
    await expect(loadScenarios('./does-not-exist.jsonl')).rejects.toBeInstanceOf(DatasetError);
  });
});
