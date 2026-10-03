import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { AnalysisResult } from '@skalu/contracts/types';

test('should create an account, manage keys, drop a PDF, reconnect, inspect images and download JSON', async ({
    page,
}) => {
    const email = `browser-${crypto.randomUUID()}@example.com`;
    await page.goto('/');
    await page.getByLabel('Name', { exact: true }).fill('Browser Reader');
    await page.getByLabel('Email', { exact: true }).fill(email);
    await page.getByLabel('Password', { exact: true }).fill('Only-a-test-password-2026');
    await page.getByRole('button', { exact: true, name: 'Create account' }).click();
    await expect(page.getByRole('heading', { name: 'Your workbench.' })).toBeVisible();
    await page.getByText('Your API key', { exact: true }).click();
    await page.getByRole('button', { exact: true, name: 'Create API key' }).click();
    const keyField = page.getByLabel('API key — copy now; shown only once');
    await expect(keyField).toHaveValue(/^sk_[a-f0-9]{64}$/);
    const firstKey = await keyField.inputValue();
    await page.getByRole('button', { name: 'Rotate API key' }).click();
    await expect(keyField).not.toHaveValue(firstKey);
    // Real drag/drop uses a real PDF, with no intercepted API or engine responses.
    const bytes = readFileSync('e2e/lines.pdf');
    const transfer = await page.evaluateHandle(
        (bytes) => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([new Uint8Array(bytes)], 'lines.pdf', { type: 'application/pdf' }));
            return transfer;
        },
        [...bytes],
    );
    await page.locator('.drop-zone').dispatchEvent('drop', { dataTransfer: transfer });
    await transfer.dispose();
    await page.getByRole('button', { name: 'Analyze PDF' }).click();
    const image = page.getByRole('img', { exact: true, name: 'Detected lines and rectangles on page 1' });
    await expect(image).toBeVisible({ timeout: 30000 });
    await expect.poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBe(1200);
    await expect(page.getByText('running', { exact: true }).first()).toBeVisible();
    await page.reload();
    await expect(image).toBeVisible();
    const downloadLink = page.getByRole('link', { name: 'Download JSON' });
    await expect(downloadLink).toBeVisible({ timeout: 90000 });
    const pending = page.waitForEvent('download');
    await downloadLink.click();
    const download = await pending;
    const path = await download.path();
    expect(path).not.toBeNull();
    const result: AnalysisResult = JSON.parse(readFileSync(path!, 'utf8'));
    expect(result.result_data.pages).toHaveLength(12);
    expect(result.result_data.pages[0]?.horizontal_lines?.[0]?.width).toBeGreaterThan(950);
    await page.getByRole('button', { name: 'Sign out' }).click();
    await page.getByRole('button', { name: 'Already have an account? Sign in' }).click();
    await page.getByLabel('Email', { exact: true }).fill(email);
    await page.getByLabel('Password', { exact: true }).fill('Only-a-test-password-2026');
    await page.getByRole('button', { exact: true, name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Your workbench.' })).toBeVisible();
    await page.getByRole('button', { name: /lines.pdf/ }).click();
    await expect(downloadLink).toBeVisible();
    await page.getByRole('button', { name: 'Delete document' }).click();
    await expect(downloadLink).not.toBeVisible();
});
