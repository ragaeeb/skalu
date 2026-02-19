import type { ProgressResponse } from "@/types"

type JobProgressProps = {
  status: ProgressResponse | null
}

export const formatProgress = (status: ProgressResponse | null): string => {
  if (!status) {
    return "Waiting for upload"
  }
  if (status.status === "uploaded") {
    return status.message || "File uploaded. Ready to process."
  }
  const total = status.total || 0
  return `${status.status} - ${status.processed}/${total} - ${status.message}`
}

export const JobProgress = ({ status }: JobProgressProps) => {
  const ratio = status && status.total ? Math.min(100, Math.round((status.processed / status.total) * 100)) : 0

  return (
    <div className="panel" data-testid="job-progress">
      <h3 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "1.125rem", fontWeight: 600, color: "#1e293b" }}>Progress</h3>
      <p style={{ marginTop: 0, marginBottom: "0.75rem", color: "#475569", fontSize: "0.9375rem" }}>{formatProgress(status)}</p>
      <div style={{ width: "100%", height: 10, borderRadius: 999, background: "#e2e8f0", overflow: "hidden" }}>
        <div style={{ width: `${ratio}%`, height: "100%", background: "#0f766e", transition: "width 0.25s ease" }} />
      </div>
    </div>
  )
}
