"""Unit tests for demo_utils.py helpers."""
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo_utils import collect_visualizations


class TestCollectVisualizations(unittest.TestCase):
    """Tests for visualization collection/sorting."""

    def test_collect_visualizations_sorts_by_numeric_page(self):
        """Ensure page visualizations are ordered by page number, not lexicographically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)

            (workdir / "sample_page_10_detected.jpg").touch()
            (workdir / "sample_page_2_detected.jpg").touch()
            (workdir / "sample_page_1_detected.jpg").touch()
            (workdir / "sample_detected.jpg").touch()
            (workdir / "ignore.txt").touch()

            visualizations = collect_visualizations(str(workdir))
            labels = [item["label"] for item in visualizations]

            self.assertEqual(
                labels,
                [
                    "Page 1 detections",
                    "Page 2 detections",
                    "Page 10 detections",
                    "Detections",
                ],
            )


if __name__ == "__main__":
    unittest.main()
