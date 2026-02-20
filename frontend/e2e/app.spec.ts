import { expect, test } from '@playwright/test';

const buildResultPayload = () => ({
    debug_groups: [],
    detection_params: {
        max_line_height: 10,
        max_rect_area_ratio: 0.5,
        min_line_width_ratio: 0.2,
        min_rect_area_ratio: 0.001,
    },
    processed_filename: 'test.pdf',
    result_data: { pages: [{ height: 1600, page: 1, width: 1200 }] },
    result_json: JSON.stringify(
        {
            detection_params: {
                max_line_height: 10,
                max_rect_area_ratio: 0.5,
                min_line_width_ratio: 0.2,
                min_rect_area_ratio: 0.001,
            },
            pages: [
                { height: 1600, horizontal_lines: [{ height: 2, width: 100, x: 10, y: 20 }], page: 1, width: 1200 },
            ],
        },
        null,
        2,
    ),
    summary: { pages: [{ lines: 1, page: 1, rectangles: 0, size: [1200, 1600] }], type: 'pdf' },
    visualizations: [{ data_url: 'data:image/jpeg;base64,a', label: 'Page 1 detections' }],
});

test.beforeEach(async ({ page }) => {
    await page.route('**/version', async (route) => {
        await route.fulfill({
            body: JSON.stringify({
                backend_version: '0.2.0',
                build_time: '2026-02-19T00:00:00Z',
                frontend_version: '0.1.0+test',
                git_sha: 'abc123',
            }),
            contentType: 'application/json',
            status: 200,
        });
    });
});

test('happy path upload to streamed result', async ({ page }) => {
    await page.route('**/analyze', async (route) => {
        const payload = buildResultPayload();
        const body = [
            JSON.stringify({ filename: 'test.pdf', started_at: '2026-02-19T00:00:00Z', type: 'accepted' }),
            JSON.stringify({ message: 'Finished all 1 pages', processed: 1, total: 1, type: 'progress' }),
            JSON.stringify({ payload, type: 'result' }),
        ].join('\n');

        await route.fulfill({ body: `${body}\n`, contentType: 'application/x-ndjson', status: 200 });
    });

    await page.goto('/');
    await page.getByRole('button', { name: 'Choose File' }).click();
    await page.setInputFiles('input[type="file"]', {
        buffer: Buffer.from('pdf-data'),
        mimeType: 'application/pdf',
        name: 'sample.pdf',
    });
    await page.getByRole('button', { name: 'Process' }).click();

    await expect(page.getByTestId('job-progress')).toContainText('finished');
    await expect(page.getByTestId('results-panel')).toContainText('test.pdf');
    await expect(page.getByRole('link', { name: 'Download Full JSON' })).toBeVisible();
});

test('streamed processing error shows alert', async ({ page }) => {
    await page.route('**/analyze', async (route) => {
        const body = [
            JSON.stringify({ filename: 'test.pdf', started_at: '2026-02-19T00:00:00Z', type: 'accepted' }),
            JSON.stringify({ code: 'processing_error', message: 'Processing failed', type: 'error' }),
        ].join('\n');

        await route.fulfill({ body: `${body}\n`, contentType: 'application/x-ndjson', status: 200 });
    });

    await page.goto('/');
    await page.getByRole('button', { name: 'Choose File' }).click();
    await page.setInputFiles('input[type="file"]', {
        buffer: Buffer.from('pdf-data'),
        mimeType: 'application/pdf',
        name: 'sample.pdf',
    });
    await page.getByRole('button', { name: 'Process' }).click();

    await expect(page.getByRole('alert')).toContainText('Processing failed');
});
