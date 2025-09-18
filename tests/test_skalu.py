import pathlib
import sys

import numpy as np

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import skalu


def make_blank(width=200, height=200):
    return np.full((height, width, 3), 255, dtype=np.uint8)


def draw_horizontal_line(image, y, x0, x1, thickness=3):
    for dy in range(-(thickness // 2), thickness // 2 + 1):
        row = y + dy
        if 0 <= row < image.shape[0]:
            image[row, x0:x1 + 1] = 0


def draw_rectangle(image, x0, y0, x1, y1, thickness=3):
    image[y0:y0 + thickness, x0:x1 + 1] = 0
    image[y1 - thickness + 1:y1 + 1, x0:x1 + 1] = 0
    image[y0:y1 + 1, x0:x0 + thickness] = 0
    image[y0:y1 + 1, x1 - thickness + 1:x1 + 1] = 0


def test_detect_horizontal_lines_finds_prominent_line():
    image = make_blank()
    draw_horizontal_line(image, 60, 10, 190, thickness=3)

    lines = skalu.detect_horizontal_lines(image, min_line_width_ratio=0.1, max_line_height=8)

    assert len(lines) == 1
    detected = lines[0]
    assert detected["width"] >= 160
    assert 50 <= detected["y"] <= 70
    assert detected["height"] <= 8


def test_detect_horizontal_lines_bridges_small_gap():
    image = make_blank()
    draw_horizontal_line(image, 100, 10, 130, thickness=3)
    draw_horizontal_line(image, 100, 134, 190, thickness=3)

    lines = skalu.detect_horizontal_lines(image, min_line_width_ratio=0.1, max_line_height=8)

    assert len(lines) == 1
    detected = lines[0]
    assert detected["width"] >= 160
    assert 90 <= detected["y"] <= 110


def test_detect_horizontal_lines_rejects_rectangle_edges():
    image = make_blank()
    draw_rectangle(image, 20, 30, 180, 150, thickness=3)

    lines = skalu.detect_horizontal_lines(image, min_line_width_ratio=0.1, max_line_height=12)

    assert lines == []


def test_detect_rectangles_finds_drawn_rectangle():
    image = make_blank()
    draw_rectangle(image, 40, 50, 160, 140, thickness=3)

    rectangles = skalu.detect_rectangles(image, min_rect_area_ratio=0.01, max_rect_area_ratio=0.9)

    assert len(rectangles) == 1
    rect = rectangles[0]
    assert rect["width"] >= 100
    assert rect["height"] >= 70


def test_get_image_dpi_reads_metadata(tmp_path):
    image_path = tmp_path / "dpi_image.png"
    from PIL import Image

    Image.new("RGB", (10, 10)).save(image_path, dpi=(144, 96))

    dpi_x, dpi_y = skalu.get_image_dpi(str(image_path))

    assert abs(dpi_x - 144) <= 1
    assert abs(dpi_y - 96) <= 1


def test_draw_detections_marks_lines_and_rectangles():
    image = make_blank()
    lines = [{"x": 10, "y": 20, "width": 100, "height": 2}]
    rectangles = [{"x": 50, "y": 60, "width": 40, "height": 30}]

    annotated = skalu.draw_detections(image, horizontal_lines=lines, rectangles=rectangles)

    assert (annotated[20, 10] == np.array([0, 255, 0])).all()
    assert (annotated[60, 50] == np.array([255, 0, 0])).all()


def test_round3_rounds_to_three_decimal_places():
    assert skalu.round3(1.23456) == 1.235
    assert skalu.round3(2) == 2.0
