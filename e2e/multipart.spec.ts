import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { PART_BYTES } from '@skalu/contracts/limits';

test('should upload and analyze a real PDF spanning multiple R2 parts', async ({ request }) => {
    const origin = process.env.SKALU_E2E_ORIGIN ?? 'http://localhost:8787';
    const headers = { origin };
    const email = `parts-${crypto.randomUUID()}@example.com`;
    await expect
        .poll(
            async () => {
                const response = await request.post('/api/auth/sign-up/email', {
                    data: { email, name: 'Multipart Reader', password: 'Only-a-test-password-2026' },
                    headers,
                });
                if (response.status() !== 429) {
                    expect(response.status(), await response.text()).toBe(200);
                }
                return response.status();
            },
            { intervals: [1000, 11000], timeout: 30000 },
        )
        .toBe(200);
    const pdf = readFileSync('e2e/multipart.pdf');
    expect(pdf.length).toBeGreaterThan(PART_BYTES);
    const created = await request.post('/api/jobs', { data: { filename: 'multipart.pdf', size: pdf.length }, headers });
    expect(created.status()).toBe(201);
    const { id } = await created.json();
    try {
        for (let offset = 0, part = 1; offset < pdf.length; offset += PART_BYTES, part++) {
            const uploaded = await request.put(`/api/jobs/${id}/parts/${part}`, {
                data: pdf.subarray(offset, offset + PART_BYTES),
                headers,
            });
            expect(uploaded.status(), await uploaded.text()).toBe(200);
        }
        expect((await request.post(`/api/jobs/${id}/start`, { headers })).status()).toBe(202);
        await expect
            .poll(async () => (await (await request.get(`/api/jobs/${id}`)).json()).status, { timeout: 30000 })
            .toBe('completed');
        const result = await (await request.get(`/api/jobs/${id}/download`)).json();
        expect(result.result_data.pages[0].horizontal_lines[0].width).toBeGreaterThan(950);
    } finally {
        await request.delete(`/api/jobs/${id}`, { headers });
    }
});
