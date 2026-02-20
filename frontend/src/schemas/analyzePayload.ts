import * as v from 'valibot';

export const detectionParamsSchema = v.strictObject({
    min_line_width_ratio: v.number(),
    max_line_height: v.number(),
    min_rect_area_ratio: v.number(),
    max_rect_area_ratio: v.number(),
});

export const detectionBoxSchema = v.strictObject({
    x: v.number(),
    y: v.number(),
    width: v.number(),
    height: v.number(),
});

export const pdfPageResultSchema = v.strictObject({
    page: v.number(),
    width: v.number(),
    height: v.number(),
    horizontal_lines: v.optional(v.array(detectionBoxSchema)),
    rectangles: v.optional(v.array(detectionBoxSchema)),
    processing_warning: v.optional(v.string()),
});

export const pdfResultDataSchema = v.strictObject({
    pages: v.array(pdfPageResultSchema),
    dpi: v.strictObject({
        x: v.number(),
        y: v.number(),
    }),
});

export const imageItemResultSchema = v.strictObject({
    dpi: v.strictObject({
        width: v.number(),
        height: v.number(),
        x: v.optional(v.number()),
        y: v.optional(v.number()),
    }),
    horizontal_lines: v.optional(v.array(detectionBoxSchema)),
    rectangles: v.optional(v.array(detectionBoxSchema)),
});

export const imageResultDataSchema = v.strictObject({
    result: v.record(v.string(), imageItemResultSchema),
});

export const analyzeResultDataSchema = v.union([pdfResultDataSchema, imageResultDataSchema]);

export const visualizationSchema = v.strictObject({
    label: v.string(),
    data_url: v.string(),
});

export const debugImageSchema = v.strictObject({
    name: v.string(),
    data_url: v.string(),
});

export const debugGroupSchema = v.strictObject({
    title: v.string(),
    images: v.array(debugImageSchema),
});

export const analyzePayloadSchema = v.strictObject({
    detection_params: detectionParamsSchema,
    result_data: analyzeResultDataSchema,
    processed_filename: v.string(),
    visualizations: v.array(visualizationSchema),
    debug_groups: v.array(debugGroupSchema),
});
