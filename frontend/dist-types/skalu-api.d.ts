export type DetectionParams = {
    min_line_width_ratio: number;
    max_line_height: number;
    min_rect_area_ratio: number;
    max_rect_area_ratio: number;
};
export type DetectionBox = {
    x: number;
    y: number;
    width: number;
    height: number;
};
export type PdfPageResult = {
    page: number;
    width: number;
    height: number;
    horizontal_lines?: DetectionBox[];
    rectangles?: DetectionBox[];
    processing_warning?: string;
};
export type PdfResultData = {
    pages: PdfPageResult[];
    dpi: {
        x: number;
        y: number;
    };
};
export type ImageItemResult = {
    dpi: {
        width: number;
        height: number;
        x?: number;
        y?: number;
    };
    horizontal_lines?: DetectionBox[];
    rectangles?: DetectionBox[];
};
export type ImageResultData = {
    result: Record<string, ImageItemResult>;
};
export type AnalyzeResultData = PdfResultData | ImageResultData;
export type AnalyzePayload = {
    detection_params: DetectionParams;
    result_data: AnalyzeResultData;
    processed_filename: string;
    visualizations: {
        label: string;
        data_url: string;
    }[];
    debug_groups: {
        title: string;
        images: {
            name: string;
            data_url: string;
        }[];
    }[];
};
export type AnalyzeStreamEvent = {
    type: 'accepted';
    filename: string;
    started_at: string;
} | {
    type: 'progress';
    processed: number;
    total: number;
    message: string;
} | {
    type: 'heartbeat';
    ts: string;
} | {
    type: 'result';
    payload: AnalyzePayload;
} | {
    type: 'error';
    code: string;
    message: string;
};
export type AnalyzeRequestOptions = {
    include_empty_pages: boolean;
    include_visualizations: boolean;
    detection_params: DetectionParams;
    stream: boolean;
};
export type VersionResponse = {
    backend_version: string;
    frontend_version: string | null;
    git_sha: string;
    build_time: string;
};
