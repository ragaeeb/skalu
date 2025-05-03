import cv2
import os
import sys
import json
import argparse
from tqdm import tqdm

def detect_horizontal_lines(image, min_line_width_ratio=0.2, max_line_height=10):
    """
    Detects horizontal lines in an image.
    
    Args:
        image: The input image (BGR format)
        min_line_width_ratio: Minimum width ratio compared to image width (default: 0.2)
        max_line_height: Maximum height of a line in pixels (default: 10)
        
    Returns:
        A list of dictionaries containing line information
    """
    height, width = image.shape[:2]
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply adaptive thresholding for better results in varied lighting
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 11, -2)
    
    # Define horizontal kernel size based on image dimensions
    kernel_width = max(50, int(width * 0.05))
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    
    # Detect horizontal lines
    detect_horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    horizontal_lines = []
    min_width = int(min_line_width_ratio * width)
    
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > min_width and h <= max_line_height:
            horizontal_lines.append({
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h)
            })
    
    # Sort lines by vertical position
    horizontal_lines.sort(key=lambda line: line["y"])
    
    return horizontal_lines

def draw_detections(image, horizontal_lines):
    """
    Draw detected horizontal lines on a copy of the image.
    
    Args:
        image: The original image
        horizontal_lines: List of detected horizontal line data
        
    Returns:
        Image with visualized detections
    """
    debug_image = image.copy()
    
    # Draw horizontal lines in green
    for i, line in enumerate(horizontal_lines):
        x, y, w, h = line["x"], line["y"], line["width"], line["height"]
        cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Add line number label
        cv2.putText(debug_image, f"#{i+1}", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.5, (0, 0, 255), 1, cv2.LINE_AA)
    
    return debug_image

def process_single_image(image_path, output_json_path, params=None):
    """
    Process a single image to detect horizontal lines.
    
    Args:
        image_path: Path to the input image
        output_json_path: Path to save the results
        params: Dictionary of detection parameters (optional)
    
    Returns:
        True if successful, False otherwise
    """
    if params is None:
        params = {}
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Warning: Unable to load image at {image_path}")
        return False
    
    # Get detection parameters
    min_line_width_ratio = params.get('min_line_width_ratio', 0.2)
    max_line_height = params.get('max_line_height', 10)
    
    # Detect horizontal lines
    horizontal_lines = detect_horizontal_lines(
        image, 
        min_line_width_ratio=min_line_width_ratio,
        max_line_height=max_line_height
    )
    
    # Prepare result data
    result = {
        "image_info": {
            "path": image_path,
            "width": image.shape[1],
            "height": image.shape[0],
        },
        "detection_params": {
            "min_line_width_ratio": min_line_width_ratio,
            "max_line_height": max_line_height
        },
        "horizontal_lines": horizontal_lines,
        "line_count": len(horizontal_lines)
    }
    
    # Save JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    print(f"Saved detection for {image_path} to {output_json_path}")
    
    # Draw detections and save debug image
    debug_image = draw_detections(image, horizontal_lines)
    debug_image_path = os.path.splitext(output_json_path)[0] + "_detected.jpg"
    cv2.imwrite(debug_image_path, debug_image)
    print(f"Saved detection visualization to {debug_image_path}")
    
    return True

def process_folder(folder_path, output_json_path, params=None):
    """
    Process all images in a folder to detect horizontal lines.
    
    Args:
        folder_path: Path to the folder containing images
        output_json_path: Path to save the results
        params: Dictionary of detection parameters (optional)
    
    Returns:
        True if successful, False otherwise
    """
    if params is None:
        params = {}
    
    all_results = {}
    supported_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]
    
    # Get all image files
    image_files = []
    for filename in os.listdir(folder_path):
        if any(filename.lower().endswith(ext) for ext in supported_extensions):
            image_files.append(filename)
    
    if not image_files:
        print(f"No supported images found in {folder_path}")
        return False
    
    print(f"Found {len(image_files)} images to process")
    
    # Process each image with progress bar
    for filename in tqdm(sorted(image_files), desc="Processing images"):
        image_path = os.path.join(folder_path, filename)
        image = cv2.imread(image_path)
        
        if image is None:
            print(f"Warning: Unable to load image {filename}, skipping.")
            continue
        
        # Get detection parameters
        min_line_width_ratio = params.get('min_line_width_ratio', 0.2)
        max_line_height = params.get('max_line_height', 10)
        
        # Detect horizontal lines
        horizontal_lines = detect_horizontal_lines(
            image, 
            min_line_width_ratio=min_line_width_ratio,
            max_line_height=max_line_height
        )
        
        # Store results
        all_results[filename] = {
            "image_info": {
                "path": image_path,
                "width": image.shape[1],
                "height": image.shape[0],
            },
            "horizontal_lines": horizontal_lines,
            "line_count": len(horizontal_lines)
        }
        
        # Also save per-image debug visualization
        debug_image = draw_detections(image, horizontal_lines)
        debug_image_path = os.path.join(folder_path, f"{os.path.splitext(filename)[0]}_detected.jpg")
        cv2.imwrite(debug_image_path, debug_image)
    
    # Add summary information
    all_results["_summary"] = {
        "total_images": len(all_results) - 1,  # Subtract 1 for the _summary key
        "detection_params": {
            "min_line_width_ratio": params.get('min_line_width_ratio', 0.2),
            "max_line_height": params.get('max_line_height', 10)
        }
    }
    
    # Save JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)
    print(f"Saved all detections to {output_json_path}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Skalu - Detect horizontal lines in images")
    parser.add_argument("input_path", help="Path to an image file or folder")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--min-width-ratio", type=float, default=0.2,
                        help="Minimum line width as ratio of image width (default: 0.2)")
    parser.add_argument("--max-height", type=int, default=10,
                        help="Maximum line height in pixels (default: 10)")
    
    args = parser.parse_args()
    
    # Prepare parameters
    params = {
        'min_line_width_ratio': args.min_width_ratio,
        'max_line_height': args.max_height
    }
    
    # Determine output path if not specified
    output_json = args.output
    if not output_json:
        if os.path.isfile(args.input_path):
            base_name = os.path.splitext(os.path.basename(args.input_path))[0]
            output_json = os.path.join(os.path.dirname(args.input_path), f"{base_name}_structures.json")
        else:
            output_json = os.path.join(args.input_path, "structures.json")
    
    # Process based on input type
    if os.path.isfile(args.input_path):
        process_single_image(args.input_path, output_json, params)
    elif os.path.isdir(args.input_path):
        process_folder(args.input_path, output_json, params)
    else:
        print(f"Error: {args.input_path} is not a valid file or folder.")
        sys.exit(1)

if __name__ == "__main__":
    main()