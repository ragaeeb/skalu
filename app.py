import base64
import json
import os
import re
import tempfile
from typing import Dict, List, Optional

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from skalu import process_pdf, process_single_image

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "bmp", "tiff", "webp"}

DEFAULT_PARAMS = {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10,
    "min_rect_area_ratio": 0.001,
    "max_rect_area_ratio": 0.5,
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "skalu-demo-secret")
# Limit uploads to 25 MB by default to keep demo responsive.
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_results_from_path(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        app.logger.exception("Failed to load results from %s", path)
        flash(f"Unable to load detection results: {exc}", "error")
        return None


def build_summary(data: dict) -> Optional[dict]:
    if not data:
        return None

    if "result" in data:
        items = []
        for name, info in data["result"].items():
            lines = len(info.get("horizontal_lines", []))
            rectangles = len(info.get("rectangles", []))
            items.append({
                "name": name,
                "lines": lines,
                "rectangles": rectangles,
                "dimensions": (
                    info.get("dpi", {}).get("width"),
                    info.get("dpi", {}).get("height"),
                ),
            })
        return {"type": "image", "items": items}

    if "pages" in data:
        pages = []
        for page in data["pages"]:
            pages.append({
                "page": page.get("page"),
                "lines": len(page.get("horizontal_lines", [])),
                "rectangles": len(page.get("rectangles", [])),
                "size": (page.get("width"), page.get("height")),
            })
        return {"type": "pdf", "pages": pages}

    return None


def encode_image_as_data_url(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as file:
            encoded = base64.b64encode(file.read()).decode("ascii")
    except OSError:
        app.logger.warning("Unable to read debug image %s", path)
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
    visualizations: List[Dict[str, str]] = []
    if not os.path.isdir(workdir):
        return visualizations

    for name in sorted(os.listdir(workdir)):
        if not name.lower().endswith(("_detected.jpg", "_detected.jpeg", "_detected.png", "_detected.webp")):
            continue

        path = os.path.join(workdir, name)
        data_url = encode_image_as_data_url(path)
        if not data_url:
            continue

        label = "Detections"
        page_match = re.search(r"_page_(\d+)_", name)
        if page_match:
            label = f"Page {int(page_match.group(1))} detections"
        elif "page" in name.lower():
            label = name.rsplit("_detected", 1)[0]

        visualizations.append({"label": label, "data_url": data_url})

    return visualizations


def collect_debug_groups(debug_dir: str) -> List[Dict[str, List[Dict[str, str]]]]:
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
                data_url = encode_image_as_data_url(os.path.join(entry_path, img_name))
                if data_url:
                    images.append({"name": img_name, "data_url": data_url})

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
            data_url = encode_image_as_data_url(os.path.join(debug_dir, img_name))
            if data_url:
                images.append({"name": img_name, "data_url": data_url})
        if images:
            groups.append({"title": "Processing steps", "images": images})

    return groups


@app.route("/", methods=["GET", "POST"])
def index():
    result_json = None
    result_data = None
    summary = None
    processed_filename = None
    debug_groups = []
    visualizations = []
    download_filename = None

    if request.method == "POST":
        uploaded_file = request.files.get("file")

        if not uploaded_file or uploaded_file.filename == "":
            flash("Please choose a PDF or image file to analyze.", "error")
            return redirect(url_for("index"))

        filename = secure_filename(uploaded_file.filename)
        if not allowed_file(filename):
            flash("Unsupported file type. Please upload a PDF or common image format.", "error")
            return redirect(url_for("index"))

        suffix = os.path.splitext(filename)[1].lower()

        params = DEFAULT_PARAMS.copy()

        try:
            with tempfile.TemporaryDirectory() as workdir:
                input_path = os.path.join(workdir, filename)
                uploaded_file.save(input_path)

                output_json_path = os.path.join(workdir, "results.json")
                debug_dir = os.path.join(workdir, "debug")

                if suffix == ".pdf":
                    success = process_pdf(
                        input_path,
                        output_json_path,
                        params=params,
                        debug_dir=debug_dir,
                        save_visualization=True,
                    )
                else:
                    success = process_single_image(
                        input_path,
                        output_json_path,
                        params=params,
                        debug_dir=debug_dir,
                        save_visualization=True,
                    )

                if not success:
                    flash("Processing failed. Please try another file.", "error")
                    return redirect(url_for("index"))

                result_data = load_results_from_path(output_json_path)
                if result_data is None:
                    return redirect(url_for("index"))

                result_json = json.dumps(result_data, indent=4, ensure_ascii=False)
                summary = build_summary(result_data)
                processed_filename = filename
                debug_groups = collect_debug_groups(debug_dir)
                visualizations = collect_visualizations(workdir)
                download_filename = f"{os.path.splitext(filename)[0]}_results.json"
        except Exception as exc:  # pylint: disable=broad-except
            app.logger.exception("Error while processing upload")
            flash(f"An unexpected error occurred: {exc}", "error")
            return redirect(url_for("index"))

    return render_template(
        "index.html",
        result_json=result_json,
        result_data=result_data,
        summary=summary,
        processed_filename=processed_filename,
        detection_params=result_data.get("detection_params") if result_data else None,
        debug_groups=debug_groups,
        visualizations=visualizations,
        download_filename=download_filename,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
