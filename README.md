# skalu

<div align="center">
  <img src="https://wakatime.com/badge/user/a0b906ce-b8e7-4463-8bce-383238df6d4b/project/26c7c021-8f40-4bb9-aa97-ba8965462f2d.svg" />
  <a href="https://colab.research.google.com/github/ragaeeb/skalu/blob/main/skalu.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" /></a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/podman-v5.5.2-purple.svg" alt="Podman: v5.5.2" />
</div>

## Overview

Skalu is a Python tool for detecting horizontal lines and rectangles in images and PDFs. It's particularly useful for document analysis, form processing, and table structure extraction. The tool uses computer vision techniques to identify structural elements and outputs structured data about their positions.

### Key Features

- **Structure Detection**: Identify horizontal lines and rectangles (including squares)
- **Single Image Processing**: Detect structures in individual images
- **PDF Processing**: Extract structures from PDF documents page by page
- **Batch Processing**: Process entire folders of images at once
- **JSON Output**: Get structured data about detected elements
- **Smart Filtering**: Only include pages/images with detected structures
- **Visual Debugging**: Generate annotated images showing detected structures
- **Configurable Parameters**: Adjust detection sensitivity for different structure types
- **Docker Support**: Run anywhere with containerization
- **Google Colab Integration**: Process files in the cloud

## Web Demo

You can explore Skalu through a lightweight Flask web demo that accepts PDF and image uploads and shows the detected rectangles and horizontal lines.

- **Real-time feedback** – uploads run asynchronously so the page displays live progress as each page is analyzed.
- **Inline insights** – once finished, the app renders summaries, visualizations, debug frames, and a downloadable JSON payload without refreshing the page.

### Run the demo locally

```bash
pip install -r requirements.txt
FLASK_APP=app.py flask run
```

Then open <http://127.0.0.1:5000> in your browser, upload a document, and review the JSON output directly in the page. The demo now renders annotated visualizations, surfaces the intermediate debug frames when available, and lets you download the structured results as a JSON file with one click.

### Deploy to Render

1. Push this repository to your own GitHub account.
2. Create a new **Web Service** on [Render](https://render.com/) and connect it to your fork.
3. When prompted, enable the **Auto-detect settings from render.yaml** option.
4. Deploy. Render will run `pip install -r requirements.txt` and start the server with `gunicorn app:app`.

The default configuration limits uploads to 25&nbsp;MB to keep the demo responsive. Adjust the `MAX_CONTENT_LENGTH` environment variable in `render.yaml` if you need to allow larger files. The asynchronous upload workflow keeps requests short so long-running PDF analyses do not trip Render's worker timeout.

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

# Start the web demo on http://localhost:10000
docker run -p 10000:10000 skalu

# Run the batch processor against a mounted volume
docker run -v /path/to/your/images:/data skalu all

# Process a single file inside the container
docker run -v /path/to/your/file.pdf:/data/file.pdf skalu /data/file.pdf
```

## Usage

### Command Line Interface

```bash
# Process a single image
python skalu.py path/to/image.jpg

# Process a PDF document
python skalu.py path/to/document.pdf

# Process a folder of images
python skalu.py path/to/folder/

# Specify custom output JSON path
python skalu.py path/to/image.jpg --output results.json

# Process PDF with custom output filename
python skalu.py document.pdf -o pdf_results.json

# Adjust detection parameters for lines
python skalu.py path/to/image.jpg --min-width-ratio 0.3 --max-height 15

# Adjust detection parameters for rectangles
python skalu.py path/to/image.jpg --min-rect-area 0.002 --max-rect-area 0.4

# Generate debug images and visualizations
python skalu.py document.pdf --debug-dir debug_output --save-viz
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

### Image Processing

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

### PDF Processing

For PDF files, the output format includes page-by-page results:

```json
{
  "dpi": {
    "x": 200,
    "y": 200
  },
  "pages": [
    {
      "page": 1,
      "width": 1654,
      "height": 2339,
      "horizontal_lines": [
        {
          "x": 150,
          "y": 400,
          "width": 1200,
          "height": 3
        }
      ],
      "rectangles": [
        {
          "x": 200,
          "y": 150,
          "width": 400,
          "height": 300
        }
      ]
    },
    {
      "page": 3,
      "width": 1654,
      "height": 2339,
      "horizontal_lines": [
        {
          "x": 100,
          "y": 800,
          "width": 1400,
          "height": 2
        }
      ]
    }
  ],
  "detection_params": {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10,
    "min_rect_area_ratio": 0.001,
    "max_rect_area_ratio": 0.5
  }
}
```

**Notes**: 
- The output only includes structure types (`horizontal_lines` or `rectangles`) that are actually detected.
- For PDFs, only pages containing at least one horizontal line OR rectangle are included in the results.
- PDF pages are rendered at 200 DPI for high-quality structure detection.

## Google Colab

You can use Skalu directly in Google Colab without any local installation:

1. Open the [Skalu Colab Notebook](https://colab.research.google.com/github/ragaeeb/skalu/blob/main/skalu.ipynb)
2. Upload your images or PDFs using the file browser
3. Run the notebook to process all files
4. Download the results

## Use Cases

- Extract table structures from scanned documents and PDFs
- Process form fields by identifying separator lines and bounding boxes
- Detect paragraph/section divisions in documents
- Identify form field boxes and checkboxes in PDF forms
- Prepare images for OCR by understanding document layout
- Detect rectangular regions of interest in diagrams and charts
- Batch process multi-page PDF documents for structure analysis
- Filter PDF pages based on structural content

## Supported Formats

- **Images**: JPG, JPEG, PNG, BMP, TIFF, WebP
- **Documents**: PDF (multi-page support)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request