import json
import os
import tempfile
from typing import Optional

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


@app.route("/", methods=["GET", "POST"])
def index():
    result_json = None
    result_data = None
    summary = None
    processed_filename = None

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
        temp_input_path = None
        temp_output_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_input:
                uploaded_file.save(temp_input.name)
                temp_input_path = temp_input.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_output:
                temp_output_path = temp_output.name

            params = DEFAULT_PARAMS.copy()

            if suffix == ".pdf":
                success = process_pdf(temp_input_path, temp_output_path, params=params)
            else:
                success = process_single_image(temp_input_path, temp_output_path, params=params)

            if not success:
                flash("Processing failed. Please try another file.", "error")
                return redirect(url_for("index"))

            result_data = load_results_from_path(temp_output_path)
            if result_data is None:
                return redirect(url_for("index"))

            result_json = json.dumps(result_data, indent=4, ensure_ascii=False)
            summary = build_summary(result_data)
            processed_filename = filename
        except Exception as exc:  # pylint: disable=broad-except
            app.logger.exception("Error while processing upload")
            flash(f"An unexpected error occurred: {exc}", "error")
            return redirect(url_for("index"))
        finally:
            if temp_input_path and os.path.exists(temp_input_path):
                os.remove(temp_input_path)
            if temp_output_path and os.path.exists(temp_output_path):
                os.remove(temp_output_path)

    return render_template(
        "index.html",
        result_json=result_json,
        result_data=result_data,
        summary=summary,
        processed_filename=processed_filename,
        detection_params=result_data.get("detection_params") if result_data else None,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
