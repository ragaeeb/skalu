# skalu 🎵➡️🎤

<div align="center">
  <img src="https://via.placeholder.com/600x200/2B3D4F/FFFFFF?text=Skalu+Line+Detection" alt="Skalu Banner">
  <img src="https://wakatime.com/badge/user/a0b906ce-b8e7-4463-8bce-383238df6d4b/project/26c7c021-8f40-4bb9-aa97-ba8965462f2d.svg" />
  <a href="https://colab.research.google.com/github/ragaeeb/skalu/blob/main/skalu.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" /></a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/podman-v5.4.2-purple.svg" alt="Podman: v5.4.2" />
</div>

## Overview

Skalu is a Python tool for detecting horizontal lines in images. It's particularly useful for document analysis, form processing, and table structure extraction. The tool uses computer vision techniques to identify horizontal lines and outputs structured data about their positions.

### Key Features

- **Single Image Processing**: Detect horizontal lines in individual images
- **Batch Processing**: Process entire folders of images at once
- **JSON Output**: Get structured data about detected lines
- **Visual Debugging**: Generate annotated images showing detected lines
- **Configurable Parameters**: Adjust detection sensitivity
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

# Adjust detection parameters
python skalu.py path/to/image.jpg --min-width-ratio 0.3 --max-height 15
```

### Parameters

- `--min-width-ratio`: Minimum width ratio of detected lines compared to image width (default: 0.2)
- `--max-height`: Maximum height in pixels for a detected line (default: 10)
- `--output`, `-o`: Custom output path for results JSON

## Output Format

Skalu generates a JSON file with detailed information about the detected lines:

```json
{
  "image_info": {
    "path": "example.jpg",
    "width": 1240,
    "height": 1754
  },
  "detection_params": {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10
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
  "line_count": 2
}
```

## Google Colab

You can use Skalu directly in Google Colab without any local installation:

1. Open the [Skalu Colab Notebook](https://colab.research.google.com/github/yourusername/skalu/blob/main/skalu.ipynb)
2. Upload your images using the file browser
3. Run the notebook to process all images
4. Download the results

## Examples

Input image | Detection result
:-------------------------:|:-------------------------:
![Input image](https://via.placeholder.com/300x200/F5F5F5/CCCCCC?text=Input+Form) | ![Result image](https://via.placeholder.com/300x200/F5F5F5/CCCCCC?text=Detected+Lines)

## Use Cases

- Extract table structures from scanned documents
- Process form fields by identifying separator lines
- Detect paragraph/section divisions in documents
- Prepare images for OCR by understanding document layout

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
