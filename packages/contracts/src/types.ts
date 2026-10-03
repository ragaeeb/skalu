export type DetectionParams = {
    min_line_width_ratio: number;
    max_line_height: number;
    min_rect_area_ratio: number;
    max_rect_area_ratio: number;
};
export type DetectionBox = { x: number; y: number; width: number; height: number };
export type PageResult = {
    page: number;
    width: number;
    height: number;
    horizontal_lines?: DetectionBox[];
    rectangles?: DetectionBox[];
    processing_warning?: string;
};
export type JobStatus = 'uploading' | 'queued' | 'running' | 'completed' | 'failed' | 'expired';
export type Job = {
    id: string;
    filename: string;
    status: JobStatus;
    total: number;
    processed: number;
    error: string | null;
    created_at: number;
    expires_at: number;
};
export type PageReceipt = { page: number; image_url: string; result_url: string };
export type JobDetail = Job & { pages: PageReceipt[] };
export type AnalysisResult = {
    api_version: 2;
    engine_version: string;
    processed_filename: string;
    detection_params: DetectionParams;
    result_data: { pages: PageResult[]; dpi: { x: number; y: number } };
};
