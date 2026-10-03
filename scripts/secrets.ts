import { chmodSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

export const ensureSecrets = async (path: string, names: string[]): Promise<Record<string, string>> => {
    const values: Record<string, string> = existsSync(path) ? await Bun.file(path).json() : {};
    if (!values || typeof values !== 'object' || Array.isArray(values)) {
        throw new Error(`Invalid secret file: ${path}`);
    }
    for (const name of names) {
        if (values[name] !== undefined && (typeof values[name] !== 'string' || values[name].length < 32)) {
            throw new Error(`Restore or remove invalid ${name} in ${path}.`);
        }
        values[name] ??= crypto.randomUUID().replaceAll('-', '') + crypto.randomUUID().replaceAll('-', '');
    }
    mkdirSync(dirname(path), { mode: 0o700, recursive: true });
    writeFileSync(path, `${JSON.stringify(values, null, 2)}\n`, { mode: 0o600 });
    chmodSync(path, 0o600);
    return values;
};
