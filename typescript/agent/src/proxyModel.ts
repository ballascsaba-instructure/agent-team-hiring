import { BedrockRuntimeClient } from '@aws-sdk/client-bedrock-runtime';
import { ChatBedrockConverse } from '@langchain/aws';
import { HttpResponse } from '@smithy/protocol-http';
import type { HttpRequest } from '@smithy/protocol-http';
import { Readable } from 'node:stream';
import process from 'node:process';

/**
 * Runs the agent against the ai-engineer-test Bedrock proxy instead of Bedrock
 * itself, so an interview candidate needs no AWS account and no credentials —
 * just a URL and a short-lived JWT.
 *
 * The proxy speaks a *nearly* Converse-shaped protocol: a single `POST /` with
 * the model in the body and a bearer token, rather than SigV4 against
 * `/model/{modelId}/converse`. So rather than reimplement LangChain's
 * message-to-Converse translation, we let the SDK build a real Converse request
 * and rewrite it at the HTTP layer on the way out. That is the same trick the
 * Python client plays with botocore's `before-send` hook.
 */

/** The only body fields the proxy accepts — anything else is a 400. */
const ALLOWED_FIELDS = ['messages', 'system', 'inferenceConfig', 'toolConfig', 'additionalModelRequestFields'];

/** Pulls `sonnet-4.5` out of `/model/sonnet-4.5/converse`. */
function modelFromPath(path: string): string {
  const match = /^\/model\/(.+?)\/converse/.exec(path);
  if (!match?.[1]) {
    throw new Error(`Proxy supports Converse only, but the SDK requested "${path}".`);
  }
  return decodeURIComponent(match[1]);
}

function createProxyRequestHandler(proxyUrl: string, token: string) {
  return {
    // The SDK probes for these; it never needs them to do anything here.
    updateHttpClientConfig: () => {},
    httpHandlerConfigs: () => ({}),

    async handle(request: HttpRequest): Promise<{ response: HttpResponse }> {
      // The SDK hands us a Uint8Array and warns if you call string methods on
      // it, so decode explicitly rather than relying on String()/toString().
      const rawBody =
        typeof request.body === 'string'
          ? request.body
          : new TextDecoder().decode((request.body as Uint8Array | undefined) ?? new Uint8Array());

      const converse = JSON.parse(rawBody || '{}') as Record<string, unknown>;

      const body: Record<string, unknown> = { model: modelFromPath(request.path) };
      for (const field of ALLOWED_FIELDS) {
        if (converse[field] !== undefined) {
          body[field] = converse[field];
        }
      }

      const proxyResponse = await fetch(proxyUrl, {
        method: 'POST',
        headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
        body: JSON.stringify(body),
      });

      const text = await proxyResponse.text();

      // The SDK expects AWS's error envelope. Reshape the proxy's
      // `{error: {type, message}}` so a refused model surfaces as its actual
      // reason rather than an empty deserialisation failure.
      let payload = text;
      if (!proxyResponse.ok) {
        try {
          const parsed = JSON.parse(text) as {
            error?: { type?: string; message?: string };
            Reason?: string;
          };
          if (parsed.error) {
            payload = JSON.stringify({
              __type: parsed.error.type ?? 'ProxyError',
              message: parsed.error.message ?? text,
            });
          } else if (parsed.Reason) {
            // Lambda's own concurrency throttle, not the proxy's rate limiter.
            payload = JSON.stringify({
              __type: parsed.Reason,
              message: 'Lambda concurrency limit, not the rate limiter. Retry.',
            });
          }
        } catch {
          // Not JSON — pass the body through untouched.
        }
      }

      return {
        response: new HttpResponse({
          statusCode: proxyResponse.status,
          headers: Object.fromEntries(proxyResponse.headers),
          // Must be a Node stream, not a string: on Node the SDK collects the
          // body by piping it, so a string fails with `nodeStream.pipe is not a
          // function` during deserialisation.
          body: Readable.from([Buffer.from(payload, 'utf8')]),
        }),
      };
    },
  };
}

/** True when the environment is configured to talk to the proxy. */
export function proxyConfigured(): boolean {
  return Boolean(process.env['AIET_TOKEN'] && process.env['AIET_PROXY_URL']);
}

/**
 * A `ChatBedrockConverse` whose traffic is redirected to the proxy. Credentials
 * are dummies: the SDK insists on signing the request, and the proxy discards
 * the signature in favour of the bearer token.
 */
export function createProxyModel(): ChatBedrockConverse {
  const proxyUrl = process.env['AIET_PROXY_URL'];
  const token = process.env['AIET_TOKEN'];

  if (!proxyUrl || !token) {
    throw new Error('Set AIET_PROXY_URL and AIET_TOKEN to use the proxy.');
  }

  const region = 'us-west-2';

  return new ChatBedrockConverse({
    model: process.env['AGENT_MODEL'] ?? 'sonnet-4.5',
    region,
    temperature: 0,
    // The proxy clamps output to 4096 and bills input by body size, so stay modest.
    maxTokens: 2048,
    // The proxy exposes Converse but not ConverseStream.
    streaming: false,
    client: new BedrockRuntimeClient({
      region,
      credentials: { accessKeyId: 'proxy', secretAccessKey: 'proxy' },
      requestHandler: createProxyRequestHandler(proxyUrl, token),
    }),
  });
}
