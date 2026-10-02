import { afterAll, afterEach, expect, it } from 'bun:test';
import { mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ensureSecrets } from './secrets';

const directory = mkdtempSync(join(tmpdir(), 'skalu-secrets-'));
afterEach(() => rmSync(join(directory, 'secrets.json'), { force: true }));
afterAll(() => rmSync(directory, { force: true, recursive: true }));
it('should preserve existing credentials while generating missing secrets privately', async () => {
    const path = join(directory, 'secrets.json');
    writeFileSync(path, JSON.stringify({ AUTH: 'x'.repeat(64) }), { mode: 0o644 });
    const result = await ensureSecrets(path, ['AUTH', 'NEW']);
    expect(result.AUTH).toBe('x'.repeat(64));
    expect(result.NEW?.length).toBeGreaterThanOrEqual(32);
    expect(statSync(path).mode & 0o777).toBe(0o600);
    expect((await ensureSecrets(path, ['AUTH', 'NEW'])).NEW).toBe(result.NEW);
});
it('should refuse an invalid existing secret rather than silently rotate it', async () => {
    const path = join(directory, 'secrets.json');
    for (const value of ['broken', 123, null]) {
        writeFileSync(path, JSON.stringify({ AUTH: value }));
        await expect(ensureSecrets(path, ['AUTH'])).rejects.toThrow('invalid AUTH');
        expect(await Bun.file(path).json()).toEqual({ AUTH: value });
    }
});
