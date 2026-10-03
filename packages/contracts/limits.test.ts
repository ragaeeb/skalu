import { expect, it } from 'bun:test';
import { DEFAULT_PARAMS, parseParams } from './src/limits';

it('should reject invalid public detection inputs and retain supported defaults', () => {
    expect(parseParams(undefined)).toEqual(DEFAULT_PARAMS);
    for (const input of [
        null,
        [],
        '',
        { min_line_width_ratio: 0 },
        { max_line_height: 2.2 },
        { max_line_height: Infinity },
        { max_rect_area_ratio: 0.5, min_rect_area_ratio: 0.9 },
        { max_rect_area_ratio: NaN },
        { unknown: 1 },
    ]) {
        expect(() => parseParams(input)).toThrow();
    }
});
