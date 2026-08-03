import { ChatBedrockConverse } from '@langchain/aws';
import { AIMessage, HumanMessage, SystemMessage } from '@langchain/core/messages';
import type { BaseMessageLike } from '@langchain/core/messages';

import type { JudgeConfig } from './config.ts';

export interface JudgeMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface CompletionRequest {
  messages: JudgeMessage[];
  temperature?: number;
  maxTokens?: number;
}

export interface CompletionResult {
  content: string;
  model: string;
  promptTokens: number;
  completionTokens: number;
}

export interface JudgeClient {
  complete(request: CompletionRequest): Promise<CompletionResult>;
}

/**
 * The slice of a LangChain chat model this module depends on. Keeping it narrow
 * lets tests supply a stub instead of reaching Bedrock.
 */
export interface ChatModelLike {
  invoke(
    input: BaseMessageLike[],
    options?: { signal?: AbortSignal },
  ): Promise<{
    content: unknown;
    usage_metadata?: { input_tokens?: number; output_tokens?: number } | undefined;
    response_metadata?: Record<string, unknown> | undefined;
  }>;
}

export interface JudgeApiErrorOptions {
  code?: string;
  status?: number;
  retryable: boolean;
  cause?: unknown;
}

export class JudgeApiError extends Error {
  readonly code: string | undefined;
  readonly status: number | undefined;
  readonly retryable: boolean;

  constructor(message: string, options: JudgeApiErrorOptions) {
    super(message, { cause: options.cause });
    this.name = 'JudgeApiError';
    this.code = options.code;
    this.status = options.status;
    this.retryable = options.retryable;
  }
}

/**
 * Bedrock surfaces transient conditions as named exceptions. Everything else
 * (validation errors, denied access, an unknown model id) is a caller problem
 * and is surfaced immediately instead of being retried.
 */
const RETRYABLE_BEDROCK_ERRORS: ReadonlySet<string> = new Set([
  'InternalServerException',
  'ModelNotReadyException',
  'ModelTimeoutException',
  'ServiceUnavailableException',
  'ThrottlingException',
  'TooManyRequestsException',
  'RequestTimeout',
  'RequestTimeoutException',
  'TimeoutError',
]);

interface AwsErrorShape {
  name?: unknown;
  $metadata?: { httpStatusCode?: unknown };
}

function errorCode(error: unknown): string | undefined {
  const name = (error as AwsErrorShape | null)?.name;
  return typeof name === 'string' ? name : undefined;
}

function errorStatus(error: unknown): number | undefined {
  const status = (error as AwsErrorShape | null)?.$metadata?.httpStatusCode;
  return typeof status === 'number' ? status : undefined;
}

export function isRetryableJudgeError(error: unknown): boolean {
  const code = errorCode(error);
  if (code !== undefined && RETRYABLE_BEDROCK_ERRORS.has(code)) return true;

  const status = errorStatus(error);
  if (status !== undefined) return status === 429 || status >= 500;

  // No AWS metadata at all: a socket hang-up or DNS blip rather than a rejected request.
  return code === undefined || code === 'Error';
}

function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function backoffDelayMs(attempt: number, baseDelayMs: number): number {
  const exponential = baseDelayMs * 2 ** attempt;
  return exponential + Math.random() * baseDelayMs;
}

function toLangChainMessages(messages: JudgeMessage[]): BaseMessageLike[] {
  return messages.map((message) => {
    switch (message.role) {
      case 'system':
        return new SystemMessage(message.content);
      case 'assistant':
        return new AIMessage(message.content);
      default:
        return new HumanMessage(message.content);
    }
  });
}

/** Bedrock replies with either a plain string or a list of content parts. */
function extractText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';

  return content
    .map((part) => {
      if (typeof part === 'string') return part;
      const text = (part as { type?: unknown; text?: unknown } | null)?.text;
      return typeof text === 'string' ? text : '';
    })
    .join('');
}

export function createBedrockModel(config: JudgeConfig): ChatModelLike {
  return new ChatBedrockConverse({
    model: config.model,
    region: config.region,
    temperature: config.temperature,
    maxTokens: config.maxOutputTokens,
    // Retry policy lives in this module, so the SDK's own retries stay out of the way.
    maxRetries: 0,
  });
}

export function createJudgeClient(
  config: JudgeConfig,
  model: ChatModelLike = createBedrockModel(config),
): JudgeClient {
  async function attempt(request: CompletionRequest): Promise<CompletionResult> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), config.requestTimeoutMs);

    let response: Awaited<ReturnType<ChatModelLike['invoke']>>;
    try {
      response = await model.invoke(toLangChainMessages(request.messages), {
        signal: controller.signal,
      });
    } catch (cause) {
      if (controller.signal.aborted) {
        throw new JudgeApiError(`judge request timed out after ${config.requestTimeoutMs}ms`, {
          code: 'TimeoutError',
          retryable: true,
          cause,
        });
      }
      throw new JudgeApiError(`judge request failed: ${toMessage(cause)}`, {
        code: errorCode(cause),
        status: errorStatus(cause),
        retryable: isRetryableJudgeError(cause),
        cause,
      });
    } finally {
      clearTimeout(timer);
    }

    const content = extractText(response.content);
    if (content.trim() === '') {
      throw new JudgeApiError('judge returned an empty response', { retryable: false });
    }

    const modelId = response.response_metadata?.['model_id'];

    return {
      content,
      model: typeof modelId === 'string' ? modelId : config.model,
      promptTokens: response.usage_metadata?.input_tokens ?? 0,
      completionTokens: response.usage_metadata?.output_tokens ?? 0,
    };
  }

  return {
    async complete(request: CompletionRequest): Promise<CompletionResult> {
      for (let tries = 0; ; tries += 1) {
        try {
          return await attempt(request);
        } catch (error) {
          const apiError =
            error instanceof JudgeApiError
              ? error
              : new JudgeApiError(toMessage(error), { retryable: false, cause: error });

          if (!apiError.retryable || tries >= config.maxRetries) {
            throw apiError;
          }
          await sleep(backoffDelayMs(tries, config.retryBaseDelayMs));
        }
      }
    },
  };
}
