import { describe, expect, test } from "bun:test"
import { renderToString } from "react-dom/server"
import { JobProgress, formatProgress } from "../../src/components/JobProgress"

describe("job progress rendering", () => {
  test("formatProgress renders idle state", () => {
    const text = formatProgress({
      status: "idle",
      processed: 0,
      total: 0,
      message: "Ready to process",
      filename: "sample.pdf",
    })

    expect(text).toContain("Ready to process")
    expect(text).toContain("sample.pdf")
  })

  test("formatProgress renders finished state", () => {
    const text = formatProgress({
      status: "finished",
      processed: 3,
      total: 3,
      message: "Analysis complete",
      filename: "test.pdf",
    })

    expect(text).toContain("finished")
    expect(text).toContain("3/3")
  })

  test("component server render includes progress content", () => {
    const html = renderToString(
      <JobProgress
        progress={{
          status: "running",
          processed: 1,
          total: 3,
          message: "Processing page 2 of 3",
          filename: "x.pdf",
        }}
      />,
    )

    expect(html).toContain("Progress")
    expect(html).toContain("running")
    expect(html).toContain("Processing page 2 of 3")
  })
})
