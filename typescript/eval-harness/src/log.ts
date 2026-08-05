import process from 'node:process';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'silent';

const ORDER: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40, silent: 100 };

// Read straight from the environment rather than from HarnessConfig, so logging
// works before (and while) the config is loaded.
function emit(level: LogLevel, message: string, fields: Record<string, unknown>): void {
  const configured = process.env['LOG_LEVEL']?.trim().toLowerCase() ?? '';
  const threshold = configured in ORDER ? ORDER[configured as LogLevel] : ORDER.info;
  if (ORDER[level] < threshold) return;
  process.stderr.write(`${JSON.stringify({ level, message, ...fields })}\n`);
}

type Fields = Record<string, unknown>;

/**
 * One JSON object per line on stderr, so diagnostics never mix into the report
 * on stdout. `LOG_LEVEL` sets the threshold and defaults to `info`.
 *
 * Fields are for identifiers, counts and error messages. Scenario messages,
 * candidate responses and rubrics are customer conversations: nothing here
 * redacts them, and CI retains whatever a run prints.
 */
export const log = {
  debug: (message: string, fields: Fields = {}): void => emit('debug', message, fields),
  info: (message: string, fields: Fields = {}): void => emit('info', message, fields),
  warn: (message: string, fields: Fields = {}): void => emit('warn', message, fields),
  error: (message: string, fields: Fields = {}): void => emit('error', message, fields),
};
