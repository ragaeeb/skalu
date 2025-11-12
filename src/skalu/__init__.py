"""Skalu document analysis toolkit."""

import fitz  # type: ignore
from PIL import Image

from . import processing as _processing
from .processing import (
    detect_horizontal_lines,
    detect_rectangles,
    draw_detections,
    get_image_dpi,
    process_folder,
    process_pdf,
    process_single_image,
    round3,
)

__all__ = [
    "detect_horizontal_lines",
    "detect_rectangles",
    "draw_detections",
    "get_image_dpi",
    "process_folder",
    "process_pdf",
    "process_single_image",
    "round3",
    "Image",
    "fitz",
]

# Ensure the processing module exposes the same objects that tests monkeypatch.
_processing.Image = Image
_processing.fitz = fitz

del _processing
