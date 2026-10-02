import { existsSync, readFileSync } from 'node:fs';
import { bindings, defineConfig, defineContainer, exports, triggers } from 'cf/config';
import appPackage from '../../package.json' with { type: 'json' };

const state = existsSync('../../.cloudflare/deploy-state.json')
    ? JSON.parse(readFileSync('../../.cloudflare/deploy-state.json', 'utf8'))
    : {};
const engine = defineContainer({
    image: { buildContext: '../..', dockerfile: '../../packages/engine/Dockerfile' },
    instanceType: 'standard-1',
    maxInstances: 4,
    name: 'skalu-engine',
});
export default defineConfig({
    containers: [engine],
    worker: {
        assets: { notFoundHandling: 'single-page-application', runWorkerFirst: ['/api/*', '/health', '/version'] },
        compatibilityDate: '2026-09-29',
        compatibilityFlags: ['nodejs_compat'],
        domains: ['skalu.ilmtest.net'],
        entrypoint: 'src/worker.ts',
        env: {
            ANALYSIS: bindings.workflow({ exportName: 'AnalysisWorkflow', name: 'skalu-analysis', worker: 'skalu' }),
            APP_ORIGIN: bindings.text('https://skalu.ilmtest.net'),
            APP_VERSION: bindings.text(appPackage.version),
            ASSETS: bindings.assets(),
            BETTER_AUTH_SECRET: bindings.secret(),
            BUILD_TIME: bindings.text(state.buildTime ?? 'dev'),
            DB: bindings.d1({ id: state.databaseId ?? '00000000-0000-0000-0000-000000000000', name: 'skalu' }),
            DEPLOY_CHECK_TOKEN: bindings.secret(),
            ENGINE: bindings.durableObject({ exportName: 'EngineContainer', worker: 'skalu' }),
            FILES: bindings.r2({ name: 'skalu-files' }),
            GIT_SHA: bindings.text(state.gitSha ?? 'dev'),
        },
        exports: {
            AnalysisWorkflow: exports.workflow({ name: 'skalu-analysis' }),
            EngineContainer: exports.durableObject({ container: engine, storage: 'sqlite' }),
        },
        limits: { cpuMs: 300000, subrequests: 30000 },
        name: 'skalu',
        observability: { enabled: true, traces: { enabled: true } },
        previewUrls: false,
        triggers: [triggers.scheduled({ schedule: '*/15 * * * *' })],
        workersDev: false,
    },
});
