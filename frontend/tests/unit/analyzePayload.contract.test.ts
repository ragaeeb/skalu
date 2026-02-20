import { describe, expect, it } from 'bun:test';
import { safeParse, type InferOutput } from 'valibot';
import { analyzePayloadSchema } from '../../src/schemas/analyzePayload';
import type { AnalyzePayload } from '../../src/types';

type IsEqual<A, B> =
    (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2)
        ? ((<T>() => T extends B ? 1 : 2) extends (<T>() => T extends A ? 1 : 2) ? true : false)
        : false;
type Assert<T extends true> = T;

type AnalyzePayloadFromSchema = InferOutput<typeof analyzePayloadSchema>;
const _assertAnalyzePayloadType: Assert<IsEqual<AnalyzePayload, AnalyzePayloadFromSchema>> = true;

describe('analyze payload contract', () => {
    it('should accept a valid PDF analyze payload', () => {
        const payload: AnalyzePayload = {
            detection_params: {
                min_line_width_ratio: 0.2,
                max_line_height: 10,
                min_rect_area_ratio: 0.001,
                max_rect_area_ratio: 0.5,
            },
            result_data: {
                pages: [
                    {
                        page: 1,
                        width: 1200,
                        height: 1600,
                        horizontal_lines: [{ x: 10, y: 20, width: 200, height: 2 }],
                    },
                ],
                dpi: { x: 144, y: 144 },
            },
            processed_filename: 'sample.pdf',
            visualizations: [{ label: 'Page 1 detections', data_url: 'data:image/jpeg;base64,abc' }],
            debug_groups: [],
        };

        const result = safeParse(analyzePayloadSchema, payload);
        expect(result.success).toBe(true);
    });

    it('should accept a valid image analyze payload', () => {
        const payload: AnalyzePayload = {
            detection_params: {
                min_line_width_ratio: 0.2,
                max_line_height: 10,
                min_rect_area_ratio: 0.001,
                max_rect_area_ratio: 0.5,
            },
            result_data: {
                result: {
                    'input.png': {
                        dpi: { width: 800, height: 600, x: 300, y: 300 },
                        rectangles: [{ x: 100, y: 120, width: 180, height: 90 }],
                    },
                },
            },
            processed_filename: 'input.png',
            visualizations: [],
            debug_groups: [],
        };

        const result = safeParse(analyzePayloadSchema, payload);
        expect(result.success).toBe(true);
    });

    it('should reject payloads missing top-level detection_params', () => {
        const invalidPayload = {
            result_data: {
                pages: [],
                dpi: { x: 144, y: 144 },
            },
            processed_filename: 'sample.pdf',
            visualizations: [],
            debug_groups: [],
        };

        const result = safeParse(analyzePayloadSchema, invalidPayload);
        expect(result.success).toBe(false);
    });
});
