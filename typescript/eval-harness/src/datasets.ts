import { readFile } from 'node:fs/promises';

export type ChatRole = 'system' | 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

/**
 * One evaluation case. The response is already present in the dataset — the
 * harness never generates it, it only scores it.
 */
export interface Scenario {
  id: string;
  messages: ChatMessage[];
  response: string;
  rubric: string;
}

export class DatasetError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DatasetError';
  }
}

const CHAT_ROLES: readonly ChatRole[] = ['system', 'user', 'assistant'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function requireString(value: unknown, field: string, where: string): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new DatasetError(`${where}: "${field}" must be a non-empty string`);
  }
  return value;
}

function validateMessages(value: unknown, where: string): ChatMessage[] {
  if (!Array.isArray(value) || value.length === 0) {
    throw new DatasetError(`${where}: "messages" must be a non-empty array`);
  }

  return value.map((entry, index) => {
    const at = `${where} messages[${index}]`;
    if (!isRecord(entry)) {
      throw new DatasetError(`${at}: must be an object`);
    }
    const role = entry['role'];
    if (typeof role !== 'string' || !CHAT_ROLES.includes(role as ChatRole)) {
      throw new DatasetError(`${at}: "role" must be one of ${CHAT_ROLES.join(', ')}`);
    }
    const content = entry['content'];
    if (typeof content !== 'string') {
      throw new DatasetError(`${at}: "content" must be a string`);
    }
    return { role: role as ChatRole, content };
  });
}

function validateScenario(value: unknown, where: string): Scenario {
  if (!isRecord(value)) {
    throw new DatasetError(`${where}: each line must be a JSON object`);
  }

  return {
    id: requireString(value['id'], 'id', where),
    messages: validateMessages(value['messages'], where),
    response: requireString(value['response'], 'response', where),
    rubric: requireString(value['rubric'], 'rubric', where),
  };
}

export function parseScenarios(contents: string, source = '<inline>'): Scenario[] {
  const scenarios: Scenario[] = [];
  const seen = new Set<string>();
  const lines = contents.split('\n');

  for (let index = 0; index < lines.length; index += 1) {
    const line = (lines[index] ?? '').trim();
    if (line === '') continue;

    const where = `${source}:${index + 1}`;
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch (cause) {
      throw new DatasetError(`${where}: invalid JSON (${(cause as Error).message})`);
    }

    const scenario = validateScenario(parsed, where);
    if (seen.has(scenario.id)) {
      throw new DatasetError(`${where}: duplicate scenario id "${scenario.id}"`);
    }
    seen.add(scenario.id);
    scenarios.push(scenario);
  }

  if (scenarios.length === 0) {
    throw new DatasetError(`${source}: dataset contains no scenarios`);
  }

  return scenarios;
}

export async function loadScenarios(filePath: string): Promise<Scenario[]> {
  let contents: string;
  try {
    contents = await readFile(filePath, 'utf8');
  } catch (cause) {
    throw new DatasetError(`could not read dataset "${filePath}": ${(cause as Error).message}`);
  }
  return parseScenarios(contents, filePath);
}
