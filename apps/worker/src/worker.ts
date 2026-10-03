import { getAuth, hashKey, requireUser } from './auth';
import { expireJob, reconcile } from './cleanup';
import { engineFetch, stopEngine } from './engine';
import { artifact, createJob, download, fail, jobDetail, json, ownJob, readJson, startJob, uploadPart } from './jobs';

export { AnalysisWorkflow } from './workflow';

export class EngineContainer extends Container {
    defaultPort = 8080;
    sleepAfter = '2m';
    enableInternet = false;
}

const keyRoute = async (request: Request, env: Env, rotate: boolean) => {
    const userId = await requireUser(request, env, true);
    if (request.method === 'GET' && !rotate) {
        return json(
            await env.DB.prepare('SELECT prefix, created_at FROM api_key WHERE user_id=?').bind(userId).first(),
        );
    }
    if (request.method !== 'POST') {
        fail('Method not allowed.', 405);
    }
    await readJson(request);
    const key = `sk_${[...crypto.getRandomValues(new Uint8Array(32))].map((byte) => byte.toString(16).padStart(2, '0')).join('')}`;
    const hash = await hashKey(key);
    const sql = rotate
        ? 'INSERT INTO api_key(user_id,hash,prefix,created_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET hash=excluded.hash,prefix=excluded.prefix,created_at=excluded.created_at'
        : 'INSERT OR IGNORE INTO api_key(user_id,hash,prefix,created_at) VALUES(?,?,?,?)';
    const result = await env.DB.prepare(sql).bind(userId, hash, key.slice(0, 11), Date.now()).run();
    if (!result.meta.changes) {
        fail('Key already issued. Rotate it to obtain a new key.', 409);
    }
    return json({ key, prefix: key.slice(0, 11) });
};

const collectionRoute = async (request: Request, env: Env, userId: string) => {
    if (request.method === 'POST') {
        return createJob(request, env, userId);
    }
    if (request.method !== 'GET') {
        fail('Method not allowed.', 405);
    }
    const jobs = (
        await env.DB.prepare(
            "SELECT id,filename,status,total,error,created_at,expires_at,(SELECT count(*) FROM page WHERE job_id=job.id) AS processed FROM job WHERE user_id=? AND status!='expired' AND expires_at>? ORDER BY created_at DESC LIMIT 20",
        )
            .bind(userId, Date.now())
            .all()
    ).results;
    return json({ jobs });
};

const apiRoute = async (request: Request, env: Env, pathname: string) => {
    if (['/api/key', '/api/key/rotate'].includes(pathname)) {
        return keyRoute(request, env, pathname.endsWith('/rotate'));
    }
    const userId = await requireUser(request, env);
    if (pathname === '/api/jobs') {
        return collectionRoute(request, env, userId);
    }
    const match = /^\/api\/jobs\/([a-f0-9-]{36})(?:\/(start|download|parts\/\d+|pages\/\d+(?:\/image)?))?$/.exec(
        pathname,
    );
    if (!match) {
        fail('Not found.', 404);
    }
    const row = await ownJob(env, match[1]!, userId);
    const action = match[2];
    if (!action && request.method === 'GET') {
        return jobDetail(env, row);
    }
    if (!action && request.method === 'DELETE') {
        await expireJob(env, row);
        return new Response(null, { status: 204 });
    }
    if (action === 'start' && request.method === 'POST') {
        await readJson(request);
        return startJob(env, row);
    }
    if (action === 'download' && request.method === 'GET') {
        return download(env, row);
    }
    if (action?.startsWith('parts/') && request.method === 'PUT') {
        return uploadPart(request, env, row, Number(action.split('/')[1]));
    }
    if (action?.startsWith('pages/') && request.method === 'GET') {
        return artifact(env, row, Number(action.split('/')[1]), action.endsWith('/image'));
    }
    return fail('Method not allowed.', 405);
};

const route = async (request: Request, env: Env) => {
    const { pathname } = new URL(request.url);
    if (pathname === '/health') {
        return json({ status: 'ok' });
    }
    if (pathname === '/version') {
        return json({ api_version: 2, build_time: env.BUILD_TIME, git_sha: env.GIT_SHA, version: env.APP_VERSION });
    }
    if (pathname === '/api/deploy-check') {
        const token = request.headers.get('authorization')?.replace(/^Bearer /, '');
        if (!token || (await hashKey(token)) !== (await hashKey(env.DEPLOY_CHECK_TOKEN))) {
            fail('Unauthorized.', 401);
        }
        await env.DB.prepare('SELECT count(*) FROM user').first();
        await env.FILES.list({ limit: 1 });
        const response = await engineFetch(env, 'deploy-check', '/health');
        if (!response.ok) {
            fail('Engine unavailable.', 503);
        }
        const engine = await response.json<{ version: string; protocol: number }>();
        if (!env.ENGINE_LOCAL_URL) {
            await stopEngine(env, 'deploy-check');
        }
        return json({ engine_version: engine.version, protocol: engine.protocol, version: env.APP_VERSION });
    }
    if (pathname.startsWith('/api/auth/')) {
        return getAuth(env).handler(request);
    }
    if (pathname.startsWith('/api/')) {
        return apiRoute(request, env, pathname);
    }
    return env.ASSETS.fetch(request);
};

export default {
    async fetch(request, env) {
        try {
            return await route(request, env);
        } catch (error) {
            if (error instanceof Response) {
                return json({ error: await error.text() }, error.status);
            }
            console.error(
                JSON.stringify({
                    event: 'request_failed',
                    message: String(error),
                    path: new URL(request.url).pathname,
                }),
            );
            return json({ error: 'Request failed. Please try again.' }, 503);
        }
    },
    async scheduled(_controller, env, ctx) {
        ctx.waitUntil(reconcile(env));
    },
} satisfies ExportedHandler<Env>;

import { Container } from '@cloudflare/containers';
