import { chmodSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { ensureSecrets } from './secrets';

const run = async (args: string[], capture = false, cwd?: string): Promise<string> => {
    const child = Bun.spawn(args, {
        cwd,
        env: { ...process.env, CI: 'true', WRANGLER_SEND_METRICS: 'false' },
        stderr: capture ? 'pipe' : 'inherit',
        stdout: capture ? 'pipe' : 'inherit',
    });
    const [code, stdout, stderr] = await Promise.all([
        child.exited,
        capture ? new Response(child.stdout).text() : Promise.resolve(''),
        capture ? new Response(child.stderr).text() : Promise.resolve(''),
    ]);
    if (code !== 0) {
        const detail = stderr || stdout;
        throw new Error(`${args.join(' ')} failed (${code}): ${detail}`);
    }
    return stdout;
};
const cf = (args: string[], capture = false, cwd?: string) => run(['cf', ...args], capture, cwd);
const parse = <T>(value: string): T => {
    try {
        return JSON.parse(value);
    } catch {
        throw new Error('Cloudflare returned invalid JSON. Deployment stopped.');
    }
};

let startedBuilder = false;
const prepareDocker = async () => {
    const ready = () =>
        run(['docker', 'info', '--format', '{{.ServerVersion}}'], true).then(
            () => true,
            () => false,
        );
    if (await ready()) {
        return;
    }
    if (
        process.platform !== 'darwin' ||
        !Bun.which('colima') ||
        process.env.DOCKER_HOST ||
        (process.env.DOCKER_CONTEXT && process.env.DOCKER_CONTEXT !== 'colima-skalu')
    ) {
        throw new Error('Start your Docker engine before deploying. On macOS, Colima is also supported.');
    }
    process.env.DOCKER_CONTEXT = 'colima-skalu';
    if (!(await ready())) {
        startedBuilder = true;
        await run([
            'colima',
            'start',
            'skalu',
            '--activate=false',
            '--cpus',
            '2',
            '--memory',
            '4',
            '--disk',
            '20',
            '--mount',
            'none',
            '--vm-type',
            'vz',
        ]);
    }
    if (!(await ready())) {
        throw new Error('Skalu builder could not start.');
    }
};

const provision = async (version: string) => {
    const databases = parse<{ uuid: string; name: string }[]>(await cf(['d1', 'list', '--name', 'skalu'], true));
    let database = databases.find((database) => database.name === 'skalu');
    if (!database) {
        await cf(['d1', 'create', '--name', 'skalu']);
        database = parse<{ uuid: string; name: string }[]>(await cf(['d1', 'list', '--name', 'skalu'], true)).find(
            (item) => item.name === 'skalu',
        );
    }
    if (!database) {
        throw new Error('D1 provisioning failed.');
    }
    const { buckets } = parse<{ buckets: { name: string }[] }>(await cf(['r2', 'buckets', 'list'], true));
    if (!buckets.some((bucket) => bucket.name === 'skalu-files')) {
        await cf(['r2', 'buckets', 'create', '--name', 'skalu-files']);
    }
    const lifecycle = parse<{ rules: { id: string }[] }>(
        await cf(['r2', 'buckets', 'lifecycle', 'get', 'skalu-files'], true),
    );
    const rules = [
        ...lifecycle.rules.filter((rule) => rule.id !== 'skalu-expiry'),
        {
            abortMultipartUploadsTransition: { condition: { maxAge: 86400, type: 'Age' } },
            conditions: { prefix: 'jobs/' },
            deleteObjectsTransition: { condition: { maxAge: 172800, type: 'Age' } },
            enabled: true,
            id: 'skalu-expiry',
        },
    ];
    await ensureSecrets('.cloudflare/production-secrets.json', []);
    writeFileSync('.cloudflare/lifecycle.json', JSON.stringify(rules));
    await cf([
        'r2',
        'buckets',
        'lifecycle',
        'update',
        'skalu-files',
        '--rules',
        '@.cloudflare/lifecycle.json',
        '--force',
    ]);
    const gitSha = (await run(['git', 'rev-parse', '--short', 'HEAD'], true)).trim();
    const dirty = (await run(['git', 'status', '--porcelain'], true)).trim().length > 0;
    writeFileSync(
        '.cloudflare/deploy-state.json',
        JSON.stringify({
            buildTime: new Date().toISOString(),
            databaseId: database.uuid,
            gitSha: `${gitSha}${dirty ? '-dirty' : ''}`,
            version,
        }),
    );
    let remote: { name: string }[];
    try {
        remote = parse(await cf(['workers', 'secrets', 'list', '--worker', 'skalu'], true));
    } catch (error) {
        if (!/\b10007\b/.test(String(error))) {
            throw error;
        }
        remote = [];
    }
    return { database, origin: 'https://skalu.ilmtest.net', remote };
};

const verifyRollout = async (origin: string, version: string, token: string) => {
    console.log('Worker uploaded. Verifying database, storage, and engine rollout…');
    const deadline = Date.now() + 10 * 60000;
    while (Date.now() < deadline) {
        try {
            const response = await fetch(`${origin}/api/deploy-check`, {
                headers: { authorization: `Bearer ${token}` },
                signal: AbortSignal.timeout(45000),
            });
            if (response.ok) {
                const health = await response.json<{ version: string; engine_version: string; protocol: number }>();
                if (health.version === version && health.engine_version === version && health.protocol === 1) {
                    console.log(`Deployed Skalu ${version}: ${origin}`);
                    return;
                }
            }
        } catch {
            /* First container rollout can take several minutes. */
        }
        await Bun.sleep(10000);
    }
    throw new Error(
        'Worker uploaded, but engine rollout verification timed out. Inspect cf containers applications list.',
    );
};

const main = async () => {
    // No remote mutations before credentials, Docker, checks, and the native image pass.
    const identity = parse<{ accounts: { id: string }[]; authenticated: boolean }>(await cf(['auth', 'whoami'], true));
    const accountId =
        process.env.CLOUDFLARE_ACCOUNT_ID ?? (identity.accounts.length === 1 ? identity.accounts[0]?.id : undefined);
    if (!accountId || !identity.accounts.some((account) => account.id === accountId)) {
        throw new Error('Set CLOUDFLARE_ACCOUNT_ID to one authenticated account.');
    }
    process.env.CLOUDFLARE_ACCOUNT_ID = accountId;
    if (!identity.authenticated) {
        throw new Error('Authenticate with cf login before deploying.');
    }
    await prepareDocker();
    await run(['bun', 'run', 'typecheck']);
    await run(['bun', 'run', 'check']);
    await run(['bun', 'run', 'test']);
    await run(['bun', 'run', 'test:engine']);
    await run(['bun', 'run', 'build']);
    const version = parse<{ version: string }>(readFileSync('package.json', 'utf8')).version;
    await run([
        'docker',
        'build',
        '--platform',
        'linux/amd64',
        '-t',
        `skalu-engine:${version}`,
        '-f',
        'packages/engine/Dockerfile',
        '.',
    ]);
    const { database, origin, remote } = await provision(version);
    const secrets: Record<string, string> = { DEPLOY_CHECK_TOKEN: crypto.randomUUID() + crypto.randomUUID() };
    if (!remote.some((secret) => secret.name === 'BETTER_AUTH_SECRET')) {
        const local = await ensureSecrets('.cloudflare/production-secrets.json', ['BETTER_AUTH_SECRET']);
        secrets.BETTER_AUTH_SECRET = local.BETTER_AUTH_SECRET!;
    }
    const secretPath = '.cloudflare/deploy-secrets.json';
    await ensureSecrets('.cloudflare/production-secrets.json', []);
    writeFileSync(secretPath, JSON.stringify(secrets), { mode: 0o600 });
    chmodSync(secretPath, 0o600);
    try {
        await cf(['d1', 'migrations', 'apply', database.uuid, '--dir', 'migrations']);
        await cf(['deploy', '--secrets-file', `../../${secretPath}`], false, 'apps/worker');
        await verifyRollout(origin, version, secrets.DEPLOY_CHECK_TOKEN!);
    } finally {
        unlinkSync(secretPath);
    }
};

try {
    await main();
} catch (error) {
    console.error(String(error));
    process.exitCode = 1;
} finally {
    if (startedBuilder) {
        await run(['colima', 'stop', 'skalu']);
    }
}
