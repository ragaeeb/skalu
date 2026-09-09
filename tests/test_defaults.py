"""Regression tests for the public detection defaults."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import DEFAULT_DETECTION_PARAMS
from backend.models import DetectionParams
from demo_utils import DEFAULT_PARAMS
from skalu import DEFAULT_MIN_LINE_WIDTH_RATIO


def test_omitted_detection_options_use_the_core_public_default():
    expected = DEFAULT_MIN_LINE_WIDTH_RATIO

    assert DEFAULT_PARAMS["min_line_width_ratio"] == expected
    assert DEFAULT_DETECTION_PARAMS["min_line_width_ratio"] == expected
    assert DetectionParams.from_form({}).min_line_width_ratio == expected
