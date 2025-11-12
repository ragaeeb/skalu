# Skalu

<div align="center">
  <img src="https://wakatime.com/badge/user/a0b906ce-b8e7-4463-8bce-383238df6d4b/project/26c7c021-8f40-4bb9-aa97-ba8965462f2d.svg" alt="Wakatime badge" />
  <a href="https://colab.research.google.com/github/ragaeeb/skalu/blob/main/skalu.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab" /></a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/podman-v5.5.2-purple.svg" alt="Podman: v5.5.2" />
</div>

Skalu is a computer-vision toolkit that detects horizontal lines and rectangles in PDFs and raster images. It powers both a Flask-powered asynchronous uploader as well as a polished Streamlit demo to showcase the detection results. The codebase now follows the modern [`src/` layout](https://packaging.python.org/en/latest/discussions/src-layout/) and exposes reusable primitives for building your own document analysis workflows.

## Table of contents

1. [Live demos](#live-demos)
2. [Key features](#key-features)
3. [Project structure](#project-structure)
4. [Getting started](#getting-started)
5. [Usage](#usage)
6. [Testing](#testing)
7. [Deployment options](#deployment-options)
8. [Contributing](#contributing)
9. [License](#license)

## Live demos

| Experience | URL | Highlights |
| --- | --- | --- |
| Streamlit | [skaluapp.streamlit.app](http://skaluapp.streamlit.app/) | Upload PDFs or images, watch progress in real time, download JSON summaries, and review annotated visualisations. |
| Flask | `/` when running `app.py` locally | Async uploads, progress polling, and a responsive dashboard that mirrors the Streamlit experience for production hosting. |

> 💡 The Streamlit deployment is refreshed automatically from `main`. If you fork the project, update the `requirements.txt` first so Streamlit installs the right stack.

## Key features

- **Structure detection** – Identify long horizontal lines and rectangular regions suitable for table/form extraction.
- **PDF + image support** – Process a single file, an entire folder of images, or each page of a PDF.
- **Batch friendly** – Uses tqdm-based progress reporting and optional callbacks for tight integration with other systems.
- **JSON outputs** – Persist detection results, DPI metadata, and the parameters used for repeatability.
- **Visual debugging** – Save annotated images that highlight the detected shapes.
- **Reusable package** – Import `skalu.processing` functions directly in your own applications.
- **Web front-ends** – Choose between Flask (WSGI friendly) and Streamlit (rapid prototyping) demos.

## Project structure

```text
.
├── AGENTS.md                # Repo conventions for AI assistants
├── LICENSE                  # MIT License
├── README.md
├── app.py                   # WSGI entry point delegating to skalu.web.flask_app
├── streamlit_app.py         # Thin wrapper around skalu.web.streamlit_app
├── requirements.txt         # Runtime dependencies
├── requirements-test.txt    # Test + runtime dependencies
├── pyproject.toml           # Package metadata and tool configuration
├── src/
│   └── skalu/
│       ├── __init__.py
│       ├── processing.py    # Core detection + CLI
│       └── web/
│           ├── __init__.py
│           ├── flask_app.py
│           ├── streamlit_app.py
│           └── templates/
│               └── index.html
└── tests/
    └── test_skalu.py        # pytest suite covering the public API
```

The `src/skalu` package is what gets installed when you run `pip install -e .`. Both the Flask and Streamlit entry points import from this package so they share logic with the CLI and test suite.

## Getting started

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) is optional; this project uses plain `pip` and `pyproject.toml` metadata.
- For PDF support ensure the system packages required by [PyMuPDF](https://pymupdf.readthedocs.io/) are available (they ship with wheels on most platforms).

### Installation

Clone and install the runtime dependencies:

```bash
git clone https://github.com/ragaeeb/skalu.git
cd skalu
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

To work on the package itself (editable mode) run:

```bash
pip install -e .
```

Docker users can build an image that exposes the Flask demo and CLI tools:

```bash
docker build -t skalu .
docker run -p 10000:10000 skalu
```

## Usage

### Command-line interface

The CLI lives inside `skalu.processing`. Invoke it with Python to process single files, PDFs, or entire folders:

```bash
python -m skalu.processing path/to/image.jpg
python -m skalu.processing path/to/document.pdf --save-viz
python -m skalu.processing path/to/folder/ -o ./output/structures.json
```

Useful flags:

- `--min-width-ratio` / `--max-height` to control the horizontal line detector.
- `--min-rect-area` / `--max-rect-area` to control rectangle detection.
- `--debug-dir` to persist intermediate masks for troubleshooting.
- `--save-viz` to emit annotated JPEGs next to your inputs.

### Python API

Import the functions directly for programmatic use:

```python
from skalu import process_pdf, process_single_image

process_single_image("sample.png", "sample_structures.json", save_visualization=True)
```

The module exposes additional helpers such as `detect_horizontal_lines`, `detect_rectangles`, `draw_detections`, and DPI utilities.

### Web front-ends

Run the Flask application:

```bash
pip install -r requirements.txt
FLASK_APP=app.py flask run
```

Run the Streamlit experience locally:

```bash
streamlit run streamlit_app.py
```

Both UIs upload documents, stream progress updates, and render summaries, annotated previews, and downloadable JSON without page refreshes.

## Testing

Install the testing dependencies and execute the suite with pytest:

```bash
pip install -r requirements-test.txt
python -m pytest
```

For coverage reporting:

```bash
python -m pytest --cov=skalu --cov-report=term-missing
```

The `tests/` folder uses fixtures defined in `tests/conftest.py` to simulate PDF/image processing without requiring heavyweight assets.

## Deployment options

- **Render** – Deploy `app.py` behind gunicorn (`gunicorn app:app`) and set the `MAX_CONTENT_LENGTH` environment variable if you need to allow large uploads.
- **Streamlit Community Cloud** – Point the dashboard to `streamlit_app.py`; Streamlit installs `requirements.txt` automatically.
- **Docker** – The included `Dockerfile` uses the CLI entry point so you can process mounted volumes or run the Flask demo with `docker run -p 10000:10000 skalu`.

## Contributing

Issues and pull requests are welcome. Please run the test suite and linters (if added) before submitting changes and keep the README aligned with new functionality.

## License

This project is licensed under the [MIT License](./LICENSE).
