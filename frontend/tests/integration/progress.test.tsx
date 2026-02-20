import { describe, expect, test } from 'bun:test';
import { renderToString } from 'react-dom/server';
import { formatProgress, JobProgress } from '../../src/components/JobProgress';

describe('job progress rendering', () => {
    test('formatProgress renders idle state', () => {
        const text = formatProgress({
            filename: 'sample.pdf',
            message: 'Ready to process',
            processed: 0,
            status: 'idle',
            total: 0,
        });

        expect(text).toContain('Ready to process');
        expect(text).toContain('sample.pdf');
    });

    test('formatProgress renders finished state', () => {
        const text = formatProgress({
            filename: 'test.pdf',
            message: 'Analysis complete',
            processed: 3,
            status: 'finished',
            total: 3,
        });

        expect(text).toContain('finished');
        expect(text).toContain('3/3');
    });

    test('component server render includes progress content', () => {
        const html = renderToString(
            <JobProgress
                progress={{
                    filename: 'x.pdf',
                    message: 'Processing page 2 of 3',
                    processed: 1,
                    status: 'running',
                    total: 3,
                }}
            />,
        );

        expect(html).toContain('Progress');
        expect(html).toContain('running');
        expect(html).toContain('Processing page 2 of 3');
    });
});
