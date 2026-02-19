// Shared test bootstrap for bun:test suites.
Object.assign(globalThis, {
  __APP_VERSION__: "0.1.0-test",
  __APP_GIT_SHA__: "test-sha",
})
