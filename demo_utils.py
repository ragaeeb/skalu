"""Shared helpers for the Skalu demos."""
from __future__ import annotations

import base64
import os
import re
from typing import Dict, List, Optional

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "bmp", "tiff", "webp"}

DEFAULT_PARAMS = {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10,
    "min_rect_area_ratio": 0.001,
    "max_rect_area_ratio": 0.5,
}


def allowed_file(filename: str) -> bool:
    """Return True when a filename has a supported extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_summary(data: dict) -> Optional[dict]:
    """Create a compact summary of PDF or image detection results."""
    if not data:
        return None

    if "result" in data:
        items = []
        for name, info in data["result"].items():
            lines = len(info.get("horizontal_lines", []))
            rectangles = len(info.get("rectangles", []))
            items.append(
                {
                    "name": name,
                    "lines": lines,
                    "rectangles": rectangles,
                    "dimensions": (
                        info.get("dpi", {}).get("width"),
                        info.get("dpi", {}).get("height"),
                    ),
                }
            )
        return {"type": "image", "items": items}

    if "pages" in data:
        pages = []
        for page in data["pages"]:
            pages.append(
                {
                    "page": page.get("page"),
                    "lines": len(page.get("horizontal_lines", [])),
                    "rectangles": len(page.get("rectangles", [])),
                    "size": (page.get("width"), page.get("height")),
                }
            )
        return {"type": "pdf", "pages": pages}

    return None


def encode_image_as_data_url(path: str) -> Optional[str]:
    """Load an image and return it as a data URL for inline display."""
    try:
        with open(path, "rb") as file:
            encoded = base64.b64encode(file.read()).decode("ascii")
    except OSError:
        return None

    ext = os.path.splitext(path)[1].lower()
    if ext in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/octet-stream"

    return f"data:{mime};base64,{encoded}"


def collect_visualizations(workdir: str) -> List[Dict[str, str]]:
    """Return detected visualization images stored within *workdir*."""
    visualizations: List[Dict[str, str]] = []
    if not os.path.isdir(workdir):
        return visualizations

    for name in sorted(os.listdir(workdir)):
        if not name.lower().endswith(("_detected.jpg", "_detected.jpeg", "_detected.png", "_detected.webp")):
            continue

        path = os.path.join(workdir, name)
        label = "Detections"
        page_match = re.search(r"_page_(\d+)_", name)
        if page_match:
            label = f"Page {int(page_match.group(1))} detections"
        elif "page" in name.lower():
            label = name.rsplit("_detected", 1)[0]

        visualizations.append({"label": label, "path": path})

    return visualizations


def collect_debug_groups(debug_dir: str) -> List[Dict[str, List[Dict[str, str]]]]:
    """Collect debug imagery grouped by page or processing step."""
    groups: List[Dict[str, List[Dict[str, str]]]] = []
    if not debug_dir or not os.path.isdir(debug_dir):
        return groups

    entries = sorted(os.listdir(debug_dir))
    has_subdirs = any(os.path.isdir(os.path.join(debug_dir, entry)) for entry in entries)

    def sort_key(name: str):
        page_match = re.search(r"(\d+)", name)
        return (int(page_match.group(1)) if page_match else float("inf"), name)

    if has_subdirs:
        for entry in sorted(entries, key=sort_key):
            entry_path = os.path.join(debug_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            images = []
            for img_name in sorted(os.listdir(entry_path)):
                if not img_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                images.append({"name": img_name, "path": os.path.join(entry_path, img_name)})

            if images:
                title = entry.replace("_", " ").title()
                page_match = re.search(r"(\d+)", entry)
                if page_match:
                    title = f"Page {int(page_match.group(1))} steps"
                groups.append({"title": title, "images": images})
    else:
        images = []
        for img_name in sorted(entries):
            if not img_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            images.append({"name": img_name, "path": os.path.join(debug_dir, img_name)})
        if images:
            groups.append({"title": "Processing steps", "images": images})

    return groups


def job_progress_message(done: int, total: int, suffix: str) -> str:
    """Generate a friendly progress message for the UI."""
    if total:
        if suffix == ".pdf":
            if done >= total:
                return f"Finished all {total} pages"
            next_page = min(done + 1, total)
            return f"Processing page {next_page} of {total}"
        if done >= total:
            return "Processing complete"
        return f"Processed {done} of {total} items"
    if suffix == ".pdf":
        return "Preparing pages"
    return "Processing image"
