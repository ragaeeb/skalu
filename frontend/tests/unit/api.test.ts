import { afterEach, describe, expect, mock, test } from "bun:test"
import { downloadUrl, fetchResults, startProcessing, uploadFile } from "../../src/lib/api"

afterEach(() => {
  mock.restore()
})

describe("api helpers", () => {
  test("uploadFile returns job id and sends file payload", async () => {
    const fakeFetch = mock(async () => new Response(JSON.stringify({ job_id: "abc123", status: "uploaded" }), { status: 202 }))
    globalThis.fetch = fakeFetch as unknown as typeof fetch

    const file = new File(["hello"], "sample.pdf", { type: "application/pdf" })
    const data = await uploadFile(file)

    expect(data.job_id).toBe("abc123")
    expect(fakeFetch).toHaveBeenCalledTimes(1)

    const call = fakeFetch.mock.calls[0]
    const req = call?.[1] as { body?: FormData } | undefined
    const form = req?.body
    expect(form).toBeInstanceOf(FormData)
    expect(form?.get("file")).toBeInstanceOf(File)
  })

  test("startProcessing sends processing configuration", async () => {
    const fakeFetch = mock(async () => new Response(JSON.stringify({ job_id: "abc123", status: "queued" }), { status: 202 }))
    globalThis.fetch = fakeFetch as unknown as typeof fetch

    await startProcessing("abc123", {
      include_empty_pages: true,
      save_visualization: true,
      detection_params: {
        min_line_width_ratio: 0.2,
        max_line_height: 10,
        min_rect_area_ratio: 0.001,
        max_rect_area_ratio: 0.5,
      },
    })

    const call = fakeFetch.mock.calls[0]
    const url = String(call?.[0])
    const req = call?.[1] as { body?: string; method?: string } | undefined
    expect(url).toContain("/process/abc123")
    expect(req?.method).toBe("POST")
    expect(typeof req?.body).toBe("string")
    const payload = JSON.parse(req?.body ?? "{}") as {
      include_empty_pages: boolean
      save_visualization: boolean
    }
    expect(payload.include_empty_pages).toBe(true)
    expect(payload.save_visualization).toBe(true)
  })

  test("uploadFile throws API error", async () => {
    const fakeFetch = mock(async () => new Response(JSON.stringify({ error: "bad upload" }), { status: 400 }))
    globalThis.fetch = fakeFetch as unknown as typeof fetch

    const file = new File(["hello"], "bad.txt", { type: "text/plain" })
    await expect(uploadFile(file)).rejects.toThrow("bad upload")
  })

  test("fetchResults toggles viz query", async () => {
    const fakeFetch = mock(async (url: string | URL | Request) => {
      const text = String(url)
      if (!text.includes("viz=true") && text.includes("job-1")) {
        return new Response(JSON.stringify({
          result_json: "{}",
          summary: null,
          processed_filename: "f.pdf",
          detection_params: {
            min_line_width_ratio: 0,
            max_line_height: 0,
            min_rect_area_ratio: 0,
            max_rect_area_ratio: 0
          },
          download_filename: "f.json",
          visualizations: [],
          debug_groups: []
        }), { status: 200 })
      }
      return new Response(JSON.stringify({
        result_json: "{}",
        summary: null,
        processed_filename: "f.pdf",
        detection_params: {
          min_line_width_ratio: 0,
          max_line_height: 0,
          min_rect_area_ratio: 0,
          max_rect_area_ratio: 0
        },
        download_filename: "f.json",
        visualizations: [{ label: "x", data_url: "y" }],
        debug_groups: []
      }), { status: 200 })
    })

    globalThis.fetch = fakeFetch as unknown as typeof fetch

    const withoutViz = await fetchResults("job-1")
    const withViz = await fetchResults("job-1", true)

    expect(withoutViz.visualizations.length).toBe(0)
    expect(withViz.visualizations.length).toBe(1)
  })

  test("downloadUrl uses job id", () => {
    expect(downloadUrl("job-7")).toBe("/download/job-7")
  })
})
