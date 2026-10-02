import { defineConfig } from '@playwright/test';
export default defineConfig({
    fullyParallel: false,
    projects: [
        { name: 'api', testMatch: ['**/api.spec.ts', '**/multipart.spec.ts'] },
        { name: 'browser', testMatch: '**/workflow.spec.ts', use: { browserName: 'chromium' } },
    ],
    retries: 0,
    testDir: './e2e',
    timeout: 120000,
    use: { baseURL: process.env.SKALU_E2E_ORIGIN ?? 'http://localhost:8787', trace: 'retain-on-failure' },
    webServer: process.env.SKALU_E2E_ORIGIN
        ? undefined
        : {
              command: 'bun scripts/dev.ts',
              reuseExistingServer: !process.env.CI,
              timeout: 120000,
              url: 'http://localhost:8787/health',
          },
    workers: 1,
});
