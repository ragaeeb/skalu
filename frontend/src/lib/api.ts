import type { ProcessOptions, ResultsResponse } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL ?? ""

export const uploadFile = async (file: File): Promise<{ job_id: string; status: string }> => {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? "Upload failed")
  }
  return res.json()
}

export const startProcessing = async (jobId: string, options: ProcessOptions): Promise<void> => {
  const res = await fetch(`${API_BASE}/process/${jobId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(options),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? "Failed to start processing")
  }
}

export const fetchResults = async (jobId: string, withViz = false): Promise<ResultsResponse> => {
  const suffix = withViz ? "?viz=true" : ""
  const res = await fetch(`${API_BASE}/results/${jobId}${suffix}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? "Failed to fetch results")
  }
  return res.json()
}

export const downloadUrl = (jobId: string): string => `${API_BASE}/download/${jobId}`
