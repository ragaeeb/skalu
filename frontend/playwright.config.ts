import { defineConfig } from '@playwright/test';

export default defineConfig({
    fullyParallel: true,
    retries: 1,
    testDir: './e2e',
    use: { baseURL: 'http://127.0.0.1:4173', headless: true },
    webServer: {
        command: 'bun run build && bun run preview --host 127.0.0.1 --port 4173',
        port: 4173,
        reuseExistingServer: true,
        timeout: 120000,
    },
});
