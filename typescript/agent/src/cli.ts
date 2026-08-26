#!/usr/bin/env node
import * as readline from 'node:readline';
import process from 'node:process';
import { HumanMessage } from '@langchain/core/messages';
import type { BaseMessage } from '@langchain/core/messages';

import { agent } from './agent.ts';
import { ensureDataDir } from './pages.ts';

// Creates _data/ and seeds the example pages on a fresh checkout.
console.log(`Pages: ${ensureDataDir()}`);

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

let history: BaseMessage[] = [];
let processing = false;

const chat = async (input: string): Promise<void> => {
  if (!input) {
    return;
  }

  processing = true;
  history = [...history, new HumanMessage(input)];

  try {
    const finalState = await agent.invoke({ messages: history });
    const reply = finalState.messages.at(-1);

    if (reply?.text) {
      console.log(`\nAgent: ${reply.text}\n`);
    }

    history = finalState.messages;
  } catch (error) {
    console.error(`\nError: ${error instanceof Error ? error.message : 'Unknown error'}\n`);
    history.pop();
  } finally {
    processing = false;
  }
};

rl.on('line', async (line) => {
  if (processing) return;

  await chat(line.trim());
  process.stdout.write('You: ');
}).on('close', () => {
  console.log('\nGoodbye!');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('\nGoodbye!');
  process.exit(0);
});

process.stdin.on('error', () => {
  process.exit(0);
});

process.stdout.write('You: ');
