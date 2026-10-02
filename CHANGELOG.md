# Changelog

## 2.0.0

- Move hosting to Cloudflare Workers, D1, R2, Workflows and native Containers.
- Add accounts, session-only API key issuance/rotation and private document artifacts.
- Replace synchronous public analysis with API v2 jobs, bounded multipart uploads and page steps.
- Add incremental image display, reconnect, streamed JSON downloads and expiry/cancellation.
- Consolidate deployment and local development into root Bun commands.

Historical engine changes are retained in `packages/engine/CHANGELOG.md`.
