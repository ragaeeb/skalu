# Trigger.dev Future Integration (Deferred)

This project currently runs in a single-shot request model on Cloud Run:
- one `POST /analyze` request does upload + processing + response streaming,
- no persisted jobs/sessions,
- no resumable work.

## Why keep Trigger.dev out of runtime now

- Current requirement is minimal operational overhead and one-shot deploys.
- Cloud Run is sufficient for synchronous workloads within request timeout.
- Keeping runtime dependency surface small improves DX and debugging.

## When Trigger.dev becomes useful

Consider adding Trigger.dev if any of these become required:
- processing that consistently exceeds Cloud Run request timeout,
- durable retries,
- resumable or scheduled background runs,
- cross-request orchestration beyond single uploads.

## Suggested future shape

- Keep `POST /analyze` for short jobs.
- Add a separate async endpoint (for example `POST /analyze-async`) that enqueues work via Trigger.dev.
- Return run IDs from Trigger.dev and expose run status/result lookup in the UI.
- Preserve the single-shot path for local DX and small documents.
