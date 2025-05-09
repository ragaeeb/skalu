import cv2
import os
import sys
import json
import argparse
from tqdm import tqdm
from PIL import Image

def detect_horizontal_lines(image, min_line_width_ratio=0.2, max_line_height=10, debug_dir=None):
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
    # make the open‐kernel a bit smaller (80%) so broken/faint bars still survive erosion
    open_width = max(int(orig_min_width * 0.8), 1)
    horiz_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (open_width, 1))
    opened = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horiz_kern, iterations=1)

    # … then your usual contour‐find + filter:
    contours, _ = cv2.findContours(
        opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    lines = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        # *still* require the original minimum width
        if cw >= orig_min_width and ch <= max_line_height:
            lines.append({"x":x, "y":y, "width":cw, "height":ch})

    lines.sort(key=lambda L: L["y"])
    return lines

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

def draw_detections(image, horizontal_lines):
    """
    Creates a visual representation of detected horizontal lines.
    
    Args:
        image: Original image
        horizontal_lines: List of detected line dictionaries
        
    Returns:
        A copy of the original image with visual annotations of detected lines
    """
    debug = image.copy()
    for i, L in enumerate(horizontal_lines):
        x, y, w, h = L["x"], L["y"], L["width"], L["height"]
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(
            debug, f"#{i+1}",
            (x, y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA
        )
    return debug

def process_single_image(image_path, output_json_path, params=None, debug_dir=None, save_visualization=False):
    """
    Processes a single image to detect horizontal lines.
    
    Args:
        image_path: Path to the image file
        output_json_path: Path where the JSON results will be saved
        params: Dictionary of parameters for line detection
        debug_dir: Optional directory for debug images
        
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
    min_ratio = params.get('min_line_width_ratio', 0.2)
    max_h     = params.get('max_line_height', 10)

    lines = detect_horizontal_lines(img, min_ratio, max_h, debug_dir)

    result = {
        "result": {
            os.path.basename(image_path): {
                "dpi": {
                    "x": dpi_x,
                    "y": dpi_y,
                    "height": img.shape[0],
                    "width":  img.shape[1],
                },
                "horizontal_lines": lines
            }
        },
        "detection_params": {
            "min_line_width_ratio": min_ratio,
            "max_line_height": max_h
        }
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved detection for {image_path} → {output_json_path}")

    # Only save visualization if flag is set
    if save_visualization:
        debug_img = draw_detections(img, lines)
        dbg_path = os.path.splitext(output_json_path)[0] + "_detected.jpg"
        cv2.imwrite(dbg_path, debug_img)
        print(f"Saved visualization → {dbg_path}")

    return True

def process_folder(folder_path, output_json_path, params=None, debug_dir=None, save_visualization=False):
    """
    Processes all images in a folder to detect horizontal lines.
    
    Args:
        folder_path: Path to the folder containing images
        output_json_path: Path where the JSON results will be saved
        params: Dictionary of parameters for line detection
        debug_dir: Optional directory for debug images
        save_visualization: Whether to save visualization of detected lines
        
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

    min_ratio = params.get('min_line_width_ratio', 0.2)
    max_h = params.get('max_line_height', 10)

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

        # Pass the image-specific debug_dir to detect_horizontal_lines
        lines = detect_horizontal_lines(img, min_ratio, max_h, img_debug_dir)
        
        # Set basic image info
        result["result"][fn] = {
            "dpi": {
                "width":  img.shape[1],
                "height": img.shape[0],
            },
            "horizontal_lines": lines
        }
        
        # Only add x and y DPI values if they're not 0
        dpi_dict = result["result"][fn]["dpi"]
        if dpi_x != 0:
            dpi_dict["x"] = dpi_x
        if dpi_y != 0:
            dpi_dict["y"] = dpi_y

        # Only save visualization if flag is set
        if save_visualization:
            dbg = draw_detections(img, lines)
            dbg_fn = os.path.splitext(fn)[0] + "_detected.jpg"
            cv2.imwrite(os.path.join(folder_path, dbg_fn), dbg)

    # Add detection parameters to top level
    result["detection_params"] = {
        "min_line_width_ratio": min_ratio,
        "max_line_height": max_h
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
    parser = argparse.ArgumentParser(description="Skalu - Detect horizontal lines in images")
    parser.add_argument("input_path", help="Image file or folder")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument("--min-width-ratio", type=float, default=0.2,
                        help="Min line width as fraction of image width")
    parser.add_argument("--max-height", type=int, default=10,
                        help="Max line thickness in pixels")
    parser.add_argument("--debug-dir", default=None,
                        help="If set, dumps intermediate masks into this directory")
    parser.add_argument("--save-viz", action="store_true",
                        help="Save visualization of detected lines as images")
    args = parser.parse_args()

    params = {
        'min_line_width_ratio': args.min_width_ratio,
        'max_line_height':      args.max_height
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
        process_single_image(args.input_path, out, params, debug_dir=args.debug_dir, save_visualization=args.save_viz)
    elif os.path.isdir(args.input_path):
        process_folder(args.input_path, out, params, debug_dir=args.debug_dir, save_visualization=args.save_viz)
    else:
        print(f"Error: {args.input_path} is not valid")
        sys.exit(1)

if __name__ == "__main__":
    main()