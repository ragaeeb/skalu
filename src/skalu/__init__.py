"""Skalu document analysis toolkit."""

from .__version__ import __version__

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
    "__version__",
    "detect_horizontal_lines",
    "detect_rectangles",
    "draw_detections",
    "get_image_dpi",
    "process_folder",
    "process_pdf",
    "process_single_image",
    "round3",
]