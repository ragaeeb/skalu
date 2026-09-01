import cv2
import os
import sys
import json
import argparse
from tqdm import tqdm
from PIL import Image
import fitz  # PyMuPDF
import numpy as np

__version__ = "1.0.1"

DEFAULT_MIN_LINE_WIDTH_RATIO = 0.16


def _even_kernel_width(width):
    """Keep OpenCV morphology anchored consistently across kernel sizes."""
    return width + 1 if width > 1 and width % 2 == 1 else width


def _merge_collinear_line_fragments(fragments, max_gap):
    """Merge scan-broken horizontal fragments before applying the width cutoff."""
    merged = []
    for fragment in sorted(fragments, key=lambda line: (line["y"], line["x"])):
        fragment_right = fragment["x"] + fragment["width"]
        match = None
        for line in merged:
            line_bottom = line["y"] + line["height"]
            fragment_bottom = fragment["y"] + fragment["height"]
            vertical_overlap = min(line_bottom, fragment_bottom) - max(line["y"], fragment["y"])
            line_right = line["x"] + line["width"]
            horizontal_gap = max(fragment["x"] - line_right, line["x"] - fragment_right, 0)
            if vertical_overlap > 0 and horizontal_gap <= max_gap:
                match = line
                break

        if match is None:
            merged.append(fragment.copy())
            continue

        left = min(match["x"], fragment["x"])
        top = min(match["y"], fragment["y"])
        right = max(match["x"] + match["width"], fragment_right)
        bottom = max(match["y"] + match["height"], fragment["y"] + fragment["height"])
        match.update({"x": left, "y": top, "width": right - left, "height": bottom - top})

    return merged


def _is_thin_rotated_contour(contour, minimum_width, max_line_height):
    """Accept a lightly skewed rule whose axis-aligned box is slightly tall."""
    (_, _), (first_side, second_side), _ = cv2.minAreaRect(contour)
    thickness = min(first_side, second_side)
    length = max(first_side, second_side)
    return length >= minimum_width and thickness <= max_line_height


def _surrounding_ink_density(binary_image, line, band_height):
    """Measure whether a candidate is embedded in artwork instead of whitespace."""
    image_height, image_width = binary_image.shape[:2]
    x_start = max(0, line["x"])
    x_end = min(image_width, line["x"] + line["width"])
    y_start = max(0, line["y"])
    y_end = min(image_height, line["y"] + line["height"])
    above = binary_image[max(0, y_start - band_height):y_start, x_start:x_end]
    below = binary_image[y_end:min(image_height, y_end + band_height), x_start:x_end]
    bands = [band for band in (above, below) if band.size]
    if not bands:
        return 0.0
    return sum(float(np.count_nonzero(band)) / float(band.size) for band in bands) / len(bands)


def _consolidate_horizontal_candidates(lines, binary_image, max_line_height):
    """Merge one skewed rule and discard dense or multi-edge artwork clusters."""
    groups = []
    for candidate in sorted(lines, key=lambda line: (line["y"], line["x"])):
        candidate_right = candidate["x"] + candidate["width"]
        candidate_bottom = candidate["y"] + candidate["height"]
        matching_group = None
        for group in groups:
            group_right = max(line["x"] + line["width"] for line in group)
            group_bottom = max(line["y"] + line["height"] for line in group)
            group_left = min(line["x"] for line in group)
            group_top = min(line["y"] for line in group)
            horizontal_overlap = min(candidate_right, group_right) - max(candidate["x"], group_left)
            vertical_gap = max(candidate["y"] - group_bottom, group_top - candidate_bottom, 0)
            if horizontal_overlap > 0 and vertical_gap <= max_line_height:
                matching_group = group
                break

        if matching_group is None:
            groups.append([candidate])
        else:
            matching_group.append(candidate)

    consolidated = []
    for group in groups:
        left = min(line["x"] for line in group)
        top = min(line["y"] for line in group)
        right = max(line["x"] + line["width"] for line in group)
        bottom = max(line["y"] + line["height"] for line in group)
        vertical_span = bottom - top

        # A real rule may be lightly skewed, but multiple nearby frame/artwork
        # edges produce a much taller cluster.
        if len(group) > 1 and vertical_span > max_line_height * 1.5:
            continue

        line = {
            "x": left,
            "y": top,
            "width": right - left,
            "height": min(max_line_height, max(line["height"] for line in group)),
        }
        surrounding_ink_density = _surrounding_ink_density(binary_image, line, max_line_height + 2)
        is_wide_embedded_edge = line["width"] >= binary_image.shape[1] * 0.5 and surrounding_ink_density >= 0.15
        if surrounding_ink_density >= 0.65 or is_wide_embedded_edge:
            continue
        consolidated.append(line)

    paired_artwork = set()
    image_width = binary_image.shape[1]
    for first_index, first in enumerate(consolidated):
        for second_index in range(first_index + 1, len(consolidated)):
            second = consolidated[second_index]
            first_center_y = first["y"] + first["height"] / 2
            second_center_y = second["y"] + second["height"] / 2
            left, right = (first, second) if first["x"] <= second["x"] else (second, first)
            horizontal_gap = right["x"] - (left["x"] + left["width"])
            reference_width = max(first["width"], second["width"])
            similar_widths = abs(first["width"] - second["width"]) <= reference_width * 0.15
            if (
                abs(first_center_y - second_center_y) <= max_line_height
                and similar_widths
                and max_line_height < horizontal_gap <= image_width * 0.15
                and first["width"] + second["width"] >= image_width * 0.3
            ):
                paired_artwork.update((first_index, second_index))

    return [line for index, line in enumerate(consolidated) if index not in paired_artwork]


def detect_horizontal_lines(image, min_line_width_ratio=DEFAULT_MIN_LINE_WIDTH_RATIO, max_line_height=10, debug_dir=None):
    """
    Detects only long, thin horizontal lines in an image.
    
    This function identifies horizontal lines in an image based on specified criteria
    and optionally dumps intermediate processing steps to a debug directory.

    Args:
        image: Input image (BGR or grayscale)
        min_line_width_ratio: Minimum line width, as a fraction of image width
        max_line_height: Maximum allowed thickness of a line in pixels
        debug_dir: if not None, directory where intermediate steps will be saved

    Returns:
        A sorted list of {"x","y","width","height"} dicts for each detected line
    """
    h, w = image.shape[:2]

    # Prepare debug directory
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)

    # -- 1) Grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "step_01_gray.png"), gray)

    # -- 2) Global Otsu threshold (inverted) so that black bars -> white
    _, bw_otsu = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "step_02_otsu.png"), bw_otsu)

    # -- 3) Adaptive threshold (inverted), to catch faint lines
    bw_adapt = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15,  # block size
        8    # C
    )
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "step_03_adaptive.png"), bw_adapt)

    # -- 4) Union of Otsu + adaptive
    bw = cv2.bitwise_or(bw_otsu, bw_adapt)
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "step_04_union.png"), bw)

    # -- 5) Morphological open with a dynamic horizontal kernel
    orig_min_width = int(min_line_width_ratio * w)
    primary_reference_width = max(orig_min_width, int(w * 0.2))
    primary_open_width = _even_kernel_width(max(int(primary_reference_width * 0.8), 1))
    # A faint scan rule can contain several short surviving strokes even when
    # its full visual span exceeds the configured cutoff. Preserve smaller
    # collinear fragments here, then apply the full-width requirement after
    # merging them below.
    fragment_open_width = _even_kernel_width(max(int(orig_min_width * 0.25), 1))

    primary_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (primary_open_width, 1))
    fragment_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (fragment_open_width, 1))
    primary_opened = cv2.morphologyEx(bw, cv2.MORPH_OPEN, primary_kernel, iterations=1)
    fragment_opened = cv2.morphologyEx(bw, cv2.MORPH_OPEN, fragment_kernel, iterations=1)

    primary_contours, _ = cv2.findContours(
        primary_opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    fragment_contours, _ = cv2.findContours(
        fragment_opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    lines = []
    for c in primary_contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw >= orig_min_width and ch <= max_line_height:
            lines.append({"x": x, "y": y, "width": cw, "height": ch})

    fragments = []
    for c in fragment_contours:
        x, y, cw, ch = cv2.boundingRect(c)
        is_thin_rule = ch <= max_line_height or _is_thin_rotated_contour(
            c,
            fragment_open_width,
            max_line_height,
        )
        if cw >= fragment_open_width and is_thin_rule:
            fragments.append({"x": x, "y": y, "width": cw, "height": min(ch, max_line_height)})

    max_fragment_gap = max(max_line_height, int(w * 0.01))
    merged_fragment_lines = [
        line
        for line in _merge_collinear_line_fragments(fragments, max_fragment_gap)
        if line["width"] >= orig_min_width and line["height"] <= max_line_height
    ]

    for fragment_line in merged_fragment_lines:
        duplicates = [
            line
            for line in lines
            if abs(
                (line["y"] + line["height"] / 2)
                - (fragment_line["y"] + fragment_line["height"] / 2)
            ) <= max_line_height
            and min(line["x"] + line["width"], fragment_line["x"] + fragment_line["width"])
            - max(line["x"], fragment_line["x"]) > 0
        ]
        if not duplicates:
            lines.append(fragment_line)
        elif fragment_line["width"] > max(line["width"] for line in duplicates) + max_fragment_gap:
            for duplicate in duplicates:
                lines.remove(duplicate)
            lines.append(fragment_line)

    lines = _consolidate_horizontal_candidates(lines, bw_otsu, max_line_height)
    lines.sort(key=lambda L: L["y"])
    return lines

def detect_rectangles(image, min_rect_area_ratio=0.001, max_rect_area_ratio=0.5, debug_dir=None):
    """
    Detects rectangles (including squares) in an image.
    
    This function identifies rectangular shapes in an image based on specified criteria
    and optionally dumps intermediate processing steps to a debug directory.

    Args:
        image: Input image (BGR or grayscale)
        min_rect_area_ratio: Minimum rectangle area as a fraction of image area
        max_rect_area_ratio: Maximum rectangle area as a fraction of image area
        debug_dir: if not None, directory where intermediate steps will be saved

    Returns:
        A list of {"x","y","width","height"} dicts for each detected rectangle
    """
    h, w = image.shape[:2]
    img_area = h * w
    min_area = int(min_rect_area_ratio * img_area)
    max_area = int(max_rect_area_ratio * img_area)

    # Prepare debug directory
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)

    # -- 1) Grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "rect_01_gray.png"), gray)

    # -- 2) Edge detection
    edges = cv2.Canny(gray, 50, 150)
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "rect_02_edges.png"), edges)

    # -- 3) Dilate to connect edge segments
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=1)
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "rect_03_dilated.png"), dilated)

    # -- 4) Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rectangles = []
    for c in contours:
        # Calculate area and perimeter
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
            
        # Approximate the contour to simplify it
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        
        # If we have 4 points, it's likely a rectangle
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            # Exclude structures that are too thin (likely lines)
            if w > 5 and h > 5:  # Minimum size threshold
                rectangles.append({"x": x, "y": y, "width": w, "height": h})
    
    # Sort by area (largest first)
    rectangles.sort(key=lambda r: r["width"] * r["height"], reverse=True)
    return rectangles

def get_image_dpi(image_path):
    """
    Extracts DPI information from an image file.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        A tuple (dpi_x, dpi_y) containing the horizontal and vertical DPI values
    """
    try:
        with Image.open(image_path) as img:
            dpi = img.info.get('dpi', (0, 0))
            return int(dpi[0]), int(dpi[1])
    except Exception as e:
        print(f"Warning: Could not read DPI for {image_path}: {e}")
        return 0, 0

def draw_detections(image, horizontal_lines=None, rectangles=None):
    """
    Creates a visual representation of detected structures.
    
    Args:
        image: Original image
        horizontal_lines: List of detected line dictionaries (optional)
        rectangles: List of detected rectangle dictionaries (optional)
        
    Returns:
        A copy of the original image with visual annotations of detected structures
    """
    debug = image.copy()
    
    # Draw horizontal lines in green
    if horizontal_lines:
        for i, L in enumerate(horizontal_lines):
            x, y, w, h = L["x"], L["y"], L["width"], L["height"]
            cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                debug, f"Line #{i+1}",
                (x, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
                cv2.LINE_AA
            )
    
    # Draw rectangles in blue
    if rectangles:
        for i, R in enumerate(rectangles):
            x, y, w, h = R["x"], R["y"], R["width"], R["height"]
            cv2.rectangle(debug, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(
                debug, f"Rect #{i+1}",
                (x, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                1,
                cv2.LINE_AA
            )
    
    return debug

def round3(value):
    """
    Rounds a float value to exactly 3 decimal places.
    """
    return round(float(value), 3)

def process_pdf(
    pdf_path,
    output_json_path,
    params=None,
    debug_dir=None,
    save_visualization=False,
    progress_callback=None,
    include_empty_pages=False,
):
    """
    Processes a PDF file to detect horizontal lines and rectangles on each page.
    
    Args:
        include_empty_pages: If True, include all pages in results even if no 
                            structures were detected. Visualization will show original 
                            page image for empty pages.
    """
    if params is None:
        params = {}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error: Unable to open PDF at {pdf_path}: {e}")
        return False

    # Get parameters for detection
    min_line_ratio = params.get('min_line_width_ratio', DEFAULT_MIN_LINE_WIDTH_RATIO)
    max_line_h = params.get('max_line_height', 10)
    min_rect_area = params.get('min_rect_area_ratio', 0.001)
    max_rect_area = params.get('max_rect_area_ratio', 0.5)

    # Prepare debug directory if requested
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)

    pages = []
    
    # Variables to track DPI (calculated from first page)
    calculated_dpi_x = None
    calculated_dpi_y = None
    
    total_pages = len(doc)
    if progress_callback:
        try:
            progress_callback(0, total_pages)
        except Exception:
            pass

    print(f"Processing PDF with {total_pages} pages")
    for page_num in tqdm(range(total_pages), desc="Processing pages"):
        page = doc.load_page(page_num)
        
        # Get bounds
        crop_box = page.cropbox
        media_box = page.mediabox
        
        # Check if cropbox is empty or effectively same as mediabox
        crop_is_empty = (
            crop_box.width <= 0 or 
            crop_box.height <= 0 or
            crop_box == media_box
        )
        
        effective_bounds = media_box if crop_is_empty else crop_box
        
        print(f"Page {page_num + 1}: MediaBox={media_box}, CropBox={crop_box}, Using={effective_bounds}")

        scale = 2.0
        
        # Calculate render size
        render_width = max(1, effective_bounds.width * scale)
        render_height = max(1, effective_bounds.height * scale)
        
        # Use PyMuPDF's get_pixmap
        mat = fitz.Matrix(scale, scale)
        
        # DEBUG: Let's see what's happening with the bounds and clipping
        #print(f"DEBUG - Scale: {scale}")
        #print(f"DEBUG - EffectiveBounds: {effective_bounds}")
        #print(f"DEBUG - Matrix: {mat}")
        
        if crop_is_empty:
            # Use mediabox
            pix = page.get_pixmap(matrix=mat)
            #print(f"DEBUG - Using mediabox, no clip")
        else:
            # get_pixmap already respects the page's existing CropBox. Re-applying
            # PyMuPDF's transformed cropbox fails for MediaBoxes with non-zero origins.
            pix = page.get_pixmap(matrix=mat)
        
        # Get actual rendered dimensions
        actual_width = pix.width
        actual_height = pix.height
        
        #print(f"DEBUG - Pixmap irect: {pix.irect}")
        #print(f"DEBUG - Expected size: {render_width} x {render_height}")
        #print(f"DEBUG - Actual pixmap size: {actual_width} x {actual_height}")
        
        print(f"Render size: {render_width}x{render_height}, Actual: {actual_width}x{actual_height}")
        
        # Convert to numpy array for OpenCV
        img_data = pix.tobytes("png")
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Fallback path: build image from raw pixmap samples when PNG decode fails.
        if img is None:
            try:
                channels = int(getattr(pix, "n", 0) or 0)
                samples = np.frombuffer(pix.samples, dtype=np.uint8)
                expected_size = actual_width * actual_height * channels
                if channels in (1, 3, 4) and samples.size == expected_size:
                    raw = samples.reshape(actual_height, actual_width, channels)
                    if channels == 1:
                        img = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
                    elif channels == 3:
                        img = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
                    else:
                        img = cv2.cvtColor(raw, cv2.COLOR_RGBA2BGR)
            except Exception as e:
                print(f"Warning: Raw pixmap conversion failed for page {page_num + 1}: {e}")

        if img is None:
            print(f"Warning: Unable to decode rendered page {page_num + 1}")

            if include_empty_pages:
                pages.append(
                    {
                        "page": page_num + 1,
                        "width": actual_width,
                        "height": actual_height,
                        "processing_warning": "Unable to decode rendered page image",
                    }
                )

            if save_visualization:
                fallback_img = np.full((actual_height, actual_width, 3), 255, dtype=np.uint8)
                cv2.putText(
                    fallback_img,
                    "Unable to decode rendered page",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )
                viz_path = os.path.join(
                    os.path.dirname(output_json_path),
                    f"{os.path.splitext(os.path.basename(pdf_path))[0]}_page_{page_num + 1}_detected.jpg",
                )
                cv2.imwrite(viz_path, fallback_img)

            pix = None
            if progress_callback:
                try:
                    progress_callback(page_num + 1, total_pages)
                except Exception:
                    pass
            continue

        # Calculate DPI from first page only
        if calculated_dpi_x is None and calculated_dpi_y is None:
            # rawDpiX = Double(cgImg.width) / (Double(effectiveBounds.width) / 72.0)
            raw_dpi_x = float(actual_width) / (float(effective_bounds.width) / 72.0)
            raw_dpi_y = float(actual_height) / (float(effective_bounds.height) / 72.0)
            
            calculated_dpi_x = round3(raw_dpi_x)
            calculated_dpi_y = round3(raw_dpi_y)
            
            print(f"Calculated DPI: x={calculated_dpi_x}, y={calculated_dpi_y}")

        # Create page-specific debug directory if debug_dir is specified
        page_debug_dir = None
        if debug_dir:
            page_debug_dir = os.path.join(debug_dir, f"page_{page_num + 1}")
            os.makedirs(page_debug_dir, exist_ok=True)

        # Detect structures
        lines = detect_horizontal_lines(img, min_line_ratio, max_line_h, page_debug_dir)
        rectangles = detect_rectangles(img, min_rect_area, max_rect_area, page_debug_dir)
        
        # Include every page when requested; otherwise only include pages with detections.
        if include_empty_pages or lines or rectangles:
            # Create page result using actual rendered dimensions
            page_result = {
                "page": page_num + 1,
                "width": actual_width,
                "height": actual_height
            }

            # Add structures if they exist
            if lines:
                page_result["horizontal_lines"] = lines
            if rectangles:
                page_result["rectangles"] = rectangles

            pages.append(page_result)

        # Save visualization if requested - always save for each page
        if save_visualization:
            # If no structures detected, save original image; otherwise save with detections
            if lines or rectangles:
                debug_img = draw_detections(img, lines, rectangles)
            else:
                # Save original page image
                debug_img = img
            viz_path = os.path.join(os.path.dirname(output_json_path), 
                                   f"{os.path.splitext(os.path.basename(pdf_path))[0]}_page_{page_num + 1}_detected.jpg")
            cv2.imwrite(viz_path, debug_img)

        # Clean up pixmap
        pix = None

        if progress_callback:
            try:
                progress_callback(page_num + 1, total_pages)
            except Exception:
                pass

    doc.close()

    # Create result structure
    result = {
        "pages": pages,
        "dpi": {
            "x": calculated_dpi_x if calculated_dpi_x is not None else round3(144.0),
            "y": calculated_dpi_y if calculated_dpi_y is not None else round3(144.0)
        },
        "detection_params": {
            "min_line_width_ratio": min_line_ratio,
            "max_line_height": max_line_h,
            "min_rect_area_ratio": min_rect_area,
            "max_rect_area_ratio": max_rect_area
        }
    }

    # Save result to JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved PDF detection results → {output_json_path}")

    if progress_callback:
        try:
            progress_callback(total_pages, total_pages)
        except Exception:
            pass

    return True

def process_single_image(
    image_path,
    output_json_path,
    params=None,
    debug_dir=None,
    save_visualization=False,
    progress_callback=None,
):
    """
    Processes a single image to detect horizontal lines and rectangles.
    
    Args:
        image_path: Path to the image file
        output_json_path: Path where the JSON results will be saved
        params: Dictionary of parameters for structure detection
        debug_dir: Optional directory for debug images
        save_visualization: Whether to save visualization of detected structures
        
    Returns:
        Boolean indicating success or failure
    """
    if params is None:
        params = {}

    img = cv2.imread(image_path)
    if img is None:
        print(f"Warning: Unable to load image at {image_path}")
        return False

    # Prepare debug directory if requested
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)

    dpi_x, dpi_y = get_image_dpi(image_path)
    
    # Get parameters for detection
    min_line_ratio = params.get('min_line_width_ratio', DEFAULT_MIN_LINE_WIDTH_RATIO)
    max_line_h = params.get('max_line_height', 10)
    min_rect_area = params.get('min_rect_area_ratio', 0.001)
    max_rect_area = params.get('max_rect_area_ratio', 0.5)

    if progress_callback:
        try:
            progress_callback(0, 1)
        except Exception:
            pass

    # Detect structures
    lines = detect_horizontal_lines(img, min_line_ratio, max_line_h, debug_dir)
    rectangles = detect_rectangles(img, min_rect_area, max_rect_area, debug_dir)

    # Create base result dictionary
    result = {
        "result": {
            os.path.basename(image_path): {
                "dpi": {
                    "x": dpi_x,
                    "y": dpi_y,
                    "height": img.shape[0],
                    "width":  img.shape[1],
                }
            }
        },
        "detection_params": {
            "min_line_width_ratio": min_line_ratio,
            "max_line_height": max_line_h,
            "min_rect_area_ratio": min_rect_area,
            "max_rect_area_ratio": max_rect_area
        }
    }
    
    # Only add structures if they exist
    image_result = result["result"][os.path.basename(image_path)]
    if lines:
        image_result["horizontal_lines"] = lines
    if rectangles:
        image_result["rectangles"] = rectangles

    # Save result to JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved detection for {image_path} → {output_json_path}")

    # Only save visualization if flag is set
    if save_visualization:
        debug_img = draw_detections(img, lines, rectangles)
        dbg_path = os.path.splitext(output_json_path)[0] + "_detected.jpg"
        cv2.imwrite(dbg_path, debug_img)
        print(f"Saved visualization → {dbg_path}")

    if progress_callback:
        try:
            progress_callback(1, 1)
        except Exception:
            pass

    return True

def process_folder(folder_path, output_json_path, params=None, debug_dir=None, save_visualization=False):
    """
    Processes all images in a folder to detect horizontal lines and rectangles.
    
    Args:
        folder_path: Path to the folder containing images
        output_json_path: Path where the JSON results will be saved
        params: Dictionary of parameters for structure detection
        debug_dir: Optional directory for debug images
        save_visualization: Whether to save visualization of detected structures
        
    Returns:
        Boolean indicating success or failure
    """
    if params is None:
        params = {}

    result = {"result": {}}
    exts = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]
    imgs = sorted([f for f in os.listdir(folder_path)
                   if any(f.lower().endswith(e) for e in exts)])

    if not imgs:
        print(f"No supported images found in {folder_path}")
        return False

    # Get parameters for detection
    min_line_ratio = params.get('min_line_width_ratio', DEFAULT_MIN_LINE_WIDTH_RATIO)
    max_line_h = params.get('max_line_height', 10)
    min_rect_area = params.get('min_rect_area_ratio', 0.001)
    max_rect_area = params.get('max_rect_area_ratio', 0.5)

    print(f"Found {len(imgs)} images in {folder_path}")
    for fn in tqdm(imgs, desc="Processing"):
        path = os.path.join(folder_path, fn)
        img  = cv2.imread(path)
        if img is None:
            print(f"Warning: cannot read {fn}, skipping.")
            continue

        dpi_x, dpi_y = get_image_dpi(path)

        # Create image-specific debug directory if debug_dir is specified
        img_debug_dir = None
        if debug_dir:
            img_debug_dir = os.path.join(debug_dir, os.path.splitext(fn)[0])
            os.makedirs(img_debug_dir, exist_ok=True)

        # Detect structures
        lines = detect_horizontal_lines(img, min_line_ratio, max_line_h, img_debug_dir)
        rectangles = detect_rectangles(img, min_rect_area, max_rect_area, img_debug_dir)
        
        # Set basic image info
        result["result"][fn] = {
            "dpi": {
                "width":  img.shape[1],
                "height": img.shape[0],
            }
        }
        
        # Only add x and y DPI values if they're not 0
        dpi_dict = result["result"][fn]["dpi"]
        if dpi_x != 0:
            dpi_dict["x"] = dpi_x
        if dpi_y != 0:
            dpi_dict["y"] = dpi_y
            
        # Only add structures if they exist
        if lines:
            result["result"][fn]["horizontal_lines"] = lines
        if rectangles:
            result["result"][fn]["rectangles"] = rectangles

        # Only save visualization if flag is set
        if save_visualization:
            dbg = draw_detections(img, lines, rectangles)
            dbg_fn = os.path.splitext(fn)[0] + "_detected.jpg"
            cv2.imwrite(os.path.join(folder_path, dbg_fn), dbg)

    # Add detection parameters to top level
    result["detection_params"] = {
        "min_line_width_ratio": min_line_ratio,
        "max_line_height": max_line_h,
        "min_rect_area_ratio": min_rect_area,
        "max_rect_area_ratio": max_rect_area
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved all results → {output_json_path}")

    return True

def main():
    """
    Main function to parse command line arguments and process images.
    
    This function handles the command-line interface for the script, parses arguments,
    and calls the appropriate processing functions.
    """
    parser = argparse.ArgumentParser(description="Skalu - Detect horizontal lines and rectangles in images and PDFs")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("input_path", help="Image file, PDF file, or folder")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    
    # Line detection parameters
    parser.add_argument("--min-width-ratio", type=float, default=DEFAULT_MIN_LINE_WIDTH_RATIO,
                        help="Min line width as fraction of image width")
    parser.add_argument("--max-height", type=int, default=10,
                        help="Max line thickness in pixels")
    
    # Rectangle detection parameters                    
    parser.add_argument("--min-rect-area", type=float, default=0.001,
                        help="Min rectangle area as fraction of image area")
    parser.add_argument("--max-rect-area", type=float, default=0.5,
                        help="Max rectangle area as fraction of image area")
    
    # Debug and visualization options
    parser.add_argument("--debug-dir", default=None,
                        help="If set, dumps intermediate masks into this directory")
    parser.add_argument("--save-viz", action="store_true",
                        help="Save visualization of detected structures as images")
    args = parser.parse_args()

    params = {
        'min_line_width_ratio': args.min_width_ratio,
        'max_line_height': args.max_height,
        'min_rect_area_ratio': args.min_rect_area,
        'max_rect_area_ratio': args.max_rect_area
    }

    # auto‐choose output JSON
    out = args.output
    if not out:
        if os.path.isfile(args.input_path):
            base = os.path.splitext(os.path.basename(args.input_path))[0]
            out  = os.path.join(os.path.dirname(args.input_path), f"{base}_structures.json")
        else:
            out  = os.path.join(args.input_path, "structures.json")

    if os.path.isfile(args.input_path):
        # Check if it's a PDF
        if args.input_path.lower().endswith('.pdf'):
            process_pdf(args.input_path, out, params, debug_dir=args.debug_dir, save_visualization=args.save_viz)
        else:
            process_single_image(args.input_path, out, params, debug_dir=args.debug_dir, save_visualization=args.save_viz)
    elif os.path.isdir(args.input_path):
        process_folder(args.input_path, out, params, debug_dir=args.debug_dir, save_visualization=args.save_viz)
    else:
        print(f"Error: {args.input_path} is not valid")
        sys.exit(1)

if __name__ == "__main__":
    main()
