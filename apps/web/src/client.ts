import { MAX_UPLOAD_BYTES, PART_BYTES } from '@skalu/contracts/limits';
import type { DetectionParams } from '@skalu/contracts/types';
import { createAuthClient } from 'better-auth/react';

export const auth = createAuthClient();

export const api = async <T>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(path, init);
    if (!response.ok) {
        const result = await response.json<{ error?: string }>();
        throw new Error(result.error ?? `Request failed (${response.status}).`);
    }
    if (response.status === 204) {
        return undefined as T;
    }
    return response.json<T>();
};
export const post = <T>(path: string, body?: unknown) =>
    api<T>(path, { body: JSON.stringify(body ?? {}), headers: { 'content-type': 'application/json' }, method: 'POST' });

export const upload = async (
    file: File,
    params: DetectionParams,
    progress: (percent: number) => void,
): Promise<string> => {
    if (!file.name.toLowerCase().endsWith('.pdf') || file.size < 5 || file.size > MAX_UPLOAD_BYTES) {
        throw new Error('Choose a PDF up to 256 MiB.');
    }
    const { id } = await post<{ id: string }>('/api/jobs', {
        detection_params: params,
        filename: file.name,
        size: file.size,
    });
    try {
        for (let offset = 0, part = 1; offset < file.size; offset += PART_BYTES, part++) {
            await api(`/api/jobs/${id}/parts/${part}`, {
                body: file.slice(offset, offset + PART_BYTES),
                headers: { 'content-type': 'application/octet-stream' },
                method: 'PUT',
            });
            progress(Math.round((Math.min(offset + PART_BYTES, file.size) / file.size) * 100));
        }
        await post(`/api/jobs/${id}/start`);
        return id;
    } catch (error) {
        await api(`/api/jobs/${id}`, { method: 'DELETE' }).catch(() => undefined);
        throw error;
    }
};
