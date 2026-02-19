import { useEffect, useState } from "react"
import { DropZone } from "@/components/DropZone"
import { JobProgress } from "@/components/JobProgress"
import { ResultsPanel } from "@/components/ResultsPanel"
import { useJobPolling } from "@/hooks/useJobPolling"
import { startProcessing, uploadFile } from "@/lib/api"
import type { DetectionParams } from "@/types"

const DEFAULT_DETECTION_PARAMS: DetectionParams = {
  min_line_width_ratio: 0.2,
  max_line_height: 10,
  min_rect_area_ratio: 0.001,
  max_rect_area_ratio: 0.5,
}

const App = () => {
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null)
  const [uploadReady, setUploadReady] = useState(false)
  const [pollingEnabled, setPollingEnabled] = useState(false)
  const [pollRestartKey, setPollRestartKey] = useState(0)
  const [saveVisualization, setSaveVisualization] = useState(true)
  const [includeEmptyPages, setIncludeEmptyPages] = useState(true)
  const [detectionParams, setDetectionParams] = useState<DetectionParams>(DEFAULT_DETECTION_PARAMS)

  const status = useJobPolling(jobId, pollingEnabled, pollRestartKey)
  const canProcess = Boolean(jobId) && uploadReady && !isStarting

  useEffect(() => {
    if (status?.status === "uploaded" || status?.status === "error") {
      setUploadReady(true)
    }
    if (status?.status === "finished" || status?.status === "error") {
      setPollingEnabled(false)
    }
  }, [status?.status])

  const handleFile = async (file: File): Promise<void> => {
    try {
      setIsSubmitting(true)
      setError(null)
      setUploadReady(false)
      setPollingEnabled(false)
      const { job_id } = await uploadFile(file)
      setJobId(job_id)
      setSelectedFilename(file.name)
      setUploadReady(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleProcess = async (): Promise<void> => {
    if (!jobId) {
      return
    }

    try {
      setIsStarting(true)
      setError(null)
      setUploadReady(false)
      await startProcessing(jobId, {
        include_empty_pages: includeEmptyPages,
        save_visualization: saveVisualization,
        detection_params: detectionParams,
      })
      setPollingEnabled(true)
      setPollRestartKey((previous) => previous + 1)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start processing")
      setUploadReady(true)
      setPollingEnabled(false)
    } finally {
      setIsStarting(false)
    }
  }

  const updateParam = (key: keyof DetectionParams, value: number): void => {
    setDetectionParams((previous) => ({ ...previous, [key]: value }))
  }

  return (
    <main className="app-shell">
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: "0 0 0.5rem", fontSize: "2.25rem", fontWeight: 700, color: "#0f172a" }}>Skalu</h1>
        <p style={{ margin: 0, color: "#475569", fontSize: "1.125rem" }}>Structure extraction for PDFs and images.</p>
      </header>
      <section style={{ marginBottom: "1.5rem" }}>
        <DropZone onFile={handleFile} disabled={isSubmitting} />
      </section>
      {jobId ? (
        <section className="panel" style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ margin: "0 0 0.75rem", fontSize: "1.125rem", fontWeight: 600, color: "#1e293b" }}>
            Processing Options
          </h3>
          <p style={{ marginTop: 0, color: "#64748b", fontSize: "0.9rem" }}>
            Upload completes first. Start processing when your settings are ready.
          </p>
          <p style={{ marginTop: 0, marginBottom: "0.75rem", color: "#334155", fontSize: "0.9rem" }}>
            Selected file: <strong>{selectedFilename ?? "None"}</strong>
          </p>
          <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              <span style={{ color: "#334155", fontSize: "0.85rem" }}>
                Min Line Width Ratio: {detectionParams.min_line_width_ratio.toFixed(3)}
              </span>
              <input
                type="range"
                min="0.05"
                max="1"
                step="0.01"
                value={detectionParams.min_line_width_ratio}
                onChange={(event) => updateParam("min_line_width_ratio", Number(event.target.value))}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              <span style={{ color: "#334155", fontSize: "0.85rem" }}>
                Max Line Height: {detectionParams.max_line_height}
              </span>
              <input
                type="range"
                min="1"
                max="50"
                step="1"
                value={detectionParams.max_line_height}
                onChange={(event) => updateParam("max_line_height", Number(event.target.value))}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              <span style={{ color: "#334155", fontSize: "0.85rem" }}>
                Min Rect Area Ratio: {detectionParams.min_rect_area_ratio.toFixed(3)}
              </span>
              <input
                type="range"
                min="0.0005"
                max="0.05"
                step="0.0005"
                value={detectionParams.min_rect_area_ratio}
                onChange={(event) => updateParam("min_rect_area_ratio", Number(event.target.value))}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              <span style={{ color: "#334155", fontSize: "0.85rem" }}>
                Max Rect Area Ratio: {detectionParams.max_rect_area_ratio.toFixed(3)}
              </span>
              <input
                type="range"
                min="0.05"
                max="1"
                step="0.01"
                value={detectionParams.max_rect_area_ratio}
                onChange={(event) => updateParam("max_rect_area_ratio", Number(event.target.value))}
              />
            </label>
          </div>
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <label style={{ display: "inline-flex", gap: "0.4rem", alignItems: "center", color: "#475569", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={includeEmptyPages}
                onChange={(event) => setIncludeEmptyPages(event.target.checked)}
              />
              Include pages with no detections
            </label>
            <label style={{ display: "inline-flex", gap: "0.4rem", alignItems: "center", color: "#475569", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={saveVisualization}
                onChange={(event) => setSaveVisualization(event.target.checked)}
              />
              Generate visualization images
            </label>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button className="button" type="button" onClick={() => void handleProcess()} disabled={!canProcess || isStarting}>
              {isStarting ? "Starting..." : "Process"}
            </button>
          </div>
        </section>
      ) : null}
      {error ? (
        <section style={{ marginBottom: "1.5rem" }}>
          <p role="alert" style={{ color: "#dc2626", margin: 0 }}>{error}</p>
        </section>
      ) : null}
      <section style={{ marginBottom: "1.5rem" }}>
        <JobProgress status={status} />
      </section>
      <section>
        <ResultsPanel
          jobId={jobId}
          ready={Boolean(status?.result_ready)}
          defaultWithViz={saveVisualization}
        />
      </section>
    </main>
  )
}

export default App
