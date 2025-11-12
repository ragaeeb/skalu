"""Setup configuration for the Skalu package."""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read version from __version__.py
version_file = Path(__file__).parent / "src" / "skalu" / "__version__.py"
version = {}
exec(version_file.read_text(), version)

setup(
    name="skalu",
    version=version["__version__"],
    description="Document analysis toolkit for detecting horizontal lines and rectangles in PDFs and images",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/ragaeeb/skalu",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "opencv-python-headless>=4.12.0.88",
        "numpy>=1.24.0",
        "pymupdf>=1.26.6",
        "pillow>=12.0.0",
        "tqdm>=4.66.0",
        "flask>=3.1.2",
        "werkzeug>=3.1.3",
        "streamlit>=1.51.0",
    ],
    extras_require={
        "dev": [
            "pytest>=9.0.0",
            "pytest-cov>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "skalu=skalu.processing:main",
        ],
    },
    python_requires=">=3.13",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
    ],
    include_package_data=True,
    package_data={
        "skalu.web": ["templates/*.html", "static/**/*"],
    },
)