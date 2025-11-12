# Repository Guidelines

- Prefer using `pathlib.Path` for filesystem paths in tests and new Python code.
- Keep tests inside the `tests/` package and name them with the `test_*.py` pattern.
- Follow existing code style (PEP 8) and avoid introducing linting tools that are not already configured.
- When adding CLI functionality, expose it through `skalu.py` so the script remains the main entry point.
- Use [`uv`](https://github.com/astral-sh/uv) for dependency management. Install runtime packages with `uv pip install -r requirements.txt` and development tooling with `uv pip install -r requirements_dev.txt`.
- Run the automated test suite with `uv run pytest`; integration tests live alongside unit tests and are exercised by the same command.
