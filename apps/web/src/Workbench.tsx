import { DEFAULT_PARAMS } from '@skalu/contracts/limits';
import type { DetectionParams, Job, JobDetail } from '@skalu/contracts/types';
import { useEffect, useState } from 'react';
import { ApiKey } from './ApiKey';
import { api, upload } from './client';

export const Workbench = () => {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [selected, setSelected] = useState<string | null>(() => new URLSearchParams(location.search).get('job'));
    const [job, setJob] = useState<JobDetail | null>(null);
    const [file, setFile] = useState<File | null>(null);
    const [params, setParams] = useState<DetectionParams>(DEFAULT_PARAMS);
    const [uploading, setUploading] = useState(false);
    const [percent, setPercent] = useState(0);
    const [error, setError] = useState('');
    useEffect(() => {
        const controller = new AbortController();
        let timer: ReturnType<typeof setTimeout>;
        const poll = async () => {
            try {
                const list = await api<{ jobs: Job[] }>('/api/jobs', { signal: controller.signal });
                setJobs(list.jobs);
                if (selected) {
                    setJob(await api<JobDetail>(`/api/jobs/${selected}`, { signal: controller.signal }));
                }
            } catch (error) {
                if (!controller.signal.aborted) {
                    setError(String(error));
                }
            }
            if (!controller.signal.aborted) {
                timer = setTimeout(() => void poll(), 2000);
            }
        };
        void poll();
        return () => {
            controller.abort();
            clearTimeout(timer);
        };
    }, [selected]);
    const select = (id: string) => {
        setSelected(id);
        setJob(null);
        history.replaceState({}, '', `?job=${id}`);
    };
    const analyze = async () => {
        if (!file) {
            return;
        }
        setUploading(true);
        setError('');
        setPercent(0);
        try {
            select(await upload(file, params, setPercent));
        } catch (error) {
            setError(String(error));
        } finally {
            setUploading(false);
        }
    };
    const cancel = async () => {
        if (!job) {
            return;
        }
        try {
            await api(`/api/jobs/${job.id}`, { method: 'DELETE' });
            setSelected(null);
            setJob(null);
            history.replaceState({}, '', '/');
        } catch (error) {
            setError(String(error));
        }
    };
    const labels: Record<keyof DetectionParams, string> = {
        max_line_height: 'Maximum line height (pixels)',
        max_rect_area_ratio: 'Maximum rectangle area ratio',
        min_line_width_ratio: 'Minimum line width ratio',
        min_rect_area_ratio: 'Minimum rectangle area ratio',
    };
    return (
        <main className="workbench">
            <aside>
                <p className="eyebrow">PDF STRUCTURE EXTRACTION</p>
                <h1>Your workbench.</h1>
                <p>Drop a document. Watch the lines emerge.</p>
                <label
                    className="drop-zone"
                    htmlFor="pdf-file"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                        event.preventDefault();
                        if (!uploading) {
                            setFile(event.dataTransfer.files[0] ?? null);
                        }
                    }}
                >
                    <span aria-hidden="true">↥</span>
                    <strong>{file?.name ?? 'Drag a PDF here'}</strong>
                    <small>or choose a file · up to 256 MiB</small>
                    <input
                        id="pdf-file"
                        type="file"
                        accept="application/pdf,.pdf"
                        disabled={uploading}
                        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                    />
                </label>
                <details>
                    <summary>Detection settings</summary>
                    {(Object.keys(labels) as (keyof DetectionParams)[]).map((key) => (
                        <label key={key}>
                            {labels[key]}
                            <input
                                type="number"
                                value={params[key]}
                                min={key === 'max_line_height' ? 1 : 0}
                                max={key === 'max_line_height' ? 100 : 1}
                                step={key === 'max_line_height' ? 1 : 0.001}
                                onChange={(event) => setParams({ ...params, [key]: Number(event.target.value) })}
                            />
                        </label>
                    ))}
                </details>
                <button type="button" disabled={!file || uploading} onClick={() => void analyze()}>
                    {uploading ? `Uploading ${percent}%` : 'Analyze PDF'}
                </button>
                {error && <p role="alert">{error}</p>}
                <ApiKey />
                <h2>Recent documents</h2>
                <ul className="job-list">
                    {jobs.map((item) => (
                        <li key={item.id}>
                            <button
                                type="button"
                                className="secondary"
                                aria-pressed={selected === item.id}
                                onClick={() => select(item.id)}
                            >
                                {item.filename}
                                <small>
                                    {item.status} · {item.processed}/{item.total || '…'} pages
                                </small>
                            </button>
                        </li>
                    ))}
                </ul>
            </aside>
            <section className="results" aria-label="Analysis results">
                {job ? (
                    <>
                        <div className="result-heading">
                            <div>
                                <p className="eyebrow">{job.status}</p>
                                <h2>{job.filename}</h2>
                            </div>
                            <button type="button" className="secondary" onClick={() => void cancel()}>
                                {['queued', 'running', 'uploading'].includes(job.status)
                                    ? 'Cancel job'
                                    : 'Delete document'}
                            </button>
                        </div>
                        <p role="status">
                            {job.processed} of {job.total || '…'} pages processed
                            {job.status === 'completed' ? ' — Complete' : ''}
                        </p>
                        {job.total > 0 && (
                            <progress max={job.total} value={job.processed} aria-label="Page processing progress" />
                        )}
                        {job.error && <p role="alert">{job.error}</p>}
                        {job.status === 'completed' && (
                            <a className="button" href={`/api/jobs/${job.id}/download`} download>
                                Download JSON
                            </a>
                        )}
                        <div className="page-images">
                            {job.pages.map((page) => (
                                <figure key={page.page}>
                                    <figcaption>
                                        PAGE {page.page}{' '}
                                        <a href={page.result_url} target="_blank" rel="noreferrer">
                                            Page JSON ↗
                                        </a>
                                    </figcaption>
                                    <img
                                        src={page.image_url}
                                        alt={`Detected lines and rectangles on page ${page.page}`}
                                        loading="lazy"
                                    />
                                </figure>
                            ))}
                        </div>
                    </>
                ) : (
                    <div className="empty">
                        <span aria-hidden="true">≡</span>
                        <h2>A clearer view of every page.</h2>
                        <p>
                            Detected lines appear in green, rectangles in blue.
                            <br />
                            Your results and images stay private to your account.
                        </p>
                    </div>
                )}
            </section>
        </main>
    );
};
