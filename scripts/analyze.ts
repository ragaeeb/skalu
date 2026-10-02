import type { Job } from '@skalu/contracts/types';

const base = process.env.SKALU_URL;
const key = process.env.SKALU_KEY;
const filename = process.argv[2];
if (!base || !key || !filename) {
    throw new Error('Set SKALU_URL/SKALU_KEY and pass a PDF filename.');
}
const call = async (path: string, init?: RequestInit) => {
    const headers = new Headers(init?.headers);
    headers.set('authorization', `Bearer ${key}`);
    const response = await fetch(new URL(path, base), { ...init, headers });
    if (!response.ok) {
        throw new Error(await response.text());
    }
    return response;
};
const file = Bun.file(filename);
const { id, part_bytes } = await (
    await call('/api/jobs', {
        body: JSON.stringify({ filename: filename.split('/').pop(), size: file.size }),
        headers: { 'content-type': 'application/json' },
        method: 'POST',
    })
).json<{ id: string; part_bytes: number }>();
try {
    for (let offset = 0, part = 1; offset < file.size; offset += part_bytes, part++) {
        const bytes = file.slice(offset, offset + part_bytes);
        await call(`/api/jobs/${id}/parts/${part}`, {
            body: bytes,
            headers: { 'content-length': String(bytes.size) },
            method: 'PUT',
        });
    }
    await call(`/api/jobs/${id}/start`, { method: 'POST' });
} catch (error) {
    await call(`/api/jobs/${id}`, { method: 'DELETE' }).catch(() => undefined);
    throw error;
}
for (;;) {
    const job = await (await call(`/api/jobs/${id}`)).json<Job>();
    if (job.status === 'failed') {
        throw new Error(job.error ?? 'Analysis failed.');
    }
    if (job.status === 'completed') {
        break;
    }
    await Bun.sleep(2000);
}
await Bun.write('results.json', await call(`/api/jobs/${id}/download`));
console.log('Saved results.json');
