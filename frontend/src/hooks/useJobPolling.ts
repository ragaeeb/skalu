import { useEffect, useRef, useState } from "react"
import type { ProgressResponse } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL ?? ""

export const useJobPolling = (
  jobId: string | null,
  enabled: boolean,
  restartKey: number
): ProgressResponse | null => {
  const [status, setStatus] = useState<ProgressResponse | null>(null)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    setStatus(null)
  }, [jobId])

  useEffect(() => {
    if (!jobId || !enabled) {
      if (sourceRef.current) {
        sourceRef.current.close()
        sourceRef.current = null
      }
      return
    }

    const source = new EventSource(`${API_BASE}/events/${jobId}`)
    sourceRef.current = source

    source.onmessage = (event) => {
      if (!event.data) return
      try {
        const payload = JSON.parse(event.data) as ProgressResponse
        setStatus(payload)
        if (payload.status === "finished" || payload.status === "error") {
          source.close()
          sourceRef.current = null
        }
      } catch {
        // Ignore malformed stream events and keep the connection open.
      }
    }

    source.onerror = () => {
      // Browser will automatically reconnect unless closed explicitly.
    }

    return () => {
      if (sourceRef.current) {
        sourceRef.current.close()
        sourceRef.current = null
      }
    }
  }, [jobId, enabled, restartKey])

  return status
}
