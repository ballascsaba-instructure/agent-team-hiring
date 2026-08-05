import { defineConfig } from 'vitest/config';

// LOG_LEVEL keeps the harness's own diagnostics out of the test report.
export default defineConfig({ test: { env: { LOG_LEVEL: 'silent' } } });
