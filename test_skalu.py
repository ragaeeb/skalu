"""Comprehensive unit tests for skalu.py"""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

import cv2
import numpy as np

# Import functions from skalu
from skalu import (
    detect_horizontal_lines,
    detect_rectangles,
    draw_detections,
    get_image_dpi,
    process_single_image,
    process_folder,
    process_pdf,
    round3,
)


class TestDetectHorizontalLines(unittest.TestCase):
    """Test horizontal line detection functionality."""

    def setUp(self):
        """Create test images for line detection."""
        # Create a simple white image with a black horizontal line
        self.img_with_line = np.ones((300, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(self.img_with_line, (50, 100), (350, 102), (0, 0, 0), -1)

        # Create an image without lines
        self.img_no_lines = np.ones((300, 400, 3), dtype=np.uint8) * 255

        # Create an image with a short line (below threshold)
        self.img_short_line = np.ones((300, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(self.img_short_line, (50, 100), (100, 102), (0, 0, 0), -1)

    def test_detect_single_line(self):
        """Test detection of a single horizontal line."""
        lines = detect_horizontal_lines(self.img_with_line, min_line_width_ratio=0.2)
        self.assertGreater(len(lines), 0, "Should detect at least one line")
        
        # Check that line properties are reasonable
        line = lines[0]
        self.assertIn("x", line)
        self.assertIn("y", line)
        self.assertIn("width", line)
        self.assertIn("height", line)
        self.assertGreater(line["width"], 200, "Line width should be substantial")

    def test_no_lines_detected(self):
        """Test that no lines are detected in a blank image."""
        lines = detect_horizontal_lines(self.img_no_lines)
        self.assertEqual(len(lines), 0, "Should detect no lines in blank image")

    def test_short_line_not_detected(self):
        """Test that short lines below threshold are not detected."""
        lines = detect_horizontal_lines(self.img_short_line, min_line_width_ratio=0.5)
        self.assertEqual(len(lines), 0, "Short line should not be detected with high threshold")

    def test_line_height_threshold(self):
        """Test max_line_height parameter."""
        # Create image with thick line
        img_thick = np.ones((300, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(img_thick, (50, 100), (350, 120), (0, 0, 0), -1)
        
        lines = detect_horizontal_lines(img_thick, max_line_height=5)
        self.assertEqual(len(lines), 0, "Thick line should not be detected with low max_height")

    def test_debug_output(self):
        """Test that debug images are saved when debug_dir is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detect_horizontal_lines(self.img_with_line, debug_dir=tmpdir)
            
            # Check that debug files were created
            debug_files = os.listdir(tmpdir)
            self.assertGreater(len(debug_files), 0, "Debug files should be created")
            self.assertTrue(
                any("step_01_gray" in f for f in debug_files),
                "Gray image should be in debug output"
            )

    def test_grayscale_input(self):
        """Test that function works with grayscale input."""
        gray_img = cv2.cvtColor(self.img_with_line, cv2.COLOR_BGR2GRAY)
        lines = detect_horizontal_lines(gray_img, min_line_width_ratio=0.2)
        self.assertGreater(len(lines), 0, "Should detect lines in grayscale image")


class TestDetectRectangles(unittest.TestCase):
    """Test rectangle detection functionality."""

    def setUp(self):
        """Create test images for rectangle detection."""
        # Create image with a rectangle
        self.img_with_rect = np.ones((400, 500, 3), dtype=np.uint8) * 255
        cv2.rectangle(self.img_with_rect, (100, 100), (300, 250), (0, 0, 0), 2)

        # Create image without rectangles
        self.img_no_rects = np.ones((400, 500, 3), dtype=np.uint8) * 255

        # Create image with very small rectangle
        self.img_small_rect = np.ones((400, 500, 3), dtype=np.uint8) * 255
        cv2.rectangle(self.img_small_rect, (100, 100), (105, 105), (0, 0, 0), 2)

    def test_detect_rectangle(self):
        """Test detection of a rectangle."""
        rects = detect_rectangles(self.img_with_rect, min_rect_area_ratio=0.001)
        self.assertGreater(len(rects), 0, "Should detect at least one rectangle")
        
        rect = rects[0]
        self.assertIn("x", rect)
        self.assertIn("y", rect)
        self.assertIn("width", rect)
        self.assertIn("height", rect)

    def test_no_rectangles_detected(self):
        """Test that no rectangles are detected in blank image."""
        rects = detect_rectangles(self.img_no_rects)
        self.assertEqual(len(rects), 0, "Should detect no rectangles in blank image")

    def test_area_thresholds(self):
        """Test min and max area ratio parameters."""
        # Test that small rectangle is filtered out with high min threshold
        rects = detect_rectangles(self.img_small_rect, min_rect_area_ratio=0.01)
        self.assertEqual(len(rects), 0, "Small rectangle should be filtered out")

    def test_debug_output(self):
        """Test that debug images are saved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detect_rectangles(self.img_with_rect, debug_dir=tmpdir)
            
            debug_files = os.listdir(tmpdir)
            self.assertGreater(len(debug_files), 0, "Debug files should be created")
            self.assertTrue(
                any("rect_" in f for f in debug_files),
                "Rectangle debug images should be created"
            )

    def test_square_detection(self):
        """Test that squares are detected as rectangles."""
        img_square = np.ones((400, 500, 3), dtype=np.uint8) * 255
        cv2.rectangle(img_square, (100, 100), (200, 200), (0, 0, 0), 2)
        
        rects = detect_rectangles(img_square, min_rect_area_ratio=0.001)
        self.assertGreater(len(rects), 0, "Should detect squares")


class TestDrawDetections(unittest.TestCase):
    """Test visualization functions."""

    def setUp(self):
        """Create test image and detection data."""
        self.img = np.ones((300, 400, 3), dtype=np.uint8) * 255
        self.lines = [{"x": 50, "y": 100, "width": 300, "height": 2}]
        self.rectangles = [{"x": 100, "y": 150, "width": 200, "height": 100}]

    def test_draw_lines_only(self):
        """Test drawing only horizontal lines."""
        result = draw_detections(self.img, horizontal_lines=self.lines)
        self.assertIsNotNone(result)
        self.assertEqual(result.shape, self.img.shape)
        # Image should be modified (not identical to input)
        self.assertFalse(np.array_equal(result, self.img))

    def test_draw_rectangles_only(self):
        """Test drawing only rectangles."""
        result = draw_detections(self.img, rectangles=self.rectangles)
        self.assertIsNotNone(result)
        self.assertEqual(result.shape, self.img.shape)

    def test_draw_both(self):
        """Test drawing both lines and rectangles."""
        result = draw_detections(self.img, self.lines, self.rectangles)
        self.assertIsNotNone(result)
        self.assertEqual(result.shape, self.img.shape)

    def test_draw_nothing(self):
        """Test that function works with no detections."""
        result = draw_detections(self.img)
        self.assertIsNotNone(result)
        # Should return a copy
        self.assertFalse(result is self.img)


class TestGetImageDPI(unittest.TestCase):
    """Test DPI extraction."""

    def test_get_dpi_no_file(self):
        """Test behavior with non-existent file."""
        dpi_x, dpi_y = get_image_dpi("/nonexistent/file.jpg")
        self.assertEqual(dpi_x, 0)
        self.assertEqual(dpi_y, 0)

    @patch("skalu.Image")
    def test_get_dpi_from_image(self, mock_image_class):
        """Test successful DPI extraction."""
        mock_img = MagicMock()
        mock_img.info = {"dpi": (300, 300)}
        mock_image_class.open.return_value.__enter__.return_value = mock_img
        
        dpi_x, dpi_y = get_image_dpi("test.jpg")
        self.assertEqual(dpi_x, 300)
        self.assertEqual(dpi_y, 300)


class TestRound3(unittest.TestCase):
    """Test the round3 utility function."""

    def test_round_positive(self):
        """Test rounding positive numbers."""
        self.assertEqual(round3(3.14159), 3.142)
        self.assertEqual(round3(2.5), 2.5)

    def test_round_negative(self):
        """Test rounding negative numbers."""
        self.assertEqual(round3(-3.14159), -3.142)

    def test_round_integer(self):
        """Test rounding integers."""
        self.assertEqual(round3(5), 5.0)

    def test_round_precision(self):
        """Test that exactly 3 decimal places are used."""
        result = round3(1.23456789)
        self.assertEqual(len(str(result).split('.')[1]), 3)


class TestProcessSingleImage(unittest.TestCase):
    """Test single image processing."""

    def setUp(self):
        """Create temporary directory and test image."""
        self.tmpdir = tempfile.mkdtemp()
        self.img_path = os.path.join(self.tmpdir, "test.png")
        self.output_path = os.path.join(self.tmpdir, "output.json")
        
        # Create a test image with a line
        img = np.ones((300, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 100), (350, 102), (0, 0, 0), -1)
        cv2.imwrite(self.img_path, img)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_process_valid_image(self):
        """Test processing a valid image."""
        success = process_single_image(self.img_path, self.output_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.output_path))
        
        # Check JSON structure
        with open(self.output_path, 'r') as f:
            result = json.load(f)
        
        self.assertIn("result", result)
        self.assertIn("detection_params", result)

    def test_process_nonexistent_image(self):
        """Test processing non-existent image."""
        success = process_single_image("/nonexistent.jpg", self.output_path)
        self.assertFalse(success)

    def test_process_with_visualization(self):
        """Test that visualization is saved when requested."""
        success = process_single_image(
            self.img_path,
            self.output_path,
            save_visualization=True
        )
        self.assertTrue(success)
        
        # Check for visualization file
        viz_path = self.output_path.replace(".json", "_detected.jpg")
        self.assertTrue(os.path.exists(viz_path))

    def test_process_with_debug_dir(self):
        """Test that debug images are saved."""
        debug_dir = os.path.join(self.tmpdir, "debug")
        success = process_single_image(
            self.img_path,
            self.output_path,
            debug_dir=debug_dir
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(debug_dir))
        self.assertGreater(len(os.listdir(debug_dir)), 0)

    def test_process_with_custom_params(self):
        """Test processing with custom detection parameters."""
        params = {
            'min_line_width_ratio': 0.1,
            'max_line_height': 20,
            'min_rect_area_ratio': 0.002,
            'max_rect_area_ratio': 0.6,
        }
        success = process_single_image(
            self.img_path,
            self.output_path,
            params=params
        )
        self.assertTrue(success)
        
        with open(self.output_path, 'r') as f:
            result = json.load(f)
        
        # Verify parameters were saved
        self.assertEqual(result["detection_params"]["min_line_width_ratio"], 0.1)

    def test_progress_callback(self):
        """Test that progress callback is called."""
        callback_calls = []
        
        def callback(done, total):
            callback_calls.append((done, total))
        
        success = process_single_image(
            self.img_path,
            self.output_path,
            progress_callback=callback
        )
        self.assertTrue(success)
        self.assertGreater(len(callback_calls), 0)


class TestProcessFolder(unittest.TestCase):
    """Test folder processing."""

    def setUp(self):
        """Create temporary directory with test images."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = os.path.join(self.tmpdir, "output.json")
        
        # Create multiple test images
        for i in range(3):
            img_path = os.path.join(self.tmpdir, f"test_{i}.png")
            img = np.ones((300, 400, 3), dtype=np.uint8) * 255
            cv2.rectangle(img, (50, 100), (350, 102), (0, 0, 0), -1)
            cv2.imwrite(img_path, img)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_process_folder(self):
        """Test processing a folder of images."""
        success = process_folder(self.tmpdir, self.output_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.output_path))
        
        with open(self.output_path, 'r') as f:
            result = json.load(f)
        
        self.assertIn("result", result)
        self.assertEqual(len(result["result"]), 3)

    def test_process_empty_folder(self):
        """Test processing empty folder."""
        empty_dir = tempfile.mkdtemp()
        try:
            success = process_folder(empty_dir, self.output_path)
            self.assertFalse(success)
        finally:
            os.rmdir(empty_dir)

    def test_process_folder_with_visualization(self):
        """Test folder processing with visualizations."""
        success = process_folder(
            self.tmpdir,
            self.output_path,
            save_visualization=True
        )
        self.assertTrue(success)
        
        # Check for visualization files
        viz_files = [f for f in os.listdir(self.tmpdir) if "_detected" in f]
        self.assertGreater(len(viz_files), 0)


class TestProcessPDF(unittest.TestCase):
    """Test PDF processing."""

    @patch("skalu.fitz")
    def test_process_pdf_basic(self, mock_fitz):
        """Test basic PDF processing with mocked PyMuPDF."""
        # Mock PDF document
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 2
        mock_fitz.open.return_value = mock_doc
        
        # Mock page
        mock_page = MagicMock()
        mock_page.mediabox = MagicMock(width=612, height=792)
        mock_page.cropbox = MagicMock(width=612, height=792)
        
        # Mock pixmap
        mock_pix = MagicMock()
        mock_pix.width = 1224
        mock_pix.height = 1584
        
        # Create a simple test image as PNG bytes
        test_img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        _, buffer = cv2.imencode('.png', test_img)
        mock_pix.tobytes.return_value = buffer.tobytes()
        
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.load_page.return_value = mock_page
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.json")
            success = process_pdf("test.pdf", output_path)
            
            self.assertTrue(success)
            self.assertTrue(os.path.exists(output_path))

    @patch("skalu.fitz")
    def test_process_pdf_with_progress(self, mock_fitz):
        """Test PDF processing with progress callback."""
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_fitz.open.return_value = mock_doc
        
        mock_page = MagicMock()
        mock_page.mediabox = MagicMock(width=612, height=792)
        mock_page.cropbox = MagicMock(width=612, height=792)
        
        mock_pix = MagicMock()
        mock_pix.width = 1224
        mock_pix.height = 1584
        test_img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        _, buffer = cv2.imencode('.png', test_img)
        mock_pix.tobytes.return_value = buffer.tobytes()
        
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.load_page.return_value = mock_page
        
        callback_calls = []
        
        def callback(done, total):
            callback_calls.append((done, total))
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.json")
            success = process_pdf(
                "test.pdf",
                output_path,
                progress_callback=callback
            )
            
            self.assertTrue(success)
            self.assertGreater(len(callback_calls), 0)

    def test_process_pdf_invalid_file(self):
        """Test processing invalid PDF file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.json")
            success = process_pdf("/nonexistent.pdf", output_path)
            self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()