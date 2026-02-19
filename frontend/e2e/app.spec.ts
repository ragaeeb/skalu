import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.route("**/analyze", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "job-e2e", status: "uploaded" })
    })
  })

  await page.route("**/process/job-e2e", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "job-e2e", status: "queued" })
    })
  })

  await page.route("**/progress/job-e2e", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "finished",
        processed: 1,
        total: 1,
        message: "Processing complete",
        filename: "test.pdf",
        result_ready: true
      })
    })
  })

  await page.route("**/results/job-e2e**", async (route) => {
    const isViz = route.request().url().includes("viz=true")
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        result_json: "{\"ok\":true}",
        summary: null,
        processed_filename: "test.pdf",
        detection_params: {
          min_line_width_ratio: 0.2,
          max_line_height: 10,
          min_rect_area_ratio: 0.001,
          max_rect_area_ratio: 0.5
        },
        download_filename: "test_results.json",
        visualizations: isViz ? [{ label: "viz", data_url: "data:image/jpeg;base64,a" }] : [],
        debug_groups: []
      })
    })
  })
})

test("happy path upload to result", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "Choose File" }).click()
  await page.setInputFiles('input[type="file"]', {
    name: "sample.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("pdf-data")
  })
  await page.getByRole("button", { name: "Process" }).click()

  await expect(page.getByTestId("job-progress")).toContainText("finished")
  await expect(page.getByTestId("results-panel")).toContainText("test.pdf")
  await expect(page.getByRole("link", { name: "Download Full JSON" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Download Full JSON" })).toHaveAttribute("href", "/download/job-e2e")
})

test("viz toggle requests visualization payload", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "Choose File" }).click()
  await page.setInputFiles('input[type="file"]', {
    name: "sample.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("pdf-data")
  })
  await page.getByRole("button", { name: "Process" }).click()

  await page.getByRole("checkbox", { name: "Include visualizations in response" }).check()
  await expect(page.getByTestId("results-panel")).toContainText("Page 1")
})

test("error path unsupported file type", async ({ page }) => {
  await page.route("**/analyze", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ error: "Unsupported file type." })
    })
  })

  await page.goto("/")
  await page.getByRole("button", { name: "Choose File" }).click()
  await page.setInputFiles('input[type="file"]', {
    name: "sample.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("bad-data")
  })

  await expect(page.getByRole("alert")).toContainText("Unsupported file type.")
})
