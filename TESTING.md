# Testing

```sh
bun install --frozen-lockfile
uv sync --project packages/engine --frozen
bun run typecheck
bun run check
bun run test
bun run test:engine
bun run build
bun run types:generate
bun run --cwd apps/worker build
```

Retained engine tests cover real detection/geometry regressions. Native transport checks exercise chunk/full equivalence, blank pages, valid JPEG, cleanup, invalid/encrypted PDFs and pre-render pixel limits. Bun checks protect input validation and private, non-rotating secret bootstrap.

## Playwright acceptance

```sh
bun run e2e:fixture
bunx playwright install chromium
bun run test:e2e
```

The generated PDF has independently known coordinates and a blank second page. Tests do not mock analysis responses. API tests traverse Better Auth, D1, R2, Workflow and native Python; browser tests cover accounts/login, key issuance/rotation, real drag/drop, decoded images before completion, reconnect and JSON downloads. Owner isolation, CSRF, old-key revocation, upload/admission guards, cancellation and failed PDFs have negative controls.

Run without launching a browser:

```sh
bun run e2e:fixture
bunx playwright test --project api
```

Use the Codex in-app browser for local interactive checks and close tabs afterward. CI runs the isolated Chromium browser suite. Interactive proof and API tests are distinct from executing the automated UI suite.

For an isolated deployed environment:

```sh
SKALU_E2E_ORIGIN=https://skalu-test.example.com bun run test:e2e
```

Tests create synthetic accounts and delete documents; use a dedicated test deployment. Wait for native container provisioning first. Local emulation does not establish live binding/rollout correctness or Linux memory behavior. Deployment prebuilds amd64 Docker and checks the running engine.

Do not edit Worker source during integrated tests: Wrangler reload can interrupt local Workflows. Finish edits, then run on stable source. Reconciliation reports interrupted terminal Workflows as failed jobs.

Native timeout testing accelerates the parent OS wait while spawning, terminating and joining a real child, and asserts HTTP 504 plus no surviving child/cache. Local expiry testing moves a stored job deadline into the past, invokes the real scheduled handler and checks the actual R2 source is deleted.

The scoped `bun run test` command is the CI entrypoint; bare `bun test` also discovers Playwright specs and is not a valid aggregate. Cleanup regression uses actual D1/R2 with one injected transient Workflow termination failure, checks retry ordering and retained admission capacity. Running-job E2E cancellation checks the native cache and R2 artifacts are gone before admitting a replacement.

The cleanup regression also covers the production transport: failed destruction retains capacity/storage; delayed destruction must settle before either is released. Its deferred provider promise verifies owner-side ordering; the runtime teardown contract is verified against the pinned SDK and Cloudflare documentation. Live API acceptance additionally checks the real Container/R2 transport: a stream accepted by Miniflare can still lack R2's known-length marker in production.
