import { existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { type APIRequestContext, expect, test } from '@playwright/test';
import { MAX_UPLOAD_BYTES, PART_BYTES } from '@skalu/contracts/limits';
import type { AnalysisResult, JobDetail } from '@skalu/contracts/types';
import { getPlatformProxy } from 'wrangler';

const origin = process.env.SKALU_E2E_ORIGIN ?? 'http://localhost:8787';
const signup = async (client: APIRequestContext) => {
    const email = `e2e-${crypto.randomUUID()}@example.com`;
    await expect
        .poll(
            async () => {
                const response = await client.post('/api/auth/sign-up/email', {
                    data: { email, name: 'E2E Reader', password: 'Only-a-test-password-2026' },
                    headers: { origin },
                });
                if (response.status() !== 429) {
                    expect(response.status(), await response.text()).toBe(200);
                }
                return response.status();
            },
            { intervals: [1000, 11000], timeout: 30000 },
        )
        .toBe(200);
};

test('should enforce ownership and key rotation while processing a real PDF durably', async ({
    request,
    playwright,
}) => {
    await signup(request);
    const keyResponse = await request.post('/api/key', { headers: { origin } });
    expect(keyResponse.ok(), await keyResponse.text()).toBeTruthy();
    const { key } = await keyResponse.json();
    const anonymous = await playwright.request.newContext({ baseURL: origin });
    const other = await playwright.request.newContext({ baseURL: origin });
    const bearer = { authorization: `Bearer ${key}` };
    let id: string | undefined;
    try {
        expect((await anonymous.post('/api/key/rotate', { headers: bearer })).status()).toBe(401);
        expect(
            (await request.post('/api/key/rotate', { headers: { origin: 'https://attacker.example' } })).status(),
        ).toBe(403);
        expect(
            (
                await anonymous.post('/api/jobs', {
                    data: { filename: 'huge.pdf', size: MAX_UPLOAD_BYTES + 1 },
                    headers: bearer,
                })
            ).status(),
        ).toBe(413);
        const pdf = readFileSync('e2e/lines.pdf');
        const created = await anonymous.post('/api/jobs', {
            data: { filename: 'lines.pdf', size: pdf.length },
            headers: bearer,
        });
        expect(created.status(), await created.text()).toBe(201);
        id = (await created.json()).id;
        expect((await anonymous.post(`/api/jobs/${id}/start`, { headers: bearer })).status()).toBe(409);
        expect((await anonymous.put(`/api/jobs/${id}/parts/1`, { data: pdf, headers: bearer })).status()).toBe(200);
        // Re-upload and re-start are idempotent at the public transport boundary.
        expect((await anonymous.put(`/api/jobs/${id}/parts/1`, { data: pdf, headers: bearer })).status()).toBe(200);
        expect((await anonymous.post(`/api/jobs/${id}/start`, { headers: bearer })).status()).toBe(202);
        expect((await anonymous.post(`/api/jobs/${id}/start`, { headers: bearer })).status()).toBe(202);
        expect((await anonymous.get(`/api/jobs/${id}/download`, { headers: bearer })).status()).toBe(409);
        let detail: JobDetail | undefined;
        let incremental = false;
        await expect
            .poll(
                async () => {
                    const response = await anonymous.get(`/api/jobs/${id}`, { headers: bearer });
                    expect(response.ok()).toBeTruthy();
                    detail = await response.json();
                    if (detail?.status === 'failed') {
                        throw new Error(detail.error ?? 'Analysis failed');
                    }
                    if (detail && detail.processed > 0 && detail.status === 'running') {
                        incremental = true;
                    }
                    return detail?.status;
                },
                { intervals: [200, 300, 500], timeout: 90000 },
            )
            .toBe('completed');
        expect(incremental).toBe(true);
        expect(detail?.processed).toBe(12);
        const image = await anonymous.get(`/api/jobs/${id}/pages/1/image`, { headers: bearer });
        expect(image.headers()['content-type']).toBe('image/jpeg');
        expect((await image.body()).subarray(0, 2)).toEqual(Buffer.from([0xff, 0xd8]));
        const download = await anonymous.get(`/api/jobs/${id}/download`, { headers: bearer });
        expect(download.headers()['content-disposition']).toContain('attachment;');
        const result: AnalysisResult = await download.json();
        expect(result.result_data.pages.map((page) => page.page)).toEqual([...Array(12)].map((_, index) => index + 1));
        const line = result.result_data.pages[0]?.horizontal_lines?.[0];
        expect(line?.x).toBeGreaterThanOrEqual(95);
        expect(line?.x).toBeLessThanOrEqual(105);
        expect(line?.y).toBeGreaterThanOrEqual(295);
        expect(line?.y).toBeLessThanOrEqual(305);
        expect(line?.width).toBeGreaterThan(950);
        expect(result.result_data.pages[1]?.horizontal_lines).toBeUndefined();
        await signup(other);
        for (const suffix of ['', '/download', '/pages/1', '/pages/1/image']) {
            expect((await other.get(`/api/jobs/${id}${suffix}`)).status()).toBe(404);
        }
        expect((await other.delete(`/api/jobs/${id}`, { headers: { origin } })).status()).toBe(404);
        expect((await other.get('/api/jobs')).ok()).toBeTruthy();
        expect((await (await other.get('/api/jobs')).json()).jobs).toEqual([]);
        const rotated = await request.post('/api/key/rotate', { headers: { origin } });
        expect(rotated.ok()).toBeTruthy();
        const newKey = (await rotated.json()).key;
        expect((await anonymous.get('/api/jobs', { headers: bearer })).status()).toBe(401);
        expect((await anonymous.get('/api/jobs', { headers: { authorization: `Bearer ${newKey}` } })).status()).toBe(
            200,
        );
    } finally {
        if (id) {
            await request.delete(`/api/jobs/${id}`, { headers: { origin } });
        }
        await anonymous.dispose();
        await other.dispose();
    }
});

test('should bound multipart uploads, recover admission after cancellation, and report invalid PDFs', async ({
    request,
}) => {
    await signup(request);
    const create = (size: number) =>
        request.post('/api/jobs', { data: { filename: 'parts.pdf', size }, headers: { origin } });
    const first = await create(PART_BYTES + 5);
    expect(first.status()).toBe(201);
    const { id } = await first.json();
    try {
        expect((await create(100)).status()).toBe(429);
        expect(
            (
                await request.put(`/api/jobs/${id}/parts/2`, { data: Buffer.from('wrong-size'), headers: { origin } })
            ).status(),
        ).toBe(413);
        expect((await request.post(`/api/jobs/${id}/start`, { headers: { origin } })).status()).toBe(409);
        await request.delete(`/api/jobs/${id}`, { headers: { origin } });
        expect((await request.get(`/api/jobs/${id}`)).status()).toBe(404);
        const invalid = Buffer.from('%PDF-broken');
        const created = await create(invalid.length);
        expect(created.status()).toBe(201);
        const second = (await created.json()).id;
        try {
            expect(
                (await request.put(`/api/jobs/${second}/parts/1`, { data: invalid, headers: { origin } })).status(),
            ).toBe(200);
            expect((await request.post(`/api/jobs/${second}/start`, { headers: { origin } })).status()).toBe(202);
            await expect
                .poll(async () => (await (await request.get(`/api/jobs/${second}`)).json()).status, { timeout: 15000 })
                .toBe('failed');
            expect((await request.get(`/api/jobs/${second}/download`)).status()).toBe(409);
            if (!process.env.SKALU_E2E_ORIGIN) {
                const storage = await getPlatformProxy<Env>({ configPath: 'wrangler.local.json' });
                try {
                    const source = `jobs/${second}/source.pdf`;
                    expect(await storage.env.FILES.head(source)).not.toBeNull();
                    // Move the real stored deadline into the past; no production clock/test flag is needed.
                    await storage.env.DB.prepare('UPDATE job SET expires_at=? WHERE id=?')
                        .bind(Date.now() - 1, second)
                        .run();
                    expect((await request.get(`/api/jobs/${second}`)).status()).toBe(404);
                    expect((await request.get('/cdn-cgi/local/scheduled')).ok()).toBeTruthy();
                    await expect.poll(() => storage.env.FILES.head(source), { timeout: 15000 }).toBeNull();
                } finally {
                    await storage.dispose();
                }
            }
        } finally {
            await request.delete(`/api/jobs/${second}`, { headers: { origin } });
        }
    } finally {
        await request.delete(`/api/jobs/${id}`, { headers: { origin } });
    }
});

test('should cancel a running native job before releasing capacity and remove its cache and artifacts', async ({
    request,
}) => {
    test.skip(Boolean(process.env.SKALU_E2E_ORIGIN), 'Local native cache assertions require the local engine.');
    await signup(request);
    const headers = { origin };
    const pdf = readFileSync('e2e/cancel.pdf');
    const created = await request.post('/api/jobs', { data: { filename: 'cancel.pdf', size: pdf.length }, headers });
    expect(created.status()).toBe(201);
    const { id } = await created.json();
    const storage = await getPlatformProxy<Env>({ configPath: 'wrangler.local.json' });
    try {
        expect((await request.put(`/api/jobs/${id}/parts/1`, { data: pdf, headers })).status()).toBe(200);
        expect((await request.post(`/api/jobs/${id}/start`, { headers })).status()).toBe(202);
        await expect
            .poll(async () => (await (await request.get(`/api/jobs/${id}`)).json()).processed, {
                intervals: [100],
                timeout: 15000,
            })
            .toBeGreaterThan(0);
        const cache = join(tmpdir(), 'skalu-engine', id);
        expect(existsSync(join(cache, 'source.pdf'))).toBe(true);
        expect((await request.delete(`/api/jobs/${id}`, { headers })).status()).toBe(204);
        expect(existsSync(cache)).toBe(false);
        expect((await request.get(`/api/jobs/${id}`)).status()).toBe(404);
        expect(
            (await storage.env.DB.prepare('SELECT capacity_held FROM job WHERE id=?').bind(id).first())?.capacity_held,
        ).toBe(0);
        expect((await storage.env.FILES.list({ prefix: `jobs/${id}/` })).objects).toHaveLength(0);
        const next = await request.post('/api/jobs', { data: { filename: 'next.pdf', size: pdf.length }, headers });
        expect(next.status()).toBe(201);
        await request.delete(`/api/jobs/${(await next.json()).id}`, { headers });
    } finally {
        await request.delete(`/api/jobs/${id}`, { headers });
        await storage.dispose();
    }
});
