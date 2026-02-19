import { useEffect, useMemo, useRef, useState } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { downloadUrl, fetchResults } from "@/lib/api"
import type { DetectionParams, ResultsResponse } from "@/types"

type ResultsPanelProps = {
  jobId: string | null
  ready: boolean
  defaultWithViz: boolean
}

type PageData = {
  page: number
  width: number
  height: number
  horizontal_lines?: Array<Record<string, unknown>>
  rectangles?: Array<Record<string, unknown>>
}

type ParsedResult = {
  dpi?: number
  detection_params?: DetectionParams
  pages: PageData[]
}

const parseResultJson = (jsonString: string): ParsedResult => {
  try {
    return JSON.parse(jsonString)
  } catch {
    return { pages: [] }
  }
}

const DetectionParamsPanel = ({ params }: { params: DetectionParams | undefined }) => {
  if (!params) return null

  return (
    <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "1rem", marginBottom: "1.5rem" }}>
      <h3 style={{ margin: "0 0 0.75rem", fontSize: "1rem", fontWeight: 600, color: "#1e293b" }}>Detection Parameters</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem" }}>
        <div>
          <span style={{ color: "#64748b", fontSize: "0.8125rem" }}>Min Line Width Ratio: </span>
          <code style={{ color: "#0f766e", fontWeight: 500 }}>{params.min_line_width_ratio}</code>
        </div>
        <div>
          <span style={{ color: "#64748b", fontSize: "0.8125rem" }}>Max Line Height: </span>
          <code style={{ color: "#0f766e", fontWeight: 500 }}>{params.max_line_height}</code>
        </div>
        <div>
          <span style={{ color: "#64748b", fontSize: "0.8125rem" }}>Min Rect Area Ratio: </span>
          <code style={{ color: "#0f766e", fontWeight: 500 }}>{params.min_rect_area_ratio}</code>
        </div>
        <div>
          <span style={{ color: "#64748b", fontSize: "0.8125rem" }}>Max Rect Area Ratio: </span>
          <code style={{ color: "#0f766e", fontWeight: 500 }}>{params.max_rect_area_ratio}</code>
        </div>
      </div>
    </div>
  )
}

const PageRow = ({
  pageData,
  imageUrl,
  pageNumber,
}: {
  pageData: PageData | undefined
  imageUrl: string | undefined
  pageNumber: number
}) => {
  const [imageError, setImageError] = useState(false)

  const hasStructures = Boolean((pageData?.horizontal_lines?.length ?? 0) > 0 || (pageData?.rectangles?.length ?? 0) > 0)

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: "1.5rem",
        padding: "1.5rem 0",
        borderBottom: "1px solid #e2e8f0",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column" }}>
        <h4 style={{ margin: "0 0 0.75rem", fontSize: "0.9375rem", fontWeight: 600, color: "#1e293b" }}>Page {pageNumber}</h4>
        <div
          style={{
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            overflow: "hidden",
            background: "#f8fafc",
            minHeight: 300,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {imageUrl && !imageError ? (
            <img
              src={imageUrl}
              alt={`Page ${pageNumber}`}
              style={{ maxWidth: "100%", height: "auto", display: "block" }}
              onError={() => setImageError(true)}
            />
          ) : (
            <span style={{ color: "#94a3b8", padding: "2rem" }}>Image not available</span>
          )}
        </div>
        {pageData ? (
          <p style={{ margin: "0.5rem 0 0", fontSize: "0.8125rem", color: "#64748b" }}>
            {pageData.width} × {pageData.height}px
            {pageData.horizontal_lines ? ` • ${pageData.horizontal_lines.length} lines` : ""}
            {pageData.rectangles ? ` • ${pageData.rectangles.length} rectangles` : ""}
          </p>
        ) : null}
      </div>

      <div style={{ display: "flex", flexDirection: "column" }}>
        <h4 style={{ margin: "0 0 0.75rem", fontSize: "0.9375rem", fontWeight: 600, color: "#1e293b" }}>Extracted Data</h4>
        <div style={{ background: "#1e293b", borderRadius: 8, padding: "1rem", overflow: "auto", maxHeight: 400, flex: 1 }}>
          {hasStructures ? (
            <pre
              style={{
                margin: 0,
                fontSize: "0.75rem",
                color: "#e2e8f0",
                fontFamily: "'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {JSON.stringify(pageData, null, 2)}
            </pre>
          ) : (
            <span style={{ color: "#94a3b8" }}>No structures detected</span>
          )}
        </div>
      </div>
    </div>
  )
}

export const ResultsPanel = ({ jobId, ready, defaultWithViz }: ResultsPanelProps) => {
  const [results, setResults] = useState<ResultsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [withViz, setWithViz] = useState(defaultWithViz)
  const parentRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setWithViz(defaultWithViz)
  }, [defaultWithViz])

  useEffect(() => {
    if (!ready || !jobId) {
      return
    }

    const run = async (): Promise<void> => {
      try {
        setError(null)
        const data = await fetchResults(jobId, withViz)
        setResults(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load results")
      }
    }

    void run()
  }, [ready, jobId, withViz])

  const parsedResult = useMemo(() => {
    if (!results?.result_json) return null
    return parseResultJson(results.result_json)
  }, [results])

  const sortedPages = useMemo(() => {
    if (!parsedResult?.pages) return []
    const visualizations = results?.visualizations
    return parsedResult.pages.map((page, index) => ({
      pageData: page,
      imageUrl: visualizations?.[index]?.data_url,
      pageNumber: page.page,
    }))
  }, [parsedResult, results])

  const rowVirtualizer = useVirtualizer({
    count: sortedPages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 820,
    overscan: 3,
  })

  if (!jobId) {
    return null
  }

  return (
    <div className="panel" data-testid="results-panel">
      <div style={{ marginBottom: "1rem" }}>
        <label style={{ display: "inline-flex", gap: "0.4rem", alignItems: "center", color: "#475569", cursor: "pointer" }}>
          <input type="checkbox" checked={withViz} onChange={(event) => setWithViz(event.target.checked)} />
          Include visualizations in response
        </label>
      </div>

      {error ? <p style={{ color: "#dc2626", marginBottom: "1rem" }}>{error}</p> : null}

      {results ? (
        <>
          <DetectionParamsPanel params={parsedResult?.detection_params} />

          <div style={{ marginBottom: "1rem" }}>
            <a href={downloadUrl(jobId)} download={results.download_filename} style={{ color: "#0f766e", textDecoration: "none", fontWeight: 500 }}>
              Download Full JSON
            </a>
          </div>

          {sortedPages.length > 0 ? (
            <div
              ref={parentRef}
              style={{
                height: "75vh",
                overflowY: "auto",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                padding: "0 1rem",
                background: "#ffffff",
              }}
            >
              <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: "relative", width: "100%" }}>
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const item = sortedPages[virtualRow.index]
                  return (
                    <div
                      key={`${item.pageNumber}-${virtualRow.index}`}
                      ref={rowVirtualizer.measureElement}
                      data-index={virtualRow.index}
                      style={{ position: "absolute", top: 0, left: 0, width: "100%", transform: `translateY(${virtualRow.start}px)` }}
                    >
                      <PageRow pageData={item.pageData} imageUrl={item.imageUrl} pageNumber={item.pageNumber} />
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <div style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>
              <p>No page data available. Full result:</p>
              <pre
                style={{
                  textAlign: "left",
                  background: "#f8fafc",
                  padding: "1rem",
                  borderRadius: 6,
                  fontSize: "0.75rem",
                  maxHeight: 300,
                  overflow: "auto",
                }}
              >
                {JSON.stringify(parsedResult, null, 2)}
              </pre>
            </div>
          )}
        </>
      ) : (
        <p style={{ color: "#64748b" }}>Waiting for results...</p>
      )}
    </div>
  )
}
