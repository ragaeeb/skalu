import type { AnalyzePayload, AnalyzeRequestOptions, AnalyzeStreamEvent, VersionResponse } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL ?? ""

type StreamHandlers = {
  onAccepted: (event: Extract<AnalyzeStreamEvent, { type: "accepted" }>) => void
  onProgress: (event: Extract<AnalyzeStreamEvent, { type: "progress" }>) => void
  onHeartbeat?: (event: Extract<AnalyzeStreamEvent, { type: "heartbeat" }>) => void
  onResult: (payload: AnalyzePayload) => void
  onError: (event: Extract<AnalyzeStreamEvent, { type: "error" }>) => void
}

const buildAnalyzeForm = (file: File, options: AnalyzeRequestOptions): FormData => {
  const form = new FormData()
  form.append("file", file)
  form.append("include_empty_pages", options.include_empty_pages ? "true" : "false")
  form.append("include_visualizations", options.include_visualizations ? "true" : "false")
  form.append("stream", options.stream ? "true" : "false")
  form.append("min_line_width_ratio", String(options.detection_params.min_line_width_ratio))
  form.append("max_line_height", String(options.detection_params.max_line_height))
  form.append("min_rect_area_ratio", String(options.detection_params.min_rect_area_ratio))
  form.append("max_rect_area_ratio", String(options.detection_params.max_rect_area_ratio))
  return form
}

export const fetchVersion = async (): Promise<VersionResponse> => {
  const response = await fetch(`${API_BASE}/version`, {
    headers: {
      "X-Frontend-Version": `${__APP_VERSION__}+${__APP_GIT_SHA__}`,
    },
  })
  if (!response.ok) {
    throw new Error("Failed to fetch version")
  }
  return response.json()
}

export const analyzeFile = async (file: File, options: Omit<AnalyzeRequestOptions, "stream">): Promise<AnalyzePayload> => {
  const form = buildAnalyzeForm(file, { ...options, stream: false })
  const response = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? "Analysis failed")
  }
  return response.json()
}

export const analyzeFileStream = async (
  file: File,
  options: Omit<AnalyzeRequestOptions, "stream">,
  handlers: StreamHandlers,
): Promise<void> => {
  const form = buildAnalyzeForm(file, { ...options, stream: true })
  const response = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form })

  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? "Failed to start analysis")
  }

  if (!response.body) {
    throw new Error("Streaming response not available")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let hasResult = false
  let hasError = false

  const processLine = (line: string): void => {
    if (!line.trim()) {
      return
    }

    try {
      const event = JSON.parse(line) as AnalyzeStreamEvent
      if (event.type === "accepted") {
        handlers.onAccepted(event)
        return
      }
      if (event.type === "progress") {
        handlers.onProgress(event)
        return
      }
      if (event.type === "heartbeat") {
        handlers.onHeartbeat?.(event)
        return
      }
      if (event.type === "result") {
        handlers.onResult(event.payload)
        hasResult = true
        return
      }
      if (event.type === "error") {
        handlers.onError(event)
        hasError = true
      }
    } catch {
      // Ignore malformed chunks and continue reading stream.
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    let newLineIndex = buffer.indexOf("\n")
    while (newLineIndex >= 0) {
      const line = buffer.slice(0, newLineIndex)
      processLine(line)
      buffer = buffer.slice(newLineIndex + 1)
      newLineIndex = buffer.indexOf("\n")
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    processLine(buffer)
  }

  if (!hasResult && !hasError) {
    throw new Error("Streaming response ended before terminal result")
  }
}
