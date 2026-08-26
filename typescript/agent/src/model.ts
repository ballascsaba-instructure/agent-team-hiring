/** Picks the agent's model: proxy, Bedrock, or Gemini, whichever is configured. */
import { ChatBedrockConverse } from '@langchain/aws';
import { ChatGoogleGenerativeAI } from '@langchain/google-genai';
import process from 'node:process';
import type { BaseChatModel } from '@langchain/core/language_models/chat_models';

import { createProxyModel, proxyConfigured } from './proxyModel.ts';

/** Cross-region inference profile for Claude Sonnet 4.5 on Bedrock. */
const DEFAULT_BEDROCK_MODEL = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0';
const DEFAULT_BEDROCK_REGION = 'us-east-1';

/** The cheapest and fastest current Gemini model, and free-tier eligible. */
const DEFAULT_GEMINI_MODEL = 'gemini-3.5-flash-lite';

/**
 * A chat model that accepts tools. `BaseChatModel.bindTools` is optional —
 * models that cannot call tools simply omit it — so say out loud that every
 * branch here returns one that can.
 */
export type ToolCallingModel = BaseChatModel & Required<Pick<BaseChatModel, 'bindTools'>>;

export const MODES = ['proxy', 'bedrock', 'gemini'] as const;
export type AgentMode = (typeof MODES)[number];

function isMode(value: string): value is AgentMode {
  return (MODES as readonly string[]).includes(value);
}

/** The Gemini API key, under either of the two names Google's own tools use. */
function geminiApiKey(): string | undefined {
  return process.env['GOOGLE_API_KEY'] ?? process.env['GEMINI_API_KEY'];
}

/**
 * `AGENT_MODE` decides. With it unset we guess from whatever credentials are
 * present, so the common cases work with no configuration at all.
 */
export function resolveMode(): AgentMode {
  const requested = process.env['AGENT_MODE']?.trim().toLowerCase();

  if (requested) {
    if (!isMode(requested)) {
      throw new Error(`AGENT_MODE must be one of ${MODES.join(', ')} — got "${requested}".`);
    }
    return requested;
  }

  if (proxyConfigured()) return 'proxy';
  if (geminiApiKey()) return 'gemini';
  return 'bedrock';
}

function createGeminiModel(): ChatGoogleGenerativeAI {
  const apiKey = geminiApiKey();
  if (!apiKey) {
    throw new Error('Set GOOGLE_API_KEY (or GEMINI_API_KEY) to use gemini mode.');
  }

  return new ChatGoogleGenerativeAI({
    model: process.env['AGENT_MODEL'] ?? DEFAULT_GEMINI_MODEL,
    apiKey,
    // No temperature: from gemini-3.5-flash-lite on, Google fixed the sampling
    // parameters and ignores whatever you send. The Python integration warns
    // about it on every call, so neither port sends one.
    maxOutputTokens: 2048,
  });
}

function createBedrockModel(): ChatBedrockConverse {
  return new ChatBedrockConverse({
    model: process.env['AGENT_MODEL'] ?? DEFAULT_BEDROCK_MODEL,
    region:
      process.env['AGENT_AWS_REGION'] ?? process.env['AWS_REGION'] ?? DEFAULT_BEDROCK_REGION,
    temperature: 0,
  });
}

/** The chat model for the mode in force. */
export function createModel(): ToolCallingModel {
  const mode = resolveMode();

  const model =
    mode === 'proxy'
      ? createProxyModel()
      : mode === 'gemini'
        ? createGeminiModel()
        : createBedrockModel();

  // Three ways to be misconfigured is two too many to debug in silence.
  console.log(`Using ${mode} (${model.model}).`);

  return model;
}
