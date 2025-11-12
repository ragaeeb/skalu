# Testing Guide for Skalu

This document explains how to run the comprehensive unit tests for the Skalu project.

## Installation

Create a virtual environment with Python 3.13 and install the development
dependencies using [`uv`](https://github.com/astral-sh/uv):

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements_dev.txt
```

## Running Tests

### Run all tests

```bash
uv run pytest -v
```

### Run tests with coverage report

```bash
uv run pytest --cov=skalu --cov-report=html --cov-report=term
```

This will generate:
- Terminal coverage summary
- HTML coverage report in `htmlcov/index.html`

### Run specific test classes

```bash
# Test only horizontal line detection
uv run pytest tests/test_skalu.py::TestDetectHorizontalLines -v

# Test only rectangle detection
uv run pytest tests/test_skalu.py::TestDetectRectangles -v

# Test only PDF processing
uv run pytest tests/test_skalu.py::TestProcessPDF -v
```

### Run specific test methods

```bash
uv run pytest tests/test_skalu.py::TestDetectHorizontalLines::test_detect_single_line -v
```

### Run with verbose output

```bash
uv run pytest tests/test_skalu.py -vv
```

## Test Coverage

The test suite covers:

1. **Horizontal Line Detection** (`TestDetectHorizontalLines`)
   - Single line detection
   - No lines in blank images
   - Line width threshold filtering
   - Line height threshold filtering
   - Debug output generation
   - Grayscale image support

2. **Rectangle Detection** (`TestDetectRectangles`)
   - Rectangle detection
   - Square detection (as rectangles)
   - Area threshold filtering
   - Debug output generation
   - No rectangles in blank images

3. **Visualization** (`TestDrawDetections`)
   - Drawing horizontal lines
   - Drawing rectangles
   - Drawing both lines and rectangles
   - Handling empty detection lists

4. **DPI Extraction** (`TestGetImageDPI`)
   - Successful DPI extraction
   - Handling missing files

5. **Utility Functions** (`TestRound3`)
   - Rounding to 3 decimal places
   - Positive and negative numbers
   - Integer handling

6. **Single Image Processing** (`TestProcessSingleImage`)
   - Valid image processing
   - Non-existent file handling
   - Visualization generation
   - Debug output generation
   - Custom parameters
   - Progress callbacks

7. **Folder Processing** (`TestProcessFolder`)
   - Multiple image processing
   - Empty folder handling
   - Visualization generation

8. **PDF Processing** (`TestProcessPDF`)
   - Basic PDF processing (mocked)
   - Progress callbacks
   - Invalid file handling

9. **CLI Integration** (`TestCLIIntegration`)
   - Executes `python skalu.py` against `tests/test.pdf`
   - Compares the generated JSON with `tests/expected_test_results.json`

## Continuous Integration

To run tests in CI/CD pipelines, use:

```bash
uv run pytest --cov=skalu --cov-report=xml --cov-report=term
```

The XML report can be uploaded to code coverage services like Codecov or Coveralls.

## Writing New Tests

When adding new features to Skalu, follow these guidelines:

1. Create a new test class that inherits from `unittest.TestCase`
2. Use descriptive test method names starting with `test_`
3. Use `setUp()` to create test fixtures
4. Use `tearDown()` to clean up temporary files
5. Use assertions to verify expected behavior
6. Test both success and failure cases
7. Mock external dependencies (like PDF libraries) when needed

Example:

```python
class TestNewFeature(unittest.TestCase):
    def setUp(self):
        """Prepare test fixtures."""
        self.test_data = create_test_data()
    
    def tearDown(self):
        """Clean up after tests."""
        cleanup_test_data()
    
    def test_feature_works(self):
        """Test that the feature works correctly."""
        result = my_function(self.test_data)
        self.assertEqual(result, expected_value)
    
    def test_feature_handles_errors(self):
        """Test that the feature handles errors gracefully."""
        with self.assertRaises(ValueError):
            my_function(invalid_data)
```

## Troubleshooting

### ImportError: No module named 'skalu'

Make sure you're running tests from the project root directory where `skalu.py` is located.

### OpenCV errors

If you encounter OpenCV-related errors, ensure you have the required system libraries installed:

**Ubuntu/Debian:**
```bash
sudo apt-get install libgl1 libglib2.0-0
```

**macOS:**
```bash
brew install opencv
```

### Temporary file cleanup issues

If tests fail due to permission issues with temporary files, check that:
- You have write permissions in the temp directory
- No other processes are holding locks on test files
- The `tearDown()` methods are executing properly

## Test Metrics

Current test coverage target: **80%+**

To view detailed coverage:

```bash
uv run pytest --cov=skalu --cov-report=html
open htmlcov/index.html
```
