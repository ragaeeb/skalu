import { MAX_UPLOAD_BYTES, PART_BYTES, parseParams } from '@skalu/contracts/limits';
import type { DetectionParams, JobStatus } from '@skalu/contracts/types';

export type JobRow = {
    id: string;
    user_id: string;
    filename: string;
    size: number;
    status: JobStatus;
    upload_id: string | null;
    params: string;
    total: number;
    error: string | null;
    dpi: string | null;
    engine_version: string | null;
    created_at: number;
    expires_at: number;
    processed: number;
    capacity_held: number;
    workflow_expected: number;
};

export const fail: (message: string, status?: number) => never = (message, status = 400) => {
    throw new Response(message, { status });
};
export const json = (value: unknown, status = 200) =>
    Response.json(value, { headers: { 'cache-control': 'private, no-store' }, status });

export const readJson = async (request: Request): Promise<Record<string, unknown>> => {
    if (!request.body) {
        return {};
    }
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
        for (;;) {
            const next = await reader.read();
            if (next.done) {
                break;
            }
            size += next.value.byteLength;
            if (size > 32768) {
                fail('JSON request exceeds 32 KiB.', 413);
            }
            chunks.push(next.value);
        }
        const bytes = new Uint8Array(size);
        if (size === 0) {
            return {};
        }
        let position = 0;
        for (const chunk of chunks) {
            bytes.set(chunk, position);
            position += chunk.length;
        }
        const body = JSON.parse(new TextDecoder().decode(bytes));
        if (!body || typeof body !== 'object' || Array.isArray(body)) {
            fail('Expected a JSON object.');
        }
        return body;
    } catch (error) {
        if (error instanceof Response) {
            throw error;
        }
        return fail('Invalid JSON.');
    } finally {
        await reader.cancel();
        reader.releaseLock();
    }
};

export const ownJob = async (env: Env, id: string, userId: string): Promise<JobRow> => {
    const row = await env.DB.prepare(
        'SELECT job.*, (SELECT count(*) FROM page WHERE job_id = job.id) AS processed FROM job WHERE id = ? AND user_id = ?',
    )
        .bind(id, userId)
        .first<JobRow>();
    if (!row || row.status === 'expired' || row.expires_at <= Date.now()) {
        return fail('Job not found.', 404);
    }
    return row;
};

export const createJob = async (request: Request, env: Env, userId: string) => {
    const data = await readJson(request);
    if (
        typeof data.filename !== 'string' ||
        !/\.pdf$/i.test(data.filename) ||
        data.filename.length > 180 ||
        [...data.filename].some((char) => char.charCodeAt(0) < 32) ||
        /[/\\]/.test(data.filename)
    ) {
        fail('Supply a PDF filename (maximum 180 characters).');
    }
    if (
        typeof data.size !== 'number' ||
        !Number.isInteger(data.size) ||
        data.size < 5 ||
        data.size > MAX_UPLOAD_BYTES
    ) {
        fail('PDF size must be between 5 bytes and 256 MiB.', 413);
    }
    let params: DetectionParams;
    try {
        params = parseParams(data.detection_params);
    } catch (error) {
        return fail(String(error));
    }
    const id = crypto.randomUUID();
    const now = Date.now();
    // One atomic SQLite statement owns admission across concurrent sessions and keys.
    const inserted =
        await env.DB.prepare(`INSERT INTO job (id,user_id,filename,size,status,params,created_at,expires_at)
        SELECT ?,?,?,?,'uploading',?,?,? WHERE
        (SELECT count(*) FROM job WHERE capacity_held=1) < 3 AND
        (SELECT count(*) FROM job WHERE user_id = ? AND capacity_held=1) < 1 AND
        (SELECT count(*) FROM job WHERE user_id = ? AND created_at > ?) < 20`)
            .bind(
                id,
                userId,
                data.filename,
                data.size,
                JSON.stringify(params),
                now,
                now + 3600000,
                userId,
                userId,
                now - 86400000,
            )
            .run();
    if (!inserted.meta.changes) {
        fail('Analysis capacity or daily quota reached. Try again later.', 429);
    }
    try {
        const upload = await env.FILES.createMultipartUpload(`jobs/${id}/source.pdf`, {
            httpMetadata: { contentType: 'application/pdf' },
        });
        await env.DB.prepare('UPDATE job SET upload_id = ? WHERE id = ?').bind(upload.uploadId, id).run();
    } catch (error) {
        await env.DB.prepare(
            "UPDATE job SET status = 'failed', capacity_held=0, error = 'Upload initialization failed' WHERE id = ?",
        )
            .bind(id)
            .run();
        throw error;
    }
    return json({ id, part_bytes: PART_BYTES }, 201);
};

export const uploadPart = async (request: Request, env: Env, row: JobRow, number: number) => {
    if (row.status !== 'uploading' || !row.upload_id) {
        fail('Job is not accepting uploads.', 409);
    }
    const parts = Math.ceil(row.size / PART_BYTES);
    if (!Number.isInteger(number) || number < 1 || number > parts) {
        fail('Invalid upload part.');
    }
    const expected = number === parts ? row.size - (number - 1) * PART_BYTES : PART_BYTES;
    if (request.headers.get('content-length') !== String(expected)) {
        fail('Part Content-Length does not match the declared PDF size.', 413);
    }
    if (!request.body) {
        fail('Missing upload body.');
    }
    const fixed = new FixedLengthStream(expected);
    let position = 0;
    let magic = '';
    const stream = request.body.pipeThrough(
        new TransformStream<Uint8Array, Uint8Array>({
            flush() {
                if (position !== expected) {
                    fail('Upload part is truncated.');
                }
            },
            transform(chunk, controller) {
                position += chunk.byteLength;
                if (position > expected) {
                    fail('Upload part is too large.', 413);
                }
                if (number === 1 && magic.length < 5) {
                    magic += new TextDecoder().decode(chunk.subarray(0, 5 - magic.length));
                    if (magic.length === 5 && magic !== '%PDF-') {
                        fail('Upload must be a PDF.');
                    }
                }
                controller.enqueue(chunk);
            },
        }),
    );
    const aborter = new AbortController();
    const pump = stream.pipeTo(fixed.writable, { signal: aborter.signal });
    const uploading = env.FILES.resumeMultipartUpload(`jobs/${row.id}/source.pdf`, row.upload_id).uploadPart(
        number,
        fixed.readable,
    );
    let part: R2UploadedPart;
    try {
        [part] = await Promise.all([uploading, pump]);
    } catch (error) {
        aborter.abort();
        await pump.catch(() => undefined);
        throw error;
    }
    await env.DB.prepare(
        'INSERT INTO upload_part (job_id,part,etag,size) VALUES (?,?,?,?) ON CONFLICT(job_id,part) DO UPDATE SET etag=excluded.etag,size=excluded.size',
    )
        .bind(row.id, number, part.etag, expected)
        .run();
    return json({ part: number });
};

export const ensureWorkflow = async (env: Env, id: string) => {
    try {
        await env.ANALYSIS.create({ id, params: { id } });
    } catch (error) {
        // A create may have succeeded before its response was lost. Prove existence.
        try {
            await (await env.ANALYSIS.get(id)).status();
        } catch {
            throw error;
        }
    }
};

export const startJob = async (env: Env, row: JobRow) => {
    if (row.status === 'queued' || row.status === 'running' || row.status === 'completed') {
        if (row.status === 'queued') {
            await ensureWorkflow(env, row.id);
        }
        return json({ id: row.id, status: row.status }, 202);
    }
    if (row.status !== 'uploading' || !row.upload_id) {
        fail('Job cannot be started.', 409);
    }
    const parts = (
        await env.DB.prepare('SELECT part AS partNumber, etag, size FROM upload_part WHERE job_id = ? ORDER BY part')
            .bind(row.id)
            .all<{ partNumber: number; etag: string; size: number }>()
    ).results;
    if (
        parts.length !== Math.ceil(row.size / PART_BYTES) ||
        parts.reduce((sum, part) => sum + part.size, 0) !== row.size
    ) {
        fail('Upload every PDF part before starting.', 409);
    }
    if (!(await env.FILES.head(`jobs/${row.id}/source.pdf`))) {
        await env.FILES.resumeMultipartUpload(`jobs/${row.id}/source.pdf`, row.upload_id).complete(parts);
    }
    await env.DB.prepare(
        "UPDATE job SET status='queued', workflow_expected=1, expires_at=? WHERE id=? AND status='uploading'",
    )
        .bind(Date.now() + 7200000, row.id)
        .run();
    await ensureWorkflow(env, row.id);
    return json({ id: row.id, status: 'queued' }, 202);
};

export const jobDetail = async (env: Env, row: JobRow) => {
    const pages = (
        await env.DB.prepare('SELECT page FROM page WHERE job_id = ? ORDER BY page')
            .bind(row.id)
            .all<{ page: number }>()
    ).results;
    return json({
        created_at: row.created_at,
        error: row.error,
        expires_at: row.expires_at,
        filename: row.filename,
        id: row.id,
        pages: pages.map(({ page }) => ({
            image_url: `/api/jobs/${row.id}/pages/${page}/image`,
            page,
            result_url: `/api/jobs/${row.id}/pages/${page}`,
        })),
        processed: pages.length,
        status: row.status,
        total: row.total,
    });
};

export const artifact = async (env: Env, row: JobRow, page: number, image: boolean) => {
    const committed = await env.DB.prepare('SELECT page FROM page WHERE job_id=? AND page=?')
        .bind(row.id, page)
        .first();
    if (!committed) {
        fail('Page not found.', 404);
    }
    const object = await env.FILES.get(`jobs/${row.id}/pages/${page}.${image ? 'jpg' : 'json'}`);
    if (!object) {
        fail('Artifact not found.', 404);
    }
    return new Response(object.body, {
        headers: {
            'cache-control': 'private, no-store',
            'content-type': image ? 'image/jpeg' : 'application/json',
            'x-content-type-options': 'nosniff',
        },
    });
};

export const download = (env: Env, row: JobRow) => {
    if (row.status !== 'completed') {
        fail('Results are available after all pages complete.', 409);
    }
    const encoder = new TextEncoder();
    const generate = async function* () {
        const metadata = {
            api_version: 2,
            detection_params: JSON.parse(row.params),
            engine_version: row.engine_version,
            processed_filename: row.filename,
        };
        yield encoder.encode(`${JSON.stringify(metadata).slice(0, -1)},"result_data":{"dpi":${row.dpi},"pages":[`);
        for (let page = 1; page <= row.total; page++) {
            const result = await env.FILES.get(`jobs/${row.id}/pages/${page}.json`);
            if (!result) {
                throw new Error('Committed page missing');
            }
            if (page > 1) {
                yield encoder.encode(',');
            }
            yield* result.body;
        }
        yield encoder.encode(']}}');
    };
    const iterator = generate();
    const body = new ReadableStream<Uint8Array>({
        async cancel() {
            await iterator.return();
        },
        async pull(controller) {
            try {
                const next = await iterator.next();
                if (next.done) {
                    controller.close();
                } else {
                    controller.enqueue(next.value);
                }
            } catch (error) {
                controller.error(error);
            }
        },
    });
    return new Response(body, {
        headers: {
            'cache-control': 'private, no-store',
            'content-disposition': `attachment; filename="skalu-${row.id}.json"`,
            'content-type': 'application/json',
        },
    });
};
