"""Typed models for analyze options and detection parameters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .config import DEFAULT_DETECTION_PARAMS


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError("Expected a numeric value.") from exc


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError as exc:
        raise ValueError("Expected an integer value.") from exc


@dataclass(frozen=True)
class DetectionParams:
    min_line_width_ratio: float
    max_line_height: int
    min_rect_area_ratio: float
    max_rect_area_ratio: float

    @classmethod
    def from_form(cls, form: Mapping[str, str]) -> "DetectionParams":
        min_line_width_ratio = _parse_float(
            form.get("min_line_width_ratio"),
            float(DEFAULT_DETECTION_PARAMS["min_line_width_ratio"]),
        )
        max_line_height = _parse_int(
            form.get("max_line_height"),
            int(DEFAULT_DETECTION_PARAMS["max_line_height"]),
        )
        min_rect_area_ratio = _parse_float(
            form.get("min_rect_area_ratio"),
            float(DEFAULT_DETECTION_PARAMS["min_rect_area_ratio"]),
        )
        max_rect_area_ratio = _parse_float(
            form.get("max_rect_area_ratio"),
            float(DEFAULT_DETECTION_PARAMS["max_rect_area_ratio"]),
        )

        if not (0 < min_line_width_ratio <= 1):
            raise ValueError("min_line_width_ratio must be between 0 and 1.")
        if not (1 <= max_line_height <= 100):
            raise ValueError("max_line_height must be between 1 and 100.")
        if not (0 <= min_rect_area_ratio <= 1):
            raise ValueError("min_rect_area_ratio must be between 0 and 1.")
        if not (0 < max_rect_area_ratio <= 1):
            raise ValueError("max_rect_area_ratio must be between 0 and 1.")
        if min_rect_area_ratio > max_rect_area_ratio:
            raise ValueError("min_rect_area_ratio cannot be greater than max_rect_area_ratio.")

        return cls(
            min_line_width_ratio=min_line_width_ratio,
            max_line_height=max_line_height,
            min_rect_area_ratio=min_rect_area_ratio,
            max_rect_area_ratio=max_rect_area_ratio,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "DetectionParams":
        return cls(
            min_line_width_ratio=float(data["min_line_width_ratio"]),
            max_line_height=int(data["max_line_height"]),
            min_rect_area_ratio=float(data["min_rect_area_ratio"]),
            max_rect_area_ratio=float(data["max_rect_area_ratio"]),
        )

    def to_dict(self) -> dict:
        return {
            "min_line_width_ratio": self.min_line_width_ratio,
            "max_line_height": self.max_line_height,
            "min_rect_area_ratio": self.min_rect_area_ratio,
            "max_rect_area_ratio": self.max_rect_area_ratio,
        }


@dataclass(frozen=True)
class AnalyzeOptions:
    include_empty_pages: bool
    include_visualizations: bool
    stream: bool
    detection_params: DetectionParams

    @classmethod
    def from_form(cls, form: Mapping[str, str]) -> "AnalyzeOptions":
        return cls(
            include_empty_pages=parse_bool(form.get("include_empty_pages"), True),
            include_visualizations=parse_bool(form.get("include_visualizations"), False),
            stream=parse_bool(form.get("stream"), False),
            detection_params=DetectionParams.from_form(form),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "AnalyzeOptions":
        return cls(
            include_empty_pages=bool(data["include_empty_pages"]),
            include_visualizations=bool(data["include_visualizations"]),
            stream=bool(data["stream"]),
            detection_params=DetectionParams.from_dict(data["detection_params"]),
        )

    def to_dict(self) -> dict:
        return {
            "include_empty_pages": self.include_empty_pages,
            "include_visualizations": self.include_visualizations,
            "stream": self.stream,
            "detection_params": self.detection_params.to_dict(),
        }
