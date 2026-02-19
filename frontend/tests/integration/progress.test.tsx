import { describe, expect, test } from "bun:test"
import { renderToString } from "react-dom/server"
import { JobProgress, formatProgress } from "../../src/components/JobProgress"

describe("job progress rendering", () => {
  test("formatProgress supports null state", () => {
    expect(formatProgress(null)).toContain("Waiting")
  })

  test("formatProgress supports completed state", () => {
    const text = formatProgress({
      status: "finished",
      processed: 3,
      total: 3,
      message: "Processing complete",
      filename: "test.pdf",
      result_ready: true
    })
    expect(text).toContain("finished")
    expect(text).toContain("3/3")
  })

  test("component server render includes progress content", () => {
    const html = renderToString(
      <JobProgress
        status={{
          status: "processing",
          processed: 1,
          total: 3,
          message: "Processing page 2 of 3",
          filename: "x.pdf",
          result_ready: false
        }}
      />
    )

    expect(html).toContain("Progress")
    expect(html).toContain("processing")
  })
})
