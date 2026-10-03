import { expect, it } from 'bun:test';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { getPlatformProxy } from 'wrangler';
import { expireJob } from '../apps/worker/src/cleanup';
import { createJob, type JobRow } from '../apps/worker/src/jobs';

it('should retry failed Workflow termination and retain capacity/storage until native shutdown succeeds', async () => {
    const directory = mkdtempSync(join(tmpdir(), 'skalu-cleanup-'));
    const configPath = join(directory, 'wrangler.json');
    writeFileSync(
        configPath,
        JSON.stringify({
            compatibility_date: '2026-09-29',
            d1_databases: [{ binding: 'DB', database_id: crypto.randomUUID(), database_name: 'cleanup-test' }],
            name: 'cleanup-test',
            r2_buckets: [{ binding: 'FILES', bucket_name: 'cleanup-test' }],
        }),
    );
    const storage = await getPlatformProxy<Env>({ configPath, persist: { path: join(directory, 'state') } });
    let terminations = 0;
    let stopped = 0;
    let state = 'running';
    const native = Bun.serve({
        fetch() {
            stopped++;
            return new Response(null, { status: 204 });
        },
        hostname: '127.0.0.1',
        port: 0,
    });
    const env = Object.assign(storage.env, {
        ANALYSIS: {
            async get() {
                return {
                    async status() {
                        return { status: state };
                    },
                    async terminate() {
                        terminations++;
                        if (terminations === 1) {
                            throw new Error('Transient termination failure');
                        }
                        state = 'terminated';
                    },
                };
            },
        },
        ENGINE_LOCAL_URL: native.url.origin,
    });
    try {
        for (const path of ['migrations/0001_initial.sql', 'migrations/0002_cleanup_capacity.sql']) {
            for (const sql of (await Bun.file(path).text())
                .split(';')
                .map((sql) => sql.trim())
                .filter(Boolean)) {
                await env.DB.prepare(sql).run();
            }
        }
        await env.DB.prepare(
            "INSERT INTO user(id,name,email,email_verified,created_at,updated_at) VALUES('reader','Reader','reader@example.com',0,0,0)",
        ).run();
        const id = crypto.randomUUID();
        await env.DB.prepare(
            "INSERT INTO job(id,user_id,filename,size,status,params,created_at,expires_at,workflow_expected) VALUES(?,'reader','test.pdf',10,'running','{}',?,?,1)",
        )
            .bind(id, Date.now(), Date.now() + 60000)
            .run();
        const source = `jobs/${id}/source.pdf`;
        await env.FILES.put(source, 'opaque source bytes');
        const row = () => env.DB.prepare('SELECT * FROM job WHERE id=?').bind(id).first<JobRow>();
        await expect(expireJob(env, (await row())!)).rejects.toThrow('Transient termination failure');
        expect((await row())?.status).toBe('expired');
        expect((await row())?.capacity_held).toBe(1);
        expect((await env.DB.prepare('SELECT cleaned_at FROM job WHERE id=?').bind(id).first())?.cleaned_at).toBeNull();
        expect(await env.FILES.head(source)).not.toBeNull();
        expect(stopped).toBe(0);
        const blocked = await createJob(
            new Request('http://localhost/api/jobs', {
                body: JSON.stringify({ filename: 'next.pdf', size: 10 }),
                method: 'POST',
            }),
            env,
            'reader',
        ).catch((error) => error);
        expect(blocked.status).toBe(429);
        await expireJob(env, (await row())!);
        expect(terminations).toBe(2);
        expect(stopped).toBe(1);
        expect(await env.FILES.head(source)).toBeNull();
        expect((await row())?.capacity_held).toBe(0);
        expect(
            (await env.DB.prepare('SELECT cleaned_at FROM job WHERE id=?').bind(id).first())?.cleaned_at,
        ).toBeNumber();
        const next = await createJob(
            new Request('http://localhost/api/jobs', {
                body: JSON.stringify({ filename: 'next.pdf', size: 10 }),
                method: 'POST',
            }),
            env,
            'reader',
        );
        expect(next.status).toBe(201);
        const nextId = (await next.json<{ id: string }>()).id;
        await env.DB.prepare("UPDATE job SET status='running', workflow_expected=1 WHERE id=?").bind(nextId).run();
        const nextSource = `jobs/${nextId}/source.pdf`;
        await env.FILES.put(nextSource, 'opaque source bytes');
        const reachedDestroy = Promise.withResolvers<void>();
        const destroyed = Promise.withResolvers<void>();
        let destructions = 0;
        const production = Object.assign({}, env, {
            ENGINE: {
                getByName() {
                    return {
                        destroy() {
                            if (++destructions === 1) {
                                return Promise.reject(new Error('Transient destruction failure'));
                            }
                            reachedDestroy.resolve();
                            return destroyed.promise;
                        },
                        async stop() {
                            /* A signal can finish before teardown, as in the pinned SDK. */
                        },
                    };
                },
            },
            ENGINE_LOCAL_URL: undefined,
        });
        await expect(
            expireJob(production, (await env.DB.prepare('SELECT * FROM job WHERE id=?').bind(nextId).first<JobRow>())!),
        ).rejects.toThrow('Transient destruction failure');
        expect(
            (await env.DB.prepare('SELECT capacity_held FROM job WHERE id=?').bind(nextId).first())?.capacity_held,
        ).toBe(1);
        expect(await env.FILES.head(nextSource)).not.toBeNull();
        const shutdown = expireJob(
            production,
            (await env.DB.prepare('SELECT * FROM job WHERE id=?').bind(nextId).first<JobRow>())!,
        );
        try {
            await Promise.race([
                reachedDestroy.promise,
                shutdown.then(() => {
                    throw new Error('Cleanup finished before container destruction.');
                }),
            ]);
            expect(
                (await env.DB.prepare('SELECT capacity_held FROM job WHERE id=?').bind(nextId).first())?.capacity_held,
            ).toBe(1);
            expect(await env.FILES.head(nextSource)).not.toBeNull();
            destroyed.resolve();
            await shutdown;
            expect(
                (await env.DB.prepare('SELECT capacity_held FROM job WHERE id=?').bind(nextId).first())?.capacity_held,
            ).toBe(0);
            expect(await env.FILES.head(nextSource)).toBeNull();
        } finally {
            destroyed.resolve();
            await shutdown.catch(() => undefined);
        }
    } finally {
        native.stop(true);
        await storage.dispose();
        rmSync(directory, { force: true, recursive: true });
    }
});
