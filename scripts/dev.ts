import { readFileSync, writeFileSync } from 'node:fs';
import { version } from '../package.json';
import { ensureSecrets } from './secrets';

const buildOnly = process.argv.includes('--prepare');
const run = async (args: string[]) => {
    const child = Bun.spawn(args, { stderr: 'inherit', stdout: 'inherit' });
    const code = await child.exited;
    if (code !== 0) {
        throw new Error(`${args.join(' ')} failed (${code}).`);
    }
};
await run(['uv', 'sync', '--project', 'packages/engine', '--frozen']);
await run(['bun', 'run', 'build']);
const secrets = await ensureSecrets('.cloudflare/local-secrets.json', ['BETTER_AUTH_SECRET', 'DEPLOY_CHECK_TOKEN']);
const config = JSON.parse(readFileSync('wrangler.jsonc', 'utf8'));
delete config.containers;
delete config.routes;
config.workers_dev = true;
config.vars = {
    ...config.vars,
    APP_ORIGIN: 'http://localhost:8787',
    APP_VERSION: version,
    ENGINE_LOCAL_URL: 'http://127.0.0.1:8080',
};
writeFileSync(
    '.dev.vars',
    Object.entries(secrets)
        .map(([key, value]) => `${key}=${value}`)
        .join('\n'),
    { mode: 0o600 },
);
writeFileSync('wrangler.local.json', JSON.stringify(config, null, 2), { mode: 0o600 });
await run(['bunx', 'wrangler', 'd1', 'migrations', 'apply', 'DB', '--local', '--config', 'wrangler.local.json']);
if (!buildOnly) {
    const children = [
        Bun.spawn(
            [
                'uv',
                'run',
                '--project',
                'packages/engine',
                'gunicorn',
                '--chdir',
                'packages/engine',
                '--bind',
                '127.0.0.1:8080',
                '--workers',
                '1',
                '--threads',
                '4',
                '--timeout',
                '180',
                'server:app',
            ],
            { stderr: 'inherit', stdout: 'inherit' },
        ),
        Bun.spawn(
            ['bunx', 'wrangler', 'dev', '--config', 'wrangler.local.json', '--port', '8787', '--ip', '127.0.0.1'],
            { stderr: 'inherit', stdout: 'inherit' },
        ),
    ];
    const close = () => {
        for (const child of children) {
            child.kill();
        }
    };
    process.on('SIGINT', close);
    process.on('SIGTERM', close);
    try {
        const code = await Promise.race(children.map((child) => child.exited));
        process.exitCode = code;
    } finally {
        close();
        await Promise.all(children.map((child) => child.exited));
    }
}
