import { afterEach, describe, expect, mock, test } from 'bun:test';
import { analyzeFile, analyzeFileStream, fetchVersion } from '../../src/lib/api';
import type { AnalyzePayload } from '../../src/types';

const DEFAULT_OPTIONS = {
    detection_params: {
        max_line_height: 10,
        max_rect_area_ratio: 0.5,
        min_line_width_ratio: 0.2,
        min_rect_area_ratio: 0.001,
    },
    include_empty_pages: true,
    include_visualizations: false,
};

const buildPayload = (): AnalyzePayload => ({
    debug_groups: [],
    detection_params: DEFAULT_OPTIONS.detection_params,
    processed_filename: 'sample.pdf',
    result_data: { pages: [] },
    result_json: '{"pages":[]}',
    summary: { pages: [], type: 'pdf' },
    visualizations: [],
});

const streamFromChunks = (chunks: string[]): ReadableStream<Uint8Array> =>
    new ReadableStream<Uint8Array>({
        start: (controller) => {
            const encoder = new TextEncoder();
            for (const chunk of chunks) {
                controller.enqueue(encoder.encode(chunk));
            }
            controller.close();
        },
    });

afterEach(() => {
    mock.restore();
});

describe('api helpers', () => {
    test('analyzeFile posts multipart form and returns payload', async () => {
        const payload = buildPayload();
        const fakeFetch = mock(async () => new Response(JSON.stringify(payload), { status: 200 }));
        globalThis.fetch = fakeFetch as unknown as typeof fetch;

        const file = new File(['hello'], 'sample.pdf', { type: 'application/pdf' });
        const result = await analyzeFile({ file, file_url: null }, DEFAULT_OPTIONS);

        expect(result.processed_filename).toBe('sample.pdf');
        expect(fakeFetch).toHaveBeenCalledTimes(1);
        const request = fakeFetch.mock.calls[0]?.[1] as { body?: FormData } | undefined;
        expect(request?.body).toBeInstanceOf(FormData);
        expect(request?.body?.get('file')).toBeInstanceOf(File);
        expect(request?.body?.get('stream')).toBe('false');
        expect(request?.body?.get('include_empty_pages')).toBe('true');
    });

    test('analyzeFile throws backend error message', async () => {
        const fakeFetch = mock(
            async () => new Response(JSON.stringify({ error: 'Unsupported file type.' }), { status: 400 }),
        );
        globalThis.fetch = fakeFetch as unknown as typeof fetch;

        const file = new File(['hello'], 'bad.txt', { type: 'text/plain' });
        await expect(analyzeFile({ file, file_url: null }, DEFAULT_OPTIONS)).rejects.toThrow('Unsupported file type.');
    });

    test('analyzeFile posts file_url when provided', async () => {
        const payload = buildPayload();
        const fakeFetch = mock(async () => new Response(JSON.stringify(payload), { status: 200 }));
        globalThis.fetch = fakeFetch as unknown as typeof fetch;

        const result = await analyzeFile({ file: null, file_url: 'https://example.com/input.pdf' }, DEFAULT_OPTIONS);

        expect(result.processed_filename).toBe('sample.pdf');
        const request = fakeFetch.mock.calls[0]?.[1] as { body?: FormData } | undefined;
        expect(request?.body?.get('file')).toBeNull();
        expect(request?.body?.get('file_url')).toBe('https://example.com/input.pdf');
    });

    test('analyzeFileStream parses split NDJSON chunks and ignores malformed lines', async () => {
        const payload = buildPayload();
        const chunks = [
            '{"type":"accepted","filename":"sample.pdf","started_at":"2026-02-19T00:00:00Z"}\n',
            '{"type":"progress","processed":1,"total":3,"message":"Processing page 2 of 3"}\n',
            'not-json\n',
            '{"type":"result","payload":',
            JSON.stringify(payload),
            '}\n',
        ];

        const fakeFetch = mock(
            async () =>
                new Response(streamFromChunks(chunks), {
                    headers: { 'Content-Type': 'application/x-ndjson' },
                    status: 200,
                }),
        );
        globalThis.fetch = fakeFetch as unknown as typeof fetch;

        const accepted = mock(() => {});
        const progress = mock(() => {});
        const result = mock(() => {});
        const error = mock(() => {});

        const file = new File(['hello'], 'sample.pdf', { type: 'application/pdf' });
        await analyzeFileStream({ file, file_url: null }, DEFAULT_OPTIONS, {
            onAccepted: accepted,
            onError: error,
            onProgress: progress,
            onResult: result,
        });

        expect(accepted).toHaveBeenCalledTimes(1);
        expect(progress).toHaveBeenCalledTimes(1);
        expect(result).toHaveBeenCalledTimes(1);
        expect(error).toHaveBeenCalledTimes(0);
    });

    test('analyzeFileStream throws when stream ends without terminal event', async () => {
        const fakeFetch = mock(
            async () =>
                new Response(
                    streamFromChunks([
                        '{"type":"accepted","filename":"sample.pdf","started_at":"2026-02-19T00:00:00Z"}\n',
                    ]),
                    { headers: { 'Content-Type': 'application/x-ndjson' }, status: 200 },
                ),
        );
        globalThis.fetch = fakeFetch as unknown as typeof fetch;

        const file = new File(['hello'], 'sample.pdf', { type: 'application/pdf' });
        await expect(
            analyzeFileStream({ file, file_url: null }, DEFAULT_OPTIONS, {
                onAccepted: () => {},
                onError: () => {},
                onProgress: () => {},
                onResult: () => {},
            }),
        ).rejects.toThrow('Streaming response ended before terminal result');
    });

    test('fetchVersion sends frontend version header', async () => {
        const fakeFetch = mock(
            async () =>
                new Response(
                    JSON.stringify({
                        backend_version: '0.2.0',
                        build_time: '2026-02-19T00:00:00Z',
                        frontend_version: '0.1.0+dev',
                        git_sha: 'abc123',
                    }),
                    { status: 200 },
                ),
        );
        globalThis.fetch = fakeFetch as unknown as typeof fetch;

        const result = await fetchVersion();
        expect(result.backend_version).toBe('0.2.0');
        const request = fakeFetch.mock.calls[0]?.[1] as { headers?: Record<string, string> } | undefined;
        expect(request?.headers?.['X-Frontend-Version']).toContain('+');
    });
});
