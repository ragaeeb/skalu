import { stopEngine } from './engine';
import { ensureWorkflow, type JobRow } from './jobs';

const terminal = (status: string) => ['complete', 'errored', 'terminated'].includes(status);

const terminateWorkflow = async (env: Env, row: JobRow) => {
    if (!row.workflow_expected) {
        return;
    }
    let instance: WorkflowInstance;
    try {
        instance = await env.ANALYSIS.get(row.id);
    } catch (error) {
        if (error instanceof Error && error.message.includes('instance.not_found')) {
            return;
        }
        throw error;
    }
    if (terminal((await instance.status()).status)) {
        return;
    }
    await instance.terminate();
    if (!terminal((await instance.status()).status)) {
        throw new Error('Workflow termination is still pending.');
    }
};

const releaseProcessing = async (env: Env, row: JobRow) => {
    await terminateWorkflow(env, row);
    if (row.workflow_expected) {
        await stopEngine(env, row.id);
    }
};

export const expireJob = async (env: Env, row: JobRow) => {
    await env.DB.prepare("UPDATE job SET status='expired', expires_at=? WHERE id=? AND status!='expired'")
        .bind(Date.now(), row.id)
        .run();
    // The persisted expectation survives the tombstone and retries. Capacity remains held until shutdown succeeds.
    await releaseProcessing(env, row);
    if (row.upload_id && !(await env.FILES.head(`jobs/${row.id}/source.pdf`))) {
        try {
            await env.FILES.resumeMultipartUpload(`jobs/${row.id}/source.pdf`, row.upload_id).abort();
        } catch {
            /* Completed/aborted uploads can be absent; the R2 lifecycle backstops abandoned parts. */
        }
    }
    let cursor: string | undefined;
    do {
        const objects = await env.FILES.list({ cursor, limit: 500, prefix: `jobs/${row.id}/` });
        if (objects.objects.length) {
            await env.FILES.delete(objects.objects.map((object) => object.key));
        }
        cursor = objects.truncated ? objects.cursor : undefined;
    } while (cursor);
    await env.DB.batch([
        env.DB.prepare('DELETE FROM page WHERE job_id=?').bind(row.id),
        env.DB.prepare('DELETE FROM upload_part WHERE job_id=?').bind(row.id),
        env.DB.prepare('UPDATE job SET cleaned_at=?, capacity_held=0 WHERE id=?').bind(Date.now(), row.id),
    ]);
};

const reconcileJob = async (env: Env, row: JobRow) => {
    if (row.expires_at <= Date.now()) {
        await expireJob(env, row);
        return;
    }
    if (row.status === 'queued') {
        await ensureWorkflow(env, row.id);
        return;
    }
    if (row.status === 'failed') {
        await releaseProcessing(env, row);
        await env.DB.prepare("UPDATE job SET capacity_held=0 WHERE id=? AND status='failed'").bind(row.id).run();
        return;
    }
    if (row.status === 'running' && terminal((await (await env.ANALYSIS.get(row.id)).status()).status)) {
        await releaseProcessing(env, row);
        await env.DB.prepare(
            "UPDATE job SET status='failed',capacity_held=0,error='Workflow interrupted; please submit the PDF again.',expires_at=? WHERE id=? AND status='running'",
        )
            .bind(Date.now() + 86400000, row.id)
            .run();
    }
};

export const reconcile = async (env: Env) => {
    const rows = (
        await env.DB.prepare(
            "SELECT * FROM job WHERE status IN ('queued','running') OR (status='failed' AND capacity_held=1) OR (expires_at <= ? AND (cleaned_at IS NULL OR cleaned_at < ?)) ORDER BY expires_at LIMIT 20",
        )
            .bind(Date.now(), Date.now() - 86400000)
            .all<JobRow>()
    ).results;
    for (const row of rows) {
        try {
            await reconcileJob(env, row);
        } catch (error) {
            console.error(JSON.stringify({ event: 'reconcile_failed', job: row.id, message: String(error) }));
        }
    }
    await env.DB.prepare('DELETE FROM rate_limit WHERE last_request < ?')
        .bind(Date.now() - 86400000)
        .run();
    await env.DB.prepare(
        "DELETE FROM job WHERE status='expired' AND capacity_held=0 AND cleaned_at IS NOT NULL AND expires_at < ?",
    )
        .bind(Date.now() - 7 * 86400000)
        .run();
};
