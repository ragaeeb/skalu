export type DetectionParams = {
    min_line_width_ratio: number;
    max_line_height: number;
    min_rect_area_ratio: number;
    max_rect_area_ratio: number;
};

export type SummaryPage = { page: number; lines: number; rectangles: number; size: [number, number] };

export type SummaryItem = { name: string; lines: number; rectangles: number; dimensions: [number, number] };

export type Summary = { type: 'pdf' | 'image'; pages?: SummaryPage[]; items?: SummaryItem[] };

export type AnalyzePayload = {
    result_json: string;
    result_data: Record<string, unknown>;
    summary: Summary | null;
    processed_filename: string;
    detection_params: DetectionParams;
    visualizations: Array<{ label: string; data_url: string }>;
    debug_groups: Array<{ title: string; images: Array<{ name: string; data_url: string }> }>;
};

export type AnalyzeStreamEvent =
    | { type: 'accepted'; filename: string; started_at: string }
    | { type: 'progress'; processed: number; total: number; message: string }
    | { type: 'heartbeat'; ts: string }
    | { type: 'result'; payload: AnalyzePayload }
    | { type: 'error'; code: string; message: string };

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
