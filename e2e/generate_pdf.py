"""A known rule plus blank pages, with no precomputed engine output."""
from pathlib import Path
import pymupdf as fitz

with fitz.open() as document:
    for index in range(12):
        page = document.new_page(width=600, height=800)
        if index != 1:
            page.draw_line((50, 150), (550, 150), width=2)
    Path("e2e/lines.pdf").write_bytes(document.tobytes())

with fitz.open() as document:
    document.new_page(width=600, height=800).draw_line((50, 150), (550, 150), width=2)
    document.set_metadata({"keywords": "x" * (8 * 1024 * 1024)})
    Path("e2e/multipart.pdf").write_bytes(document.tobytes())

with fitz.open() as document:
    for _ in range(100):
        document.new_page(width=600, height=800).draw_line((50, 150), (550, 150), width=2)
    Path("e2e/cancel.pdf").write_bytes(document.tobytes())
