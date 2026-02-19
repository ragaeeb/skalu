export type JobStatus = "uploaded" | "queued" | "processing" | "finished" | "error"

export type ProgressResponse = {
  status: JobStatus
  processed: number
  total: number
  message: string
  filename: string
  result_ready: boolean
  error?: string
}

export type DetectionParams = {
  min_line_width_ratio: number
  max_line_height: number
  min_rect_area_ratio: number
  max_rect_area_ratio: number
}

export type ProcessOptions = {
  include_empty_pages: boolean
  save_visualization: boolean
  detection_params: DetectionParams
}

export type SummaryPage = {
  page: number
  lines: number
  rectangles: number
  size: [number, number]
}

export type SummaryItem = {
  name: string
  lines: number
  rectangles: number
  dimensions: [number, number]
}

export type Summary = {
  type: "pdf" | "image"
  pages?: SummaryPage[]
  items?: SummaryItem[]
}

export type ResultsResponse = {
  result_json: string
  summary: Summary | null
  processed_filename: string
  detection_params: DetectionParams
  download_filename: string
  visualizations: Array<{ label: string; data_url: string }>
  debug_groups: Array<{
    title: string
    images: Array<{ name: string; data_url: string }>
  }>
}
