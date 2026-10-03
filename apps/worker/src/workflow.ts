import { WorkflowEntrypoint, type WorkflowEvent, type WorkflowStep } from 'cloudflare:workers';
import { NonRetryableError } from 'cloudflare:workflows';
import type { PageResult } from '@skalu/contracts/types';
import { engineFetch, loadSource, stopEngine } from './engine';
import type { JobRow } from './jobs';

const STEP = {
    retries: { backoff: 'exponential' as const, delay: '5 seconds', limit: 6 },
    timeout: '3 minutes',
} as const;

const engineResult = async <T>(response: Response): Promise<T> => {
    if (!response.ok) {
        const message = (await response.text()).slice(0, 500);
        if (response.status === 422 || response.status === 413 || response.status === 504) {
            throw new NonRetryableError(message);
        }
        throw new Error(`Engine unavailable: ${response.status}`);
    }
    return response.json<T>();
};

export class AnalysisWorkflow extends WorkflowEntrypoint<Env, { id: string }> {
    private async processPage(id: string, page: number, params: string, engineVersion: string) {
        const row = await this.env.DB.prepare('SELECT status, expires_at FROM job WHERE id=?').bind(id).first<JobRow>();
        if (row?.status !== 'running' || row.expires_at <= Date.now()) {
            throw new NonRetryableError('Job no longer active.');
        }
        const committed = await this.env.DB.prepare('SELECT page FROM page WHERE job_id=? AND page=?')
            .bind(id, page)
            .first();
        if (committed) {
            return;
        }
        const analyze = () =>
            engineFetch(this.env, id, `/jobs/${id}/pages/${page}`, {
                body: params,
                headers: { 'content-type': 'application/json' },
                method: 'POST',
            });
        let response = await analyze();
        if (response.status === 404) {
            await response.body?.cancel();
            await engineResult(await loadSource(this.env, id));
            response = await analyze();
        }
        const result = await engineResult<{
            pages: PageResult[];
            dpi: { x: number; y: number };
            engine_version: string;
            protocol: number;
        }>(response);
        if (result.engine_version !== engineVersion || result.protocol !== 1) {
            throw new NonRetryableError('The engine was updated during processing. Please submit the PDF again.');
        }
        if (result.pages.length !== 1 || result.pages[0]?.page !== page) {
            throw new NonRetryableError('Engine returned an unexpected page.');
        }
        await this.env.FILES.put(`jobs/${id}/pages/${page}.json`, JSON.stringify(result.pages[0]), {
            httpMetadata: { contentType: 'application/json' },
        });
        const image = await engineFetch(this.env, id, `/jobs/${id}/pages/${page}/image`);
        if (!image.ok || !image.body) {
            throw new Error('Visualization missing; retry page.');
        }
        const imageSize = Number(image.headers.get('content-length'));
        if (!Number.isSafeInteger(imageSize) || imageSize < 1 || imageSize > 8 * 1024 * 1024) {
            await image.body.cancel();
            throw new NonRetryableError('Visualization length is missing or exceeds the output limit.');
        }
        // Container RPC loses the stream's known length; R2 requires it even when the header survives.
        const fixed = new FixedLengthStream(imageSize);
        const aborter = new AbortController();
        const pump = image.body.pipeTo(fixed.writable, { signal: aborter.signal });
        try {
            await Promise.all([
                this.env.FILES.put(`jobs/${id}/pages/${page}.jpg`, fixed.readable, {
                    httpMetadata: { contentType: 'image/jpeg' },
                }),
                pump,
            ]);
        } catch (error) {
            aborter.abort();
            await pump.catch(() => undefined);
            throw error;
        }
        // Publish only after both artifacts exist; duplicate retries never increment progress.
        await this.env.DB.batch([
            this.env.DB.prepare(
                "INSERT OR IGNORE INTO page(job_id,page) SELECT ?,? WHERE EXISTS(SELECT 1 FROM job WHERE id=? AND status='running')",
            ).bind(id, page, id),
            this.env.DB.prepare("UPDATE job SET dpi=COALESCE(dpi,?) WHERE id=? AND status='running'").bind(
                JSON.stringify(result.dpi),
                id,
            ),
        ]);
    }

    async run(event: WorkflowEvent<{ id: string }>, step: WorkflowStep) {
        const id = event.payload.id;
        try {
            const meta = await step.do('inspect PDF', STEP, async () => {
                const row = await this.env.DB.prepare('SELECT * FROM job WHERE id=?').bind(id).first<JobRow>();
                if (!row || !['queued', 'running'].includes(row.status)) {
                    throw new NonRetryableError('Job no longer active.');
                }
                const meta = await engineResult<{ total: number; engine_version: string; protocol: number }>(
                    await loadSource(this.env, id),
                );
                if (meta.protocol !== 1 || !Number.isInteger(meta.total) || meta.total < 1 || meta.total > 1000) {
                    throw new NonRetryableError('Engine protocol or page count mismatch.');
                }
                await this.env.DB.prepare(
                    "UPDATE job SET status='running', total=?, engine_version=? WHERE id=? AND status IN ('queued','running')",
                )
                    .bind(meta.total, meta.engine_version, id)
                    .run();
                return { engineVersion: meta.engine_version, params: row.params, total: meta.total };
            });
            for (let page = 1; page <= meta.total; page++) {
                await step.do(`page ${page}`, STEP, () => this.processPage(id, page, meta.params, meta.engineVersion));
            }
            await step.do('release engine cache', STEP, () => this.releaseCache(id));
            await step.do('complete job', async () => {
                await this.env.DB.prepare(
                    "UPDATE job SET status='completed', capacity_held=0, expires_at=? WHERE id=? AND status='running' AND total=(SELECT count(*) FROM page WHERE job_id=?)",
                )
                    .bind(Date.now() + 86400000, id, id)
                    .run();
            });
            return { id };
        } catch (error) {
            await step.do('record failure', async () => {
                await this.env.DB.prepare(
                    "UPDATE job SET status='failed', error=?, expires_at=? WHERE id=? AND status IN ('queued','running')",
                )
                    .bind(
                        error instanceof Error ? error.message.slice(0, 500) : 'Analysis failed.',
                        Date.now() + 86400000,
                        id,
                    )
                    .run();
            });
            await step.do('release failed engine cache', STEP, () => this.releaseCache(id));
            await step.do('release failed capacity', async () => {
                await this.env.DB.prepare("UPDATE job SET capacity_held=0 WHERE id=? AND status='failed'")
                    .bind(id)
                    .run();
            });
            throw error;
        }
    }

    private async releaseCache(id: string) {
        await stopEngine(this.env, id);
        return { released: true };
    }
}
