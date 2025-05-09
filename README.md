# skalu

<div align="center">
  <img src="https://wakatime.com/badge/user/a0b906ce-b8e7-4463-8bce-383238df6d4b/project/26c7c021-8f40-4bb9-aa97-ba8965462f2d.svg" />
  <a href="https://colab.research.google.com/github/ragaeeb/skalu/blob/main/skalu.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" /></a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/podman-v5.4.2-purple.svg" alt="Podman: v5.4.2" />
</div>

## Overview

Skalu is a Python tool for detecting horizontal lines and rectangles in images. It's particularly useful for document analysis, form processing, and table structure extraction. The tool uses computer vision techniques to identify structural elements and outputs structured data about their positions.

### Key Features

- **Structure Detection**: Identify horizontal lines and rectangles (including squares)
- **Single Image Processing**: Detect structures in individual images
- **Batch Processing**: Process entire folders of images at once
- **JSON Output**: Get structured data about detected elements
- **Visual Debugging**: Generate annotated images showing detected structures
- **Configurable Parameters**: Adjust detection sensitivity for different structure types
- **Docker Support**: Run anywhere with containerization
- **Google Colab Integration**: Process files in the cloud

## Installation

### Local Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/skalu.git
   cd skalu
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Docker Installation

```bash
# Build the Docker image
docker build -t skalu .

# Run the container with your images
docker run -v /path/to/your/images:/data skalu /data
```

## Usage

### Command Line Interface

```bash
# Process a single image
python skalu.py path/to/image.jpg

# Process a folder of images
python skalu.py path/to/folder/

# Specify custom output JSON path
python skalu.py path/to/image.jpg --output results.json

# Adjust detection parameters for lines
python skalu.py path/to/image.jpg --min-width-ratio 0.3 --max-height 15

# Adjust detection parameters for rectangles
python skalu.py path/to/image.jpg --min-rect-area 0.002 --max-rect-area 0.4
```

### Parameters

- **Line Detection**:

  - `--min-width-ratio`: Minimum width ratio of detected lines compared to image width (default: 0.2)
  - `--max-height`: Maximum height in pixels for a detected line (default: 10)

- **Rectangle Detection**:

  - `--min-rect-area`: Minimum rectangle area as a fraction of image area (default: 0.001)
  - `--max-rect-area`: Maximum rectangle area as a fraction of image area (default: 0.5)

- **General**:
  - `--output`, `-o`: Custom output path for results JSON
  - `--debug-dir`: Directory for storing intermediate processing images
  - `--save-viz`: Save visualization of detected structures

## Output Format

Skalu generates a JSON file with detailed information about the detected structures:

```json
{
  "result": {
    "example.jpg": {
      "dpi": {
        "width": 1240,
        "height": 1754,
        "x": 300,
        "y": 300
      },
      "horizontal_lines": [
        {
          "x": 120,
          "y": 350,
          "width": 1000,
          "height": 2
        },
        {
          "x": 120,
          "y": 700,
          "width": 1000,
          "height": 2
        }
      ],
      "rectangles": [
        {
          "x": 200,
          "y": 150,
          "width": 400,
          "height": 300
        },
        {
          "x": 650,
          "y": 450,
          "width": 250,
          "height": 250
        }
      ]
    }
  },
  "detection_params": {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10,
    "min_rect_area_ratio": 0.001,
    "max_rect_area_ratio": 0.5
  }
}
```

**Note**: The output only includes structure types (`horizontal_lines` or `rectangles`) that are actually detected in the image. If no structures of a particular type are found, that property will not appear in the output.

## Google Colab

You can use Skalu directly in Google Colab without any local installation:

1. Open the [Skalu Colab Notebook](https://colab.research.google.com/github/ragaeeb/skalu/blob/main/skalu.ipynb)
2. Upload your images using the file browser
3. Run the notebook to process all images
4. Download the results

## Examples

|                                    Input image                                    |                                      Detection result                                       |
| :-------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------: |
| ![Input image](https://via.placeholder.com/300x200/F5F5F5/CCCCCC?text=Input+Form) | ![Result image](https://via.placeholder.com/300x200/F5F5F5/CCCCCC?text=Detected+Structures) |

## Use Cases

- Extract table structures from scanned documents
- Process form fields by identifying separator lines and bounding boxes
- Detect paragraph/section divisions in documents
- Identify form field boxes and checkboxes
- Prepare images for OCR by understanding document layout
- Detect rectangular regions of interest in diagrams and charts

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
