import { type FormEvent, useEffect, useRef, useState } from 'react';
import { DropZone } from '@/components/DropZone';
import { JobProgress } from '@/components/JobProgress';
import { ResultsPanel } from '@/components/ResultsPanel';
import { analyzeFileStream, fetchVersion } from '@/lib/api';
import type { AnalyzePayload, AnalyzeResultData, DetectionParams, VersionResponse } from '@/types';

const DEFAULT_DETECTION_PARAMS: DetectionParams = {
    min_line_width_ratio: 0.19,
    max_line_height: 10,
    min_rect_area_ratio: 0.001,
    max_rect_area_ratio: 0.5,
};

type ProgressState = {
    status: 'idle' | 'running' | 'finished' | 'error';
    processed: number;
    total: number;
    message: string;
    filename: string | null;
};

type QueryState = DetectionParams & { include_visualizations: boolean; include_empty_pages: boolean; file_url: string };

const DEFAULT_QUERY_STATE: QueryState = {
    ...DEFAULT_DETECTION_PARAMS,
    include_visualizations: true,
    include_empty_pages: true,
    file_url: '',
};

const parseNumberParam = (params: URLSearchParams, key: keyof DetectionParams): number | null => {
    const raw = params.get(key);
    if (raw === null || raw.trim() === '') {
        return null;
    }

    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
};

const parseQueryState = (search: string): QueryState => {
    const params = new URLSearchParams(search);

    const minLineWidthRatio = parseNumberParam(params, 'min_line_width_ratio');
    const maxLineHeight = parseNumberParam(params, 'max_line_height');
    const minRectAreaRatio = parseNumberParam(params, 'min_rect_area_ratio');
    const maxRectAreaRatio = parseNumberParam(params, 'max_rect_area_ratio');
    const includeVisualizationsRaw = params.get('include_visualizations');
    const includeEmptyPagesRaw = params.get('include_empty_pages');

    return {
        min_line_width_ratio: minLineWidthRatio ?? DEFAULT_QUERY_STATE.min_line_width_ratio,
        max_line_height: maxLineHeight ?? DEFAULT_QUERY_STATE.max_line_height,
        min_rect_area_ratio: minRectAreaRatio ?? DEFAULT_QUERY_STATE.min_rect_area_ratio,
        max_rect_area_ratio: maxRectAreaRatio ?? DEFAULT_QUERY_STATE.max_rect_area_ratio,
        include_visualizations:
            includeVisualizationsRaw === null
                ? DEFAULT_QUERY_STATE.include_visualizations
                : ['1', 'true', 'yes', 'on'].includes(includeVisualizationsRaw.toLowerCase()),
        include_empty_pages:
            includeEmptyPagesRaw === null
                ? DEFAULT_QUERY_STATE.include_empty_pages
                : ['1', 'true', 'yes', 'on'].includes(includeEmptyPagesRaw.toLowerCase()),
        file_url: params.get('file_url') ?? '',
    };
};

const writeQueryState = (queryState: QueryState): void => {
    const params = new URLSearchParams();
    params.set('min_line_width_ratio', String(queryState.min_line_width_ratio));
    params.set('max_line_height', String(queryState.max_line_height));
    params.set('min_rect_area_ratio', String(queryState.min_rect_area_ratio));
    params.set('max_rect_area_ratio', String(queryState.max_rect_area_ratio));
    params.set('include_visualizations', queryState.include_visualizations ? 'true' : 'false');
    params.set('include_empty_pages', queryState.include_empty_pages ? 'true' : 'false');
    if (queryState.file_url.trim()) {
        params.set('file_url', queryState.file_url.trim());
    }

    const next = params.toString();
    const target = next ? `${window.location.pathname}?${next}` : window.location.pathname;
    window.history.replaceState({}, '', target);
};

const countResultItems = (resultData: AnalyzeResultData): number => {
    if ('pages' in resultData) {
        return resultData.pages.length;
    }

    return Object.keys(resultData.result).length;
};

const App = () => {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [result, setResult] = useState<AnalyzePayload | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [queryState, setQueryState] = useState<QueryState>(() => parseQueryState(window.location.search));
    const [versionInfo, setVersionInfo] = useState<VersionResponse | null>(null);
    const urlInputRef = useRef<HTMLInputElement | null>(null);
    const [progress, setProgress] = useState<ProgressState>({
        status: 'idle',
        processed: 0,
        total: 0,
        message: 'Waiting for file',
        filename: null,
    });

    useEffect(() => {
        const onPopState = (): void => {
            setQueryState(parseQueryState(window.location.search));
        };

        window.addEventListener('popstate', onPopState);
        return () => {
            window.removeEventListener('popstate', onPopState);
        };
    }, []);

    useEffect(() => {
        if (urlInputRef.current && urlInputRef.current.value !== queryState.file_url) {
            urlInputRef.current.value = queryState.file_url;
        }
    }, [queryState.file_url]);

    useEffect(() => {
        const loadVersion = async (): Promise<void> => {
            try {
                const info = await fetchVersion();
                setVersionInfo(info);
            } catch {
                setVersionInfo(null);
            }
        };

        void loadVersion();
    }, []);

    const handleFile = async (file: File): Promise<void> => {
        setSelectedFile(file);
        setResult(null);
        setError(null);
        setProgress({ status: 'idle', processed: 0, total: 0, message: 'Ready to process', filename: file.name });
    };

    const updateQueryState = (next: QueryState): void => {
        setQueryState(next);
        writeQueryState(next);
    };

    const handleProcess = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
        event.preventDefault();
        const fileUrl = urlInputRef.current?.value.trim() ?? '';
        const usingFileUrl = fileUrl.length > 0;
        if (!usingFileUrl && !selectedFile) {
            return;
        }

        const nextQueryState = { ...queryState, file_url: fileUrl };
        updateQueryState(nextQueryState);

        setIsSubmitting(true);
        setError(null);
        setResult(null);

        try {
            await analyzeFileStream(
                { file: usingFileUrl ? null : selectedFile, file_url: usingFileUrl ? fileUrl : null },
                {
                    include_empty_pages: nextQueryState.include_empty_pages,
                    include_visualizations: nextQueryState.include_visualizations,
                    detection_params: {
                        min_line_width_ratio: nextQueryState.min_line_width_ratio,
                        max_line_height: nextQueryState.max_line_height,
                        min_rect_area_ratio: nextQueryState.min_rect_area_ratio,
                        max_rect_area_ratio: nextQueryState.max_rect_area_ratio,
                    },
                },
                {
                    onAccepted: (event) => {
                        setProgress({
                            status: 'running',
                            processed: 0,
                            total: 0,
                            message: 'Starting analysis',
                            filename: event.filename,
                        });
                    },
                    onProgress: (event) => {
                        setProgress((prev) => ({
                            ...prev,
                            status: 'running',
                            processed: event.processed,
                            total: event.total,
                            message: event.message,
                        }));
                    },
                    onResult: (payload) => {
                        setResult(payload);
                        const pages = countResultItems(payload.result_data);
                        setProgress((prev) => ({
                            ...prev,
                            status: 'finished',
                            processed: pages,
                            total: pages,
                            message: 'Analysis complete',
                        }));
                    },
                    onError: (event) => {
                        setProgress((prev) => ({ ...prev, status: 'error', message: event.message }));
                        setError(event.message);
                    },
                },
            );
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Analysis failed';
            setProgress((prev) => ({ ...prev, status: 'error', message }));
            setError(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    const updateParam = (key: keyof DetectionParams, value: number): void => {
        updateQueryState({ ...queryState, [key]: value });
    };

    return (
        <main className="app-shell">
            <header style={{ marginBottom: '2rem' }}>
                <h1 style={{ margin: '0 0 0.5rem', fontSize: '2.25rem', fontWeight: 700, color: '#0f172a' }}>Skalu</h1>
                <p style={{ margin: 0, color: '#475569', fontSize: '1.125rem' }}>
                    Single-shot structure extraction for PDFs and images.
                </p>
            </header>

            <section style={{ marginBottom: '1.5rem' }}>
                <DropZone onFile={handleFile} disabled={isSubmitting} />
            </section>

            <section className="panel" style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ margin: '0 0 0.75rem', fontSize: '1.125rem', fontWeight: 600, color: '#1e293b' }}>
                    Processing Options
                </h3>
                <p style={{ marginTop: 0, marginBottom: '0.75rem', color: '#334155', fontSize: '0.9rem' }}>
                    Selected file: <strong>{selectedFile?.name ?? 'None'}</strong>
                </p>
                <p style={{ marginTop: 0, marginBottom: '0.75rem', color: '#334155', fontSize: '0.9rem' }}>
                    PDF URL: <strong>{queryState.file_url || 'None'}</strong>
                </p>
                <form onSubmit={(event) => void handleProcess(event)}>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginBottom: '1rem' }}>
                        <span style={{ color: '#334155', fontSize: '0.85rem' }}>
                            PDF URL (if provided, this is used instead of uploaded file)
                        </span>
                        <input
                            ref={urlInputRef}
                            type="url"
                            name="file_url"
                            defaultValue={queryState.file_url}
                            placeholder="https://example.com/document.pdf"
                            onBlur={(event) => updateQueryState({ ...queryState, file_url: event.target.value.trim() })}
                            disabled={isSubmitting}
                            style={{
                                border: '1px solid #cbd5e1',
                                borderRadius: '0.5rem',
                                padding: '0.6rem 0.75rem',
                                fontSize: '0.9rem',
                            }}
                        />
                    </label>

                    <div
                        style={{
                            display: 'grid',
                            gap: '1rem',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                        }}
                    >
                        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <span style={{ color: '#334155', fontSize: '0.85rem' }}>
                                Min Line Width Ratio: {queryState.min_line_width_ratio.toFixed(3)}
                            </span>
                            <input
                                type="range"
                                min="0.05"
                                max="1"
                                step="0.01"
                                value={queryState.min_line_width_ratio}
                                onChange={(event) => updateParam('min_line_width_ratio', Number(event.target.value))}
                            />
                        </label>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <span style={{ color: '#334155', fontSize: '0.85rem' }}>
                                Max Line Height: {queryState.max_line_height}
                            </span>
                            <input
                                type="range"
                                min="1"
                                max="50"
                                step="1"
                                value={queryState.max_line_height}
                                onChange={(event) => updateParam('max_line_height', Number(event.target.value))}
                            />
                        </label>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <span style={{ color: '#334155', fontSize: '0.85rem' }}>
                                Min Rect Area Ratio: {queryState.min_rect_area_ratio.toFixed(3)}
                            </span>
                            <input
                                type="range"
                                min="0.0005"
                                max="0.05"
                                step="0.0005"
                                value={queryState.min_rect_area_ratio}
                                onChange={(event) => updateParam('min_rect_area_ratio', Number(event.target.value))}
                            />
                        </label>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <span style={{ color: '#334155', fontSize: '0.85rem' }}>
                                Max Rect Area Ratio: {queryState.max_rect_area_ratio.toFixed(3)}
                            </span>
                            <input
                                type="range"
                                min="0.05"
                                max="1"
                                step="0.01"
                                value={queryState.max_rect_area_ratio}
                                onChange={(event) => updateParam('max_rect_area_ratio', Number(event.target.value))}
                            />
                        </label>
                    </div>

                    <div style={{ marginTop: '0.75rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                        <label
                            style={{
                                display: 'inline-flex',
                                gap: '0.4rem',
                                alignItems: 'center',
                                color: '#475569',
                                cursor: 'pointer',
                            }}
                        >
                            <input
                                type="checkbox"
                                checked={queryState.include_empty_pages}
                                onChange={(event) =>
                                    updateQueryState({ ...queryState, include_empty_pages: event.target.checked })
                                }
                            />
                            Include pages with no detections
                        </label>
                        <label
                            style={{
                                display: 'inline-flex',
                                gap: '0.4rem',
                                alignItems: 'center',
                                color: '#475569',
                                cursor: 'pointer',
                            }}
                        >
                            <input
                                type="checkbox"
                                checked={queryState.include_visualizations}
                                onChange={(event) =>
                                    updateQueryState({ ...queryState, include_visualizations: event.target.checked })
                                }
                            />
                            Generate visualization images
                        </label>
                    </div>

                    <div style={{ marginTop: '1rem' }}>
                        <button className="button" type="submit" disabled={isSubmitting}>
                            {isSubmitting ? 'Processing...' : 'Process'}
                        </button>
                    </div>
                </form>
            </section>

            {error ? (
                <section style={{ marginBottom: '1.5rem' }}>
                    <p role="alert" style={{ color: '#dc2626', margin: 0 }}>
                        {error}
                    </p>
                </section>
            ) : null}

            <section style={{ marginBottom: '1.5rem' }}>
                <JobProgress progress={progress} />
            </section>

            <section>
                <ResultsPanel result={result} />
            </section>

            <footer style={{ marginTop: '2rem', color: '#64748b', fontSize: '0.8rem' }}>
                Frontend v{__APP_VERSION__} ({__APP_GIT_SHA__})
                {versionInfo ? ` • Backend v${versionInfo.backend_version} (${versionInfo.git_sha})` : ''}
            </footer>
        </main>
    );
};

export default App;
