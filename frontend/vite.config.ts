import { readFileSync } from 'node:fs';
import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const frontendPackage = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8')) as {
    version?: string;
};

const frontendVersion = frontendPackage.version ?? '0.0.0';
const gitSha = process.env.VITE_GIT_SHA ?? process.env.GIT_SHA ?? 'dev';

export default defineConfig({
    build: { emptyOutDir: true, outDir: 'dist' },
    define: { __APP_GIT_SHA__: JSON.stringify(gitSha), __APP_VERSION__: JSON.stringify(frontendVersion) },
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
    server: {
        proxy: {
            '/analyze': 'http://localhost:8080',
            '/health': 'http://localhost:8080',
            '/version': 'http://localhost:8080',
        },
    },
});
