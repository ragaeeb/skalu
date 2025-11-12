"""Web front-ends for the Skalu demos."""

from .flask_app import create_app
from .streamlit_app import main as run_streamlit

__all__ = ["create_app", "run_streamlit"]
