"""Streamlit application for the Skalu document analyzer."""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
from typing import Dict, List

import streamlit as st
from PIL import Image
from werkzeug.utils import secure_filename

from skalu import process_pdf, process_single_image
from skalu.demo_utils import (
    ALLOWED_EXTENSIONS,
    DEFAULT_PARAMS,
    allowed_file,
    build_summary,
    collect_debug_groups,
    collect_visualizations,
    job_progress_message,
)


def _load_image_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _prepare_images_for_display(debug_groups: List[Dict[str, List[Dict[str, str]]]]):
    prepared_groups: List[Dict[str, List[Dict[str, object]]]] = []
    for group in debug_groups:
        images = []
        for image in group["images"]:
            try:
                data = _load_image_bytes(image["path"])
            except OSError:
                continue
            images.append({"name": image["name"], "bytes": data})
        if images:
            prepared_groups.append({"title": group["title"], "images": images})
    return prepared_groups


def _prepare_visualizations_for_display(visualizations: List[Dict[str, str]]):
    prepared_visuals: List[Dict[str, object]] = []
    for viz in visualizations:
        try:
            data = _load_image_bytes(viz["path"])
        except OSError:
            continue
        prepared_visuals.append({"label": viz["label"], "bytes": data})
    return prepared_visuals


def _run_analysis(uploaded_file) -> Dict[str, object]:
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    if not suffix:
        suffix = ".pdf" if uploaded_file.type == "application/pdf" else ""

    filename = secure_filename(uploaded_file.name) or f"upload{suffix or '.bin'}"

    workdir = tempfile.mkdtemp(prefix="skalu_streamlit_")
    input_path = os.path.join(workdir, filename)
    output_json_path = os.path.join(workdir, "results.json")
    debug_dir = os.path.join(workdir, "debug")

    with open(input_path, "wb") as handle:
        handle.write(uploaded_file.getbuffer())

    progress_placeholder = st.empty()
    progress_bar = st.progress(0.0)

    def progress_callback(done: int, total: int) -> None:
        message = job_progress_message(done, total, suffix)
        if total:
            progress_bar.progress(min(done / float(total), 1.0))
        else:
            progress_bar.progress(0.05)
        progress_placeholder.info(message)

    success = False
    try:
        if suffix == ".pdf":
            success = process_pdf(
                input_path,
                output_json_path,
                params=DEFAULT_PARAMS,
                debug_dir=debug_dir,
                save_visualization=True,
                progress_callback=progress_callback,
            )
        else:
            success = process_single_image(
                input_path,
                output_json_path,
                params=DEFAULT_PARAMS,
                debug_dir=debug_dir,
                save_visualization=True,
                progress_callback=progress_callback,
            )

        if not success:
            raise RuntimeError("Processing failed. Please try another file.")

        with open(output_json_path, "r", encoding="utf-8") as handle:
            result_data = json.load(handle)

        result_json = json.dumps(result_data, indent=4, ensure_ascii=False)
        summary = build_summary(result_data)
        debug_groups = _prepare_images_for_display(collect_debug_groups(debug_dir))
        visualizations = _prepare_visualizations_for_display(collect_visualizations(workdir))
        download_filename = f"{os.path.splitext(filename)[0]}_results.json"

        return {
            "result_json": result_json,
            "result_data": result_data,
            "summary": summary,
            "debug_groups": debug_groups,
            "visualizations": visualizations,
            "detection_params": result_data.get("detection_params"),
            "download_filename": download_filename,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> None:
    """Render the Streamlit experience."""
    st.set_page_config(page_title="Skalu Analyzer", layout="wide")

    st.title("Skalu Analyzer")
    st.caption("Detect rectangles and horizontal lines in PDFs or images with instant visual feedback.")

    with st.container():
        st.markdown("### Upload your document")
        st.write("Supported formats: PDF, PNG, JPG, JPEG, BMP, TIFF, WEBP")
        uploaded_file = st.file_uploader(
            "Choose a file to analyze",
            type=sorted(ALLOWED_EXTENSIONS),
            accept_multiple_files=False,
            label_visibility="collapsed",
        )

    if "analysis" not in st.session_state:
        st.session_state.analysis = None
        st.session_state.error = None

    analyze_disabled = uploaded_file is None

    analyze_button = st.button(
        "Analyze", type="primary", use_container_width=True, disabled=analyze_disabled
    )

    if analyze_button:
        st.session_state.analysis = None
        st.session_state.error = None
        if uploaded_file and allowed_file(uploaded_file.name):
            with st.spinner("Running analysis..."):
                try:
                    st.session_state.analysis = _run_analysis(uploaded_file)
                except Exception as exc:  # pylint: disable=broad-except
                    st.session_state.error = str(exc)
        else:
            st.session_state.error = "Please upload a supported PDF or image file."

    if st.session_state.error:
        st.error(st.session_state.error)

    analysis = st.session_state.analysis

    if not analysis:
        return

    st.success("Processing complete! Review the results below.")

    summary = analysis.get("summary") or {}
    is_pdf = summary.get("type") == "pdf"

    if is_pdf:
        pages = summary.get("pages", [])
        total_lines = sum(
            len(page.get("horizontal_lines", []))
            for page in analysis["result_data"].get("pages", [])
        )
        total_rectangles = sum(
            len(page.get("rectangles", [])) for page in analysis["result_data"].get("pages", [])
        )
        total_units = len(pages)
        unit_label = "Pages"
    else:
        items = summary.get("items", [])
        total_lines = sum(item.get("lines", 0) for item in items)
        total_rectangles = sum(item.get("rectangles", 0) for item in items)
        total_units = len(items) or (1 if analysis["result_data"].get("result") else 0)
        unit_label = "Images"

    columns = st.columns(3)
    with columns[0]:
        st.metric("Horizontal lines", total_lines)
    with columns[1]:
        st.metric("Rectangles", total_rectangles)
    with columns[2]:
        st.metric(unit_label, total_units)

    st.download_button(
        "Download JSON",
        data=analysis["result_json"].encode("utf-8"),
        file_name=analysis["download_filename"],
        mime="application/json",
        use_container_width=True,
    )

    st.markdown("### Summary")
    if summary:
        if summary["type"] == "pdf":
            st.table(summary["pages"])
        else:
            st.table(summary["items"])

    st.markdown("### Detection Parameters")
    st.json(analysis.get("detection_params", {}))

    st.markdown("### Visualizations")
    visuals = analysis.get("visualizations", [])
    if visuals:
        cols = st.columns(min(3, len(visuals)))
        for index, viz in enumerate(visuals):
            image = Image.open(io.BytesIO(viz["bytes"]))
            with cols[index % len(cols)]:
                st.image(image, caption=viz["label"], use_column_width=True)
    else:
        st.info("No visualization images were generated for this upload.")

    st.markdown("### Debug Frames")
    debug_groups = analysis.get("debug_groups", [])
    if debug_groups:
        for group in debug_groups:
            st.markdown(f"#### {group['title']}")
            cols = st.columns(min(3, len(group["images"])))
            for idx, image_info in enumerate(group["images"]):
                image = Image.open(io.BytesIO(image_info["bytes"]))
                with cols[idx % len(cols)]:
                    st.image(image, caption=image_info["name"], use_column_width=True)
    else:
        st.info("No debug frames were produced during processing.")

    st.markdown("### Full JSON Output")
    st.code(analysis["result_json"], language="json")


if __name__ == "__main__":  # pragma: no cover - convenience execution
    main()
