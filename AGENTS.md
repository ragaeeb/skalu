# Agent Guidelines for the Skalu Repository

- Prefer the `src/` layout for imports. The main package lives under `src/skalu/`.
- Flask assets (templates, static files) live in `src/skalu/web/`. Keep HTML/CSS in that tree modern and accessible.
- Streamlit entry point is `src/skalu/web/streamlit_app.py`; avoid duplicating business logic there—share via `skalu.processing`.
- Tests rely on `pytest` and live in the `tests/` directory. When adding new modules, create matching test modules.
- Use `python -m pytest` (configured to discover tests under `tests/`).
- Documentation belongs primarily in `README.md` and module docstrings. Keep `README.md` aligned with the package capabilities and tooling.
- Requirements are managed in `requirements.txt` (runtime) and `requirements-test.txt` (testing). Make sure shared pins stay in sync.
