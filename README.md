# Skalu

<div align="center">
  <img src="https://wakatime.com/badge/user/a0b906ce-b8e7-4463-8bce-383238df6d4b/project/26c7c021-8f40-4bb9-aa97-ba8965462f2d.svg" alt="Wakatime badge" />
  <a href="https://colab.research.google.com/github/ragaeeb/skalu/blob/main/skalu.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab" /></a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/python-3.13-blue.svg" alt="Python: 3.13" />
  <img src="https://img.shields.io/badge/podman-v5.5.2-purple.svg" alt="Podman: v5.5.2" />
</div>

**Version 0.1.0**

Skalu is a computer-vision toolkit that detects horizontal lines and rectangles in PDFs and raster images. It powers both a Flask-powered asynchronous uploader as well as a polished Streamlit demo to showcase the detection results. The codebase follows the modern [`src/` layout](https://packaging.python.org/en/latest/discussions/src-layout/) and exposes reusable primitives for building your own document analysis workflows.

## Table of contents

1. [Live demos](#live-demos)
2. [Key features](#key-features)
3. [Project structure](#project-structure)
4. [Getting started](#getting-started)
5. [Usage](#usage)
6. [Testing](#testing)
7. [Deployment options](#deployment-options)
8. [Versioning](#versioning)
9. [Contributing](#contributing)
10. [License](#license)

## Live demos

| Experience | URL | Highlights |
| --- | --- | --- |
| Streamlit | [skaluapp.streamlit.app](http://skaluapp.streamlit.app/) | Upload PDFs or images, watch progress in real time, download JSON summaries, and review annotated visualisations. |
| Flask | `/` when running `app.py` locally | Async uploads, progress polling, and a responsive dashboard that mirrors the Streamlit experience for production hosting. |

> 💡 The Streamlit deployment is refreshed automatically from `main`. The package uses `setup.py` as the single source of truth for all dependencies.

## Key features

- **Structure detection** – Identify long horizontal lines and rectangular regions suitable for table/form extraction.
- **PDF + image support** – Process a single file, an entire folder of images, or each page of a PDF.
- **Batch friendly** – Uses tqdm-based progress reporting and optional callbacks for tight integration with other systems.
- **JSON outputs** – Persist detection results, DPI metadata, and the parameters used for repeatability.
- **Visual debugging** – Save annotated images that highlight the detected shapes.
- **Reusable package** – Import `skalu.processing` functions directly in your own applications.
- **CLI tool** – Installed as a `skalu` command for easy command-line usage.
- **Web front-ends** – Choose between Flask (WSGI friendly) and Streamlit (rapid prototyping) demos.
- **Automated versioning** – Uses semantic-release for automatic version management.

## Project structure

```text
.
├── AGENTS.md                # Repo conventions for AI assistants
├── LICENSE                  # MIT License
├── README.md
├── TESTING.md               # Comprehensive testing guide
├── app.py                   # WSGI entry point delegating to skalu.web.flask_app
├── streamlit_app.py         # Thin wrapper around skalu.web.streamlit_app
├── setup.py                 # Package configuration (single source of truth for dependencies)
├── pyproject.toml           # Build system and tool configuration (pytest, semantic-release)
├── requirements.txt         # Points to setup.py via -e .
├── requirements-test.txt    # Test dependencies via -e .[dev]
├── .github/
│   └── workflows/
│       ├── test.yml         # CI pipeline using uv and Python 3.13
│       └── release.yml      # Automatic semantic versioning
├── src/
│   └── skalu/
│       ├── __init__.py
│       ├── __version__.py   # Version number (auto-updated by semantic-release)
│       ├── processing.py    # Core detection + CLI
│       ├── demo_utils.py    # Shared utilities for web demos
│       └── web/
│           ├── __init__.py
│           ├── flask_app.py
│           ├── streamlit_app.py
│           └── templates/
│               └── index.html
└── tests/
    ├── conftest.py          # pytest configuration ensuring src/ is importable
    └── test_skalu.py        # pytest suite covering the public API
```

The `src/skalu` package is what gets installed when you run `pip install -e .`. Both the Flask and Streamlit entry points import from this package so they share logic with the CLI and test suite.

## Getting started

### Prerequisites

- Python 3.13+
- System packages for OpenCV (see `packages.txt` for the list)
- For PDF support ensure the system packages required by [PyMuPDF](https://pymupdf.readthedocs.io/) are available (they ship with wheels on most platforms).

### Installation

Clone and install the package in editable mode:

```bash
git clone https://github.com/ragaeeb/skalu.git
cd skalu
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

This installs all dependencies from `setup.py` (the single source of truth) and makes the `skalu` CLI command available.

For development with testing dependencies:

```bash
pip install -e .[dev]
```

Docker users can build an image that exposes the Flask demo and CLI tools:

```bash
docker build -t skalu .
docker run -p 10000:10000 skalu
```

## Usage

### Command-line interface

After installation, use the `skalu` command (installed via entry point in `setup.py`):

```bash
# Process a PDF
skalu document.pdf -o results.json

# Process an image
skalu image.jpg -o results.json

# Process a folder of images
skalu /path/to/images/ -o results.json

# With custom parameters
skalu input.pdf -o output.json \
  --min-width-ratio 0.3 \
  --max-height 15 \
  --min-rect-area 0.002 \
  --max-rect-area 0.6

# Save visualizations
skalu input.pdf -o output.json --save-viz

# Enable debug mode (saves intermediate processing steps)
skalu input.pdf -o output.json --debug-dir ./debug
```

Alternatively, you can still invoke via module:

```bash
python -m skalu.processing path/to/image.jpg
```

Useful flags:

- `--min-width-ratio` / `--max-height` to control the horizontal line detector.
- `--min-rect-area` / `--max-rect-area` to control rectangle detection.
- `--debug-dir` to persist intermediate masks for troubleshooting.
- `--save-viz` to emit annotated JPEGs next to your inputs.

### Python API

Import the functions directly for programmatic use:

```python
from skalu import process_pdf, process_single_image, detect_horizontal_lines, detect_rectangles

# Process a PDF with custom parameters
result = process_pdf(
    "document.pdf",
    "output.json",
    params={
        'min_line_width_ratio': 0.2,
        'max_line_height': 10,
        'min_rect_area_ratio': 0.001,
        'max_rect_area_ratio': 0.5
    },
    save_visualization=True,
    debug_dir="./debug"
)

# Process a single image
result = process_single_image(
    "sample.png",
    "sample_structures.json",
    save_visualization=True
)

# Process a folder
from skalu import process_folder
result = process_folder(
    "/path/to/images",
    "output.json",
    params={'min_line_width_ratio': 0.3}
)

# Use individual detection functions
import cv2
image = cv2.imread("image.jpg")

lines = detect_horizontal_lines(
    image,
    min_line_width_ratio=0.2,
    max_line_height=10,
    debug_dir="./debug"  # Optional: save intermediate steps
)

rectangles = detect_rectangles(
    image,
    min_rect_area_ratio=0.001,
    max_rect_area_ratio=0.5,
    debug_dir="./debug"  # Optional: save intermediate steps
)

# Draw detections on image
from skalu import draw_detections
annotated = draw_detections(image, lines, rectangles)
cv2.imwrite("annotated.jpg", annotated)

# Get DPI information
from skalu import get_image_dpi
dpi_x, dpi_y = get_image_dpi("image.jpg")

# Check version
import skalu
print(skalu.__version__)
```

The module exposes additional helpers such as `round3` for rounding to 3 decimal places.

### Web front-ends

Run the Flask application:

```bash
pip install -e .
python app.py
```

Or with gunicorn for production:

```bash
gunicorn app:app
```

Run the Streamlit experience locally:

```bash
pip install -e .
streamlit run streamlit_app.py
```

Both UIs upload documents, stream progress updates, and render summaries, annotated previews, and downloadable JSON without page refreshes.

## Testing

Install the testing dependencies and execute the suite with pytest:

```bash
pip install -e .[dev]
python -m pytest
```

For coverage reporting:

```bash
python -m pytest --cov=skalu --cov-report=term-missing --cov-report=html
```

The `tests/` folder uses fixtures defined in `tests/conftest.py` to simulate PDF/image processing without requiring heavyweight assets.

See [TESTING.md](./TESTING.md) for detailed testing documentation.

### Continuous Integration

GitHub Actions automatically runs tests on every push to `main` and on pull requests:
- Uses `uv` for fast dependency installation
- Tests against Python 3.13
- Generates coverage reports
- Uploads coverage to Codecov

## Deployment options

- **Render** – Deploy `app.py` behind gunicorn (`gunicorn app:app`) and set the `MAX_CONTENT_LENGTH` environment variable if you need to allow large uploads.
- **Streamlit Community Cloud** – Point the dashboard to `streamlit_app.py`; Streamlit installs from `requirements.txt` which references `setup.py` via `-e .`.
- **Docker** – The included `Dockerfile` uses the CLI entry point so you can process mounted volumes or run the Flask demo with `docker run -p 10000:10000 skalu`.

## Versioning

This project uses [Semantic Versioning](https://semver.org/) and [Conventional Commits](https://www.conventionalcommits.org/) with automated releases via `python-semantic-release`.

### Version Management

- Version is stored in `src/skalu/__version__.py`
- `setup.py` reads the version dynamically
- GitHub Actions automatically handles version bumps and releases

### Commit Message Format

Use conventional commits to trigger automatic version bumps:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature (triggers **minor** version bump: 0.1.0 → 0.2.0)
- `fix`: Bug fix (triggers **patch** version bump: 0.1.0 → 0.1.1)
- `perf`: Performance improvement (triggers **patch** version bump)
- `docs`: Documentation changes (no version bump)
- `style`: Code style changes (no version bump)
- `refactor`: Code refactoring (no version bump)
- `test`: Adding or updating tests (no version bump)
- `chore`: Maintenance tasks (no version bump)
- `ci`: CI/CD changes (no version bump)

**Breaking changes** trigger a **major** version bump (0.1.0 → 1.0.0):

```bash
feat!: change output JSON structure

BREAKING CHANGE: horizontal_lines now includes angle property
```

**Examples:**

```bash
# New feature (0.1.0 → 0.2.0)
git commit -m "feat: add support for TIFF images"

# Bug fix (0.1.0 → 0.1.1)
git commit -m "fix: correct DPI calculation for rotated PDFs"

# Performance improvement (0.1.0 → 0.1.1)
git commit -m "perf: optimize line detection algorithm"

# Breaking change (0.1.0 → 1.0.0)
git commit -m "feat!: restructure detection output format

BREAKING CHANGE: Detection results now use nested structure"
```

### Automatic Releases

When you push commits to `main`:

1. GitHub Actions analyzes your commit messages
2. Determines the appropriate version bump
3. Updates `src/skalu/__version__.py`
4. Creates a `CHANGELOG.md` entry
5. Creates a GitHub release with the new tag
6. Commits the version changes with `[skip ci]` to avoid triggering another build

To release manually:

```bash
pip install python-semantic-release
semantic-release version
semantic-release publish
```

## Output Format

The tool generates JSON output with detected structures:

**For PDFs:**
```json
{
  "pages": [
    {
      "page": 1,
      "width": 1224,
      "height": 1584,
      "horizontal_lines": [
        {
          "x": 100,
          "y": 200,
          "width": 800,
          "height": 2
        }
      ],
      "rectangles": [
        {
          "x": 150,
          "y": 300,
          "width": 400,
          "height": 200
        }
      ]
    }
  ],
  "dpi": {
    "x": 144.0,
    "y": 144.0
  },
  "detection_params": {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10,
    "min_rect_area_ratio": 0.001,
    "max_rect_area_ratio": 0.5
  }
}
```

**For images:**
```json
{
  "result": {
    "image.jpg": {
      "dpi": {
        "x": 300,
        "y": 300,
        "width": 800,
        "height": 600
      },
      "horizontal_lines": [...],
      "rectangles": [...]
    }
  },
  "detection_params": {...}
}
```

## Detection Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_line_width_ratio` | 0.2 | Minimum line width as fraction of image width (0.0-1.0) |
| `max_line_height` | 10 | Maximum line thickness in pixels |
| `min_rect_area_ratio` | 0.001 | Minimum rectangle area as fraction of image area |
| `max_rect_area_ratio` | 0.5 | Maximum rectangle area as fraction of image area |

## Contributing

Issues and pull requests are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes using conventional commit format
4. Run the test suite: `python -m pytest`
5. Push to the branch (`git push origin feat/amazing-feature`)
6. Open a Pull Request

The CI will automatically:
- Run tests on Python 3.13
- Check code coverage
- Validate your commits follow conventional format (for versioning)

Keep the README and documentation aligned with new functionality.

## Dependencies

All dependencies are managed in `setup.py` as the single source of truth:

**Core dependencies:**
- opencv-python-headless >= 4.10.0
- numpy >= 1.24.0
- pymupdf >= 1.23.0
- pillow >= 10.0.0
- tqdm >= 4.66.0
- flask >= 3.0.0
- werkzeug >= 3.0.0
- streamlit >= 1.29.0

**Dev dependencies** (installed with `pip install -e .[dev]`):
- pytest >= 7.0.0
- pytest-cov >= 3.0.0

## License

This project is licensed under the [MIT License](./LICENSE). and bounding boxes
- 📄 **PDF support** - Process multi-page PDF documents
- 🖼️ **Image support** - Handle PNG, JPG, JPEG, BMP, TIFF, WEBP formats
- 🐛 **Debug mode** - Optional visualization of detection steps
- 🌐 **Multiple interfaces** - CLI, Flask web app, and Streamlit app

## Installation

### From source

```bash
# Clone the repository
git clone https://github.com/yourusername/skalu.git
cd skalu

# Install in editable mode
pip install -e .
```

### Requirements

- Python 3.13+
- OpenCV
- NumPy
- PyMuPDF
- Pillow
- tqdm

## Usage

### Command Line Interface

After installation, use the `skalu` command:

```bash
# Process a PDF
skalu document.pdf -o results.json

# Process an image
skalu image.jpg -o results.json

# Process a folder of images
skalu /path/to/images/ -o results.json

# With custom parameters
skalu input.pdf -o output.json \
  --min-width-ratio 0.3 \
  --max-height 15 \
  --min-rect-area 0.002 \
  --max-rect-area 0.6

# Save visualizations
skalu input.pdf -o output.json --save-viz

# Enable debug mode (saves intermediate processing steps)
skalu input.pdf -o output.json --debug-dir ./debug
```

### Python API

```python
import skalu

# Process a PDF
result = skalu.process_pdf(
    "document.pdf",
    "output.json",
    params={
        'min_line_width_ratio': 0.2,
        'max_line_height': 10,
        'min_rect_area_ratio': 0.001,
        'max_rect_area_ratio': 0.5
    },
    save_visualization=True
)

# Process a single image
result = skalu.process_single_image(
    "image.jpg",
    "output.json",
    params={'min_line_width_ratio': 0.3}
)

# Process a folder
result = skalu.process_folder(
    "/path/to/images",
    "output.json"
)

# Use individual detection functions
import cv2
image = cv2.imread("image.jpg")

lines = skalu.detect_horizontal_lines(
    image,
    min_line_width_ratio=0.2,
    max_line_height=10
)

rectangles = skalu.detect_rectangles(
    image,
    min_rect_area_ratio=0.001,
    max_rect_area_ratio=0.5
)

# Draw detections on image
annotated = skalu.draw_detections(image, lines, rectangles)
```

### Web Interfaces

#### Flask Web App

```bash
# Run development server
python app.py

# Or with gunicorn (production)
gunicorn app:app
```

Then open http://localhost:5000 in your browser.

#### Streamlit App

```bash
streamlit run streamlit_app.py
```

Then open http://localhost:8501 in your browser.

## Output Format

The tool generates JSON output with detected structures:

```json
{
  "pages": [
    {
      "page": 1,
      "width": 1224,
      "height": 1584,
      "horizontal_lines": [
        {
          "x": 100,
          "y": 200,
          "width": 800,
          "height": 2
        }
      ],
      "rectangles": [
        {
          "x": 150,
          "y": 300,
          "width": 400,
          "height": 200
        }
      ]
    }
  ],
  "dpi": {
    "x": 144.0,
    "y": 144.0
  },
  "detection_params": {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10,
    "min_rect_area_ratio": 0.001,
    "max_rect_area_ratio": 0.5
  }
}
```

## Detection Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_line_width_ratio` | 0.2 | Minimum line width as fraction of image width (0.0-1.0) |
| `max_line_height` | 10 | Maximum line thickness in pixels |
| `min_rect_area_ratio` | 0.001 | Minimum rectangle area as fraction of image area |
| `max_rect_area_ratio` | 0.5 | Maximum rectangle area as fraction of image area |

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
python -m pytest

# Run with coverage
python -m pytest --cov=skalu --cov-report=html
```

### Project Structure

```
skalu/
├── src/
│   └── skalu/
│       ├── __init__.py
│       ├── __version__.py
│       ├── processing.py      # Core detection logic
│       ├── demo_utils.py      # Shared utilities
│       └── web/
│           ├── flask_app.py   # Flask web interface
│           ├── streamlit_app.py  # Streamlit interface
│           └── templates/     # HTML templates
├── tests/
│   ├── conftest.py
│   └── test_skalu.py
├── app.py                     # Flask entry point
├── streamlit_app.py          # Streamlit entry point
├── setup.py                   # Package configuration
└── requirements.txt           # Dependencies
```

## Versioning

This project uses [Semantic Versioning](https://semver.org/) and [Conventional Commits](https://www.conventionalcommits.org/).

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature (triggers minor version bump)
- `fix`: Bug fix (triggers patch version bump)
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

**Examples:**

```bash
# New feature (0.1.0 -> 0.2.0)
git commit -m "feat: add support for TIFF images"

# Bug fix (0.1.0 -> 0.1.1)
git commit -m "fix: correct DPI calculation for rotated PDFs"

# Breaking change (0.1.0 -> 1.0.0)
git commit -m "feat!: change output JSON structure

BREAKING CHANGE: horizontal_lines now includes angle property"
```

### Releasing

Releases are automatically created when you push to `main`:

1. Make your changes
2. Commit using conventional commit format
3. Push to main
4. GitHub Actions will:
   - Analyze commits
   - Determine version bump
   - Update version files
   - Create CHANGELOG
   - Create GitHub release with tag

To release manually:

```bash
pip install python-semantic-release
semantic-release version
semantic-release publish
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes using conventional commits
4. Push to the branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Uses OpenCV for image processing
- PyMuPDF for PDF rendering
- Flask and Streamlit for web interfaces** - Identify long, thin horizontal lines with configurable thresholds
- 📦 **Detect rectangles** - Find rectangular shapes