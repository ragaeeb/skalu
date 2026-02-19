import { expect, test } from "@playwright/test"

const buildResultPayload = () => ({
  result_json: JSON.stringify(
    {
      pages: [
        {
          page: 1,
          width: 1200,
          height: 1600,
          horizontal_lines: [{ x: 10, y: 20, width: 100, height: 2 }],
        },
      ],
      detection_params: {
        min_line_width_ratio: 0.2,
        max_line_height: 10,
        min_rect_area_ratio: 0.001,
        max_rect_area_ratio: 0.5,
      },
    },
    null,
    2,
  ),
  result_data: {
    pages: [
      {
        page: 1,
        width: 1200,
        height: 1600,
      },
    ],
  },
  summary: {
    type: "pdf",
    pages: [{ page: 1, lines: 1, rectangles: 0, size: [1200, 1600] }],
  },
  processed_filename: "test.pdf",
  detection_params: {
    min_line_width_ratio: 0.2,
    max_line_height: 10,
    min_rect_area_ratio: 0.001,
    max_rect_area_ratio: 0.5,
  },
  visualizations: [{ label: "Page 1 detections", data_url: "data:image/jpeg;base64,a" }],
  debug_groups: [],
})

test.beforeEach(async ({ page }) => {
  await page.route("**/version", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        backend_version: "0.2.0",
        frontend_version: "0.1.0+test",
        git_sha: "abc123",
        build_time: "2026-02-19T00:00:00Z",
      }),
    })
  })
})

test("happy path upload to streamed result", async ({ page }) => {
  await page.route("**/analyze", async (route) => {
    const payload = buildResultPayload()
    const body = [
      JSON.stringify({ type: "accepted", filename: "test.pdf", started_at: "2026-02-19T00:00:00Z" }),
      JSON.stringify({ type: "progress", processed: 1, total: 1, message: "Finished all 1 pages" }),
      JSON.stringify({ type: "result", payload }),
    ].join("\n")

    await route.fulfill({
      status: 200,
      contentType: "application/x-ndjson",
      body: `${body}\n`,
    })
  })

  await page.goto("/")
  await page.getByRole("button", { name: "Choose File" }).click()
  await page.setInputFiles('input[type="file"]', {
    name: "sample.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("pdf-data"),
  })
  await page.getByRole("button", { name: "Process" }).click()

  await expect(page.getByTestId("job-progress")).toContainText("finished")
  await expect(page.getByTestId("results-panel")).toContainText("test.pdf")
  await expect(page.getByRole("link", { name: "Download Full JSON" })).toBeVisible()
})

test("streamed processing error shows alert", async ({ page }) => {
  await page.route("**/analyze", async (route) => {
    const body = [
      JSON.stringify({ type: "accepted", filename: "test.pdf", started_at: "2026-02-19T00:00:00Z" }),
      JSON.stringify({ type: "error", code: "processing_error", message: "Processing failed" }),
    ].join("\n")

    await route.fulfill({
      status: 200,
      contentType: "application/x-ndjson",
      body: `${body}\n`,
    })
  })

  await page.goto("/")
  await page.getByRole("button", { name: "Choose File" }).click()
  await page.setInputFiles('input[type="file"]', {
    name: "sample.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("pdf-data"),
  })
  await page.getByRole("button", { name: "Process" }).click()

  await expect(page.getByRole("alert")).toContainText("Processing failed")
})
