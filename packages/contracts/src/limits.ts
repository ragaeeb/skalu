import type { DetectionParams } from './types';

export const PART_BYTES = 8 * 1024 * 1024;
export const MAX_UPLOAD_BYTES = 256 * 1024 * 1024;
export const MAX_PAGES = 1000;
export const DEFAULT_PARAMS: DetectionParams = {
    max_line_height: 10,
    max_rect_area_ratio: 0.5,
    min_line_width_ratio: 0.16,
    min_rect_area_ratio: 0.001,
};

export const parseParams = (value: unknown): DetectionParams => {
    if (value !== undefined && (value === null || typeof value !== 'object' || Array.isArray(value))) {
        throw new Error('Detection parameters must be an object.');
    }
    const params = { ...DEFAULT_PARAMS, ...(value as Partial<DetectionParams>) };
    for (const [key, number] of Object.entries(params)) {
        if (!(key in DEFAULT_PARAMS) || typeof number !== 'number' || !Number.isFinite(number)) {
            throw new Error('Detection parameters must be finite numbers.');
        }
    }
    if (
        params.min_line_width_ratio <= 0 ||
        params.min_line_width_ratio > 1 ||
        !Number.isInteger(params.max_line_height) ||
        params.max_line_height < 1 ||
        params.max_line_height > 100 ||
        params.min_rect_area_ratio < 0 ||
        params.max_rect_area_ratio > 1 ||
        params.max_rect_area_ratio <= 0 ||
        params.min_rect_area_ratio > params.max_rect_area_ratio
    ) {
        throw new Error('Detection parameters are outside their supported ranges.');
    }
    return params;
};
