"""Single-shot analysis orchestration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from demo_utils import (
    build_summary,
    collect_debug_groups,
    collect_visualizations,
    encode_image_as_data_url,
)
from skalu import process_pdf, process_single_image

from ..errors import ProcessingError
from ..models import AnalyzeOptions


ProgressCallback = Callable[[int, int], None]


def run_analysis(workdir: str, filename: str, options: AnalyzeOptions, progress_callback: ProgressCallback | None = None) -> dict:
    """Run analysis for a single uploaded file and return the final payload."""
    suffix = Path(filename).suffix.lower()
    input_path = Path(workdir) / filename
    output_json_path = Path(workdir) / "results.json"
    debug_dir = Path(workdir) / "debug"

    params = options.detection_params.to_dict()
    if suffix == ".pdf":
        success = process_pdf(
            str(input_path),
            str(output_json_path),
            params=params,
            debug_dir=str(debug_dir),
            save_visualization=options.include_visualizations,
            progress_callback=progress_callback,
            include_empty_pages=options.include_empty_pages,
        )
    else:
        success = process_single_image(
            str(input_path),
            str(output_json_path),
            params=params,
            debug_dir=str(debug_dir),
            save_visualization=options.include_visualizations,
            progress_callback=progress_callback,
        )

    if not success:
        raise ProcessingError("Processing failed - please try another file.")

    with output_json_path.open("r", encoding="utf-8") as fh:
        result_data = json.load(fh)

    result_json = json.dumps(result_data, indent=4, ensure_ascii=False)
    summary = build_summary(result_data)

    visualizations = []
    debug_groups = []
    if options.include_visualizations:
        for viz in collect_visualizations(str(workdir)):
            data_url = encode_image_as_data_url(viz["path"])
            if data_url:
                visualizations.append({"label": viz["label"], "data_url": data_url})

        for group in collect_debug_groups(str(debug_dir)):
            images = []
            for image in group["images"]:
                data_url = encode_image_as_data_url(image["path"])
                if data_url:
                    images.append({"name": image["name"], "data_url": data_url})
            if images:
                debug_groups.append({"title": group["title"], "images": images})

    return {
        "result_json": result_json,
        "result_data": result_data,
        "summary": summary,
        "processed_filename": filename,
        "detection_params": result_data.get("detection_params") or params,
        "visualizations": visualizations,
        "debug_groups": debug_groups,
    }
