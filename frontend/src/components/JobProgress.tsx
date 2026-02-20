type ProgressState = {
    status: 'idle' | 'running' | 'finished' | 'error';
    processed: number;
    total: number;
    message: string;
    filename: string | null;
};

type JobProgressProps = { progress: ProgressState };

export const formatProgress = (progress: ProgressState): string => {
    const fileLabel = progress.filename ? ` (${progress.filename})` : '';
    if (progress.status === 'idle') {
        return `${progress.message}${fileLabel}`;
    }
    return `${progress.status} - ${progress.processed}/${progress.total || 0} - ${progress.message}${fileLabel}`;
};

export const JobProgress = ({ progress }: JobProgressProps) => {
    const ratio = progress.total ? Math.min(100, Math.round((progress.processed / progress.total) * 100)) : 0;

    return (
        <div className="panel" data-testid="job-progress">
            <h3
                style={{
                    color: '#1e293b',
                    fontSize: '1.125rem',
                    fontWeight: 600,
                    marginBottom: '0.5rem',
                    marginTop: 0,
                }}
            >
                Progress
            </h3>
            <p style={{ color: '#475569', fontSize: '0.9375rem', marginBottom: '0.75rem', marginTop: 0 }}>
                {formatProgress(progress)}
            </p>
            <div style={{ background: '#e2e8f0', borderRadius: 999, height: 10, overflow: 'hidden', width: '100%' }}>
                <div
                    style={{
                        background: '#0f766e',
                        height: '100%',
                        transition: 'width 0.25s ease',
                        width: `${ratio}%`,
                    }}
                />
            </div>
        </div>
    );
};
