"""Custom exceptions and API error helpers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApiError(Exception):
    message: str
    code: str
    status_code: int

    def to_dict(self) -> dict:
        return {"error": self.message, "code": self.code}


class BadRequestError(ApiError):
    def __init__(self, message: str):
        super().__init__(message=message, code="bad_input", status_code=400)


class ProcessingError(ApiError):
    def __init__(self, message: str = "Processing failed"):
        super().__init__(message=message, code="processing_error", status_code=500)


class AnalysisTimeoutError(ApiError):
    def __init__(self, message: str = "Analysis timed out"):
        super().__init__(message=message, code="timeout", status_code=504)
