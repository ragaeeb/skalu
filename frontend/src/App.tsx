import { useEffect, useState } from "react"
import { DropZone } from "@/components/DropZone"
import { JobProgress } from "@/components/JobProgress"
import { ResultsPanel } from "@/components/ResultsPanel"
import { analyzeFileStream, fetchVersion } from "@/lib/api"
import type { AnalyzePayload, DetectionParams, VersionResponse } from "@/types"

const DEFAULT_DETECTION_PARAMS: DetectionParams = {
  min_line_width_ratio: 0.2,
  max_line_height: 10,
  min_rect_area_ratio: 0.001,
  max_rect_area_ratio: 0.5,
}

type ProgressState = {
  status: "idle" | "running" | "finished" | "error"
  processed: number
  total: number
  message: string
  filename: string | null
}

const App = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [result, setResult] = useState<AnalyzePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [includeVisualizations, setIncludeVisualizations] = useState(true)
  const [includeEmptyPages, setIncludeEmptyPages] = useState(true)
  const [detectionParams, setDetectionParams] = useState<DetectionParams>(DEFAULT_DETECTION_PARAMS)
  const [versionInfo, setVersionInfo] = useState<VersionResponse | null>(null)
  const [progress, setProgress] = useState<ProgressState>({
    status: "idle",
    processed: 0,
    total: 0,
    message: "Waiting for file",
    filename: null,
  })

  useEffect(() => {
    const loadVersion = async (): Promise<void> => {
      try {
        const info = await fetchVersion()
        setVersionInfo(info)
      } catch {
        setVersionInfo(null)
      }
    }

    void loadVersion()
  }, [])

  const handleFile = async (file: File): Promise<void> => {
    setSelectedFile(file)
    setResult(null)
    setError(null)
    setProgress({
      status: "idle",
      processed: 0,
      total: 0,
      message: "Ready to process",
      filename: file.name,
    })
  }

  const handleProcess = async (): Promise<void> => {
    if (!selectedFile) {
      return
    }

    setIsSubmitting(true)
    setError(null)
    setResult(null)

    try {
      await analyzeFileStream(
        selectedFile,
        {
          include_empty_pages: includeEmptyPages,
          include_visualizations: includeVisualizations,
          detection_params: detectionParams,
        },
        {
          onAccepted: (event) => {
            setProgress({
              status: "running",
              processed: 0,
              total: 0,
              message: "Starting analysis",
              filename: event.filename,
            })
          },
          onProgress: (event) => {
            setProgress((prev) => ({
              ...prev,
              status: "running",
              processed: event.processed,
              total: event.total,
              message: event.message,
            }))
          },
          onResult: (payload) => {
            setResult(payload)
            const pages = payload.summary?.type === "pdf"
              ? payload.summary.pages?.length ?? 0
              : payload.summary?.items?.length ?? 1
            setProgress((prev) => ({
              ...prev,
              status: "finished",
              processed: pages,
              total: pages,
              message: "Analysis complete",
            }))
          },
          onError: (event) => {
            setProgress((prev) => ({
              ...prev,
              status: "error",
              message: event.message,
            }))
            setError(event.message)
          },
        },
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : "Analysis failed"
      setProgress((prev) => ({ ...prev, status: "error", message }))
      setError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const updateParam = (key: keyof DetectionParams, value: number): void => {
    setDetectionParams((previous) => ({ ...previous, [key]: value }))
  }

  return (
    <main className="app-shell">
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: "0 0 0.5rem", fontSize: "2.25rem", fontWeight: 700, color: "#0f172a" }}>Skalu</h1>
        <p style={{ margin: 0, color: "#475569", fontSize: "1.125rem" }}>Single-shot structure extraction for PDFs and images.</p>
      </header>

      <section style={{ marginBottom: "1.5rem" }}>
        <DropZone onFile={handleFile} disabled={isSubmitting} />
      </section>

      <section className="panel" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ margin: "0 0 0.75rem", fontSize: "1.125rem", fontWeight: 600, color: "#1e293b" }}>
          Processing Options
        </h3>
        <p style={{ marginTop: 0, marginBottom: "0.75rem", color: "#334155", fontSize: "0.9rem" }}>
          Selected file: <strong>{selectedFile?.name ?? "None"}</strong>
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
            <input type="checkbox" checked={includeEmptyPages} onChange={(event) => setIncludeEmptyPages(event.target.checked)} />
            Include pages with no detections
          </label>
          <label style={{ display: "inline-flex", gap: "0.4rem", alignItems: "center", color: "#475569", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={includeVisualizations}
              onChange={(event) => setIncludeVisualizations(event.target.checked)}
            />
            Generate visualization images
          </label>
        </div>

        <div style={{ marginTop: "1rem" }}>
          <button className="button" type="button" onClick={() => void handleProcess()} disabled={!selectedFile || isSubmitting}>
            {isSubmitting ? "Processing..." : "Process"}
          </button>
        </div>
      </section>

      {error ? (
        <section style={{ marginBottom: "1.5rem" }}>
          <p role="alert" style={{ color: "#dc2626", margin: 0 }}>
            {error}
          </p>
        </section>
      ) : null}

      <section style={{ marginBottom: "1.5rem" }}>
        <JobProgress progress={progress} />
      </section>

      <section>
        <ResultsPanel result={result} />
      </section>

      <footer style={{ marginTop: "2rem", color: "#64748b", fontSize: "0.8rem" }}>
        Frontend v{__APP_VERSION__} ({__APP_GIT_SHA__})
        {versionInfo ? ` • Backend v${versionInfo.backend_version} (${versionInfo.git_sha})` : ""}
      </footer>
    </main>
  )
}

export default App
