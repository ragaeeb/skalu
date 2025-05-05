import cv2
import os
import sys
import json
import argparse
from tqdm import tqdm
from PIL import Image

def detect_horizontal_lines(image, min_line_width_ratio=0.2, max_line_height=10):
    """
    Detects only long, thin horizontal lines in an image.
    
    Args:
        image: Input image (BGR or grayscale)
        min_line_width_ratio: Minimum line width, as a fraction of image width
        max_line_height: Maximum allowed thickness of a line in pixels
        
    Returns:
        A sorted list of {"x","y","width","height"} dicts for each line
    """
    h, w = image.shape[:2]
    
    # -- 1) Grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # -- 2) Try a global Otsu threshold (inverted) so that black bars -> white
    _, bw = cv2.threshold(
        gray, 
        0, 
        255, 
        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    
    # -- 3) If absolutely nothing is found, fall back to adaptive threshold
    #    (e.g. for really uneven scans)
    #    We only switch if bw is almost empty.
    if cv2.countNonZero(bw) < 100:
        bw = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 
            15,  # block size
            8    # C
        )
    
    # -- 4) Morphological open with a *dynamic* horizontal kernel
    min_width = int(min_line_width_ratio * w)
    # kernel: very flat, wide enough to kill any run < min_width
    horiz_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (min_width, 1))
    opened = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horiz_kern, iterations=1)
    
    # -- 5) Find the remaining connected components (these are your bars)
    contours, _ = cv2.findContours(
        opened, 
        cv2.RETR_EXTERNAL, 
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    lines = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        # keep only sufficiently long, very thin strips
        if cw >= min_width and ch <= max_line_height:
            lines.append({
                "x": int(x),
                "y": int(y),
                "width": int(cw),
                "height": int(ch)
            })
    
    # sort top→bottom
    lines.sort(key=lambda L: L["y"])
    return lines

def get_image_dpi(image_path):
    try:
        with Image.open(image_path) as img:
            dpi = img.info.get('dpi', (0, 0))
            return int(dpi[0]), int(dpi[1])
    except Exception as e:
        print(f"Warning: Could not read DPI for {image_path}: {e}")
        return 0, 0

def draw_detections(image, horizontal_lines):
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

def process_single_image(image_path, output_json_path, params=None):
    if params is None:
        params = {}
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"Warning: Unable to load image at {image_path}")
        return False
    
    dpi_x, dpi_y = get_image_dpi(image_path)
    min_ratio = params.get('min_line_width_ratio', 0.2)
    max_h     = params.get('max_line_height', 10)
    
    lines = detect_horizontal_lines(img, min_ratio, max_h)
    
    result = {
        "image_info": {
            "path": image_path,
            "width":  img.shape[1],
            "height": img.shape[0],
            "dpi_x":  dpi_x,
            "dpi_y":  dpi_y
        },
        "detection_params": {
            "min_line_width_ratio": min_ratio,
            "max_line_height":     max_h
        },
        "horizontal_lines": lines,
        "line_count":       len(lines)
    }
    
    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved detection for {image_path} → {output_json_path}")
    
    debug_img = draw_detections(img, lines)
    dbg_path = os.path.splitext(output_json_path)[0] + "_detected.jpg"
    cv2.imwrite(dbg_path, debug_img)
    print(f"Saved visualization → {dbg_path}")
    
    return True

def process_folder(folder_path, output_json_path, params=None):
    if params is None:
        params = {}
    
    all_res = {}
    exts = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]
    imgs = sorted([f for f in os.listdir(folder_path)
                   if any(f.lower().endswith(e) for e in exts)])
    
    if not imgs:
        print(f"No supported images found in {folder_path}")
        return False
    
    print(f"Found {len(imgs)} images in {folder_path}")
    for fn in tqdm(imgs, desc="Processing"):
        path = os.path.join(folder_path, fn)
        img  = cv2.imread(path)
        if img is None:
            print(f"Warning: cannot read {fn}, skipping.")
            continue
        
        dpi_x, dpi_y = get_image_dpi(path)
        min_ratio = params.get('min_line_width_ratio', 0.2)
        max_h     = params.get('max_line_height', 10)
        
        lines = detect_horizontal_lines(img, min_ratio, max_h)
        all_res[fn] = {
            "image_info": {
                "path":   path,
                "width":  img.shape[1],
                "height": img.shape[0],
                "dpi_x":  dpi_x,
                "dpi_y":  dpi_y
            },
            "horizontal_lines": lines,
            "line_count":       len(lines)
        }
        
        dbg = draw_detections(img, lines)
        dbg_fn = os.path.splitext(fn)[0] + "_detected.jpg"
        cv2.imwrite(os.path.join(folder_path, dbg_fn), dbg)
    
    # summary
    all_res["_summary"] = {
        "total_images": len(imgs),
        "detection_params": {
            "min_line_width_ratio": params.get('min_line_width_ratio', 0.2),
            "max_line_height":     params.get('max_line_height', 10)
        }
    }
    
    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(all_res, f, indent=4, ensure_ascii=False)
    print(f"Saved all results → {output_json_path}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Skalu - Detect horizontal lines in images")
    parser.add_argument("input_path", help="Image file or folder")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument("--min-width-ratio", type=float, default=0.2,
                        help="Min line width as fraction of image width")
    parser.add_argument("--max-height", type=int, default=10,
                        help="Max line thickness in pixels")
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
        process_single_image(args.input_path, out, params)
    elif os.path.isdir(args.input_path):
        process_folder(args.input_path, out, params)
    else:
        print(f"Error: {args.input_path} is not valid")
        sys.exit(1)

if __name__ == "__main__":
    main()