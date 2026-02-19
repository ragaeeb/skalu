type ProgressState = {
  status: "idle" | "running" | "finished" | "error"
  processed: number
  total: number
  message: string
  filename: string | null
}

type JobProgressProps = {
  progress: ProgressState
}

export const formatProgress = (progress: ProgressState): string => {
  const fileLabel = progress.filename ? ` (${progress.filename})` : ""
  if (progress.status === "idle") {
    return `${progress.message}${fileLabel}`
  }
  return `${progress.status} - ${progress.processed}/${progress.total || 0} - ${progress.message}${fileLabel}`
}

export const JobProgress = ({ progress }: JobProgressProps) => {
  const ratio = progress.total ? Math.min(100, Math.round((progress.processed / progress.total) * 100)) : 0

  return (
    <div className="panel" data-testid="job-progress">
      <h3 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "1.125rem", fontWeight: 600, color: "#1e293b" }}>Progress</h3>
      <p style={{ marginTop: 0, marginBottom: "0.75rem", color: "#475569", fontSize: "0.9375rem" }}>{formatProgress(progress)}</p>
      <div style={{ width: "100%", height: 10, borderRadius: 999, background: "#e2e8f0", overflow: "hidden" }}>
        <div style={{ width: `${ratio}%`, height: "100%", background: "#0f766e", transition: "width 0.25s ease" }} />
      </div>
    </div>
  )
}
