# Agent Guidelines for the Skalu Repository

## Package Structure

- Prefer the `src/` layout for imports. The main package lives under `src/skalu/`.
- The package uses `setup.py` as the **single source of truth** for all dependencies.
- Version information is stored in `src/skalu/__version__.py` and read dynamically by `setup.py`.
- Flask assets (templates, static files) live in `src/skalu/web/`. Keep HTML/CSS in that tree modern and accessible.
- Streamlit entry point is `src/skalu/web/streamlit_app.py`; avoid duplicating business logic there—share via `skalu.processing`.

## Installation & Dependencies

- All runtime dependencies are defined in `setup.py` with minimum version constraints using `>=`.
- `requirements.txt` contains only `-e .` to install from `setup.py`.
- `requirements-test.txt` contains only `-e .[dev]` to install with dev extras (pytest, pytest-cov).
- **Never** duplicate dependency versions across files—`setup.py` is the single source of truth.
- To add a new dependency, add it to `install_requires` in `setup.py` only.
- To add a test/dev dependency, add it to `extras_require["dev"]` in `setup.py` only.

## CLI Entry Point

- The package installs a `skalu` CLI command via the `console_scripts` entry point in `setup.py`.
- The CLI maps to `skalu.processing:main`.
- Users can call `skalu` from anywhere after installing with `pip install -e .`.
- The older `python -m skalu.processing` pattern also works but `skalu` command is preferred.

## Testing

- Tests rely on `pytest` and live in the `tests/` directory.
- When adding new modules, create matching test modules.
- Use `python -m pytest` (configured to discover tests under `tests/`).
- Test configuration is in `pyproject.toml` under `[tool.pytest.ini_options]`.
- Run with coverage: `python -m pytest --cov=skalu --cov-report=term-missing`.
- The `tests/conftest.py` ensures the `src/` layout is importable during tests.

## Documentation

- Documentation belongs primarily in `README.md` and module docstrings.
- Keep `README.md` aligned with the package capabilities and tooling.
- Update `TESTING.md` when adding new test patterns or requirements.
- Version information in README is auto-updated by semantic-release.

## Versioning & Releases

- This project uses **semantic versioning** (semver) with automated releases.
- Version is stored in `src/skalu/__version__.py` and read by `setup.py`.
- Use **conventional commits** for all commits:
  - `feat:` triggers minor version bump (0.1.0 → 0.2.0)
  - `fix:` or `perf:` triggers patch version bump (0.1.0 → 0.1.1)
  - `feat!:` or `BREAKING CHANGE:` footer triggers major version bump (0.1.0 → 1.0.0)
  - Other types (`docs:`, `chore:`, `ci:`, `style:`, `refactor:`, `test:`) don't trigger releases
- GitHub Actions automatically handles version bumps and releases when pushing to `main`.
- The release workflow updates `__version__.py`, creates tags, generates CHANGELOG, and creates GitHub releases.
- Manual release: `semantic-release version && semantic-release publish`

### Conventional Commit Examples

```bash
# Feature (minor bump)
git commit -m "feat: add TIFF image support"

# Bug fix (patch bump)
git commit -m "fix: correct DPI calculation for landscape PDFs"

# Breaking change (major bump)
git commit -m "feat!: restructure JSON output format

BREAKING CHANGE: Changed structure of detection results"

# No release (documentation)
git commit -m "docs: update installation instructions"

# No release (chore)
git commit -m "chore: update dependencies"
```

## Continuous Integration

- CI uses GitHub Actions with **uv** for fast package installation.
- Target Python version: **3.13** only.
- Test workflow: `.github/workflows/test.yml`
  - Installs system dependencies from `packages.txt`
  - Uses `uv pip install --system -r requirements-test.txt`
  - Runs pytest with coverage
  - Uploads coverage to Codecov
- Release workflow: `.github/workflows/release.yml`
  - Triggered on push to `main`
  - Analyzes commits for version bumps
  - Updates version files
  - Creates releases and tags
  - Commits changes with `[skip ci]`

## Web Applications

### Flask App (`app.py`)
- Entry point: `app.py` imports `create_app` from `skalu.web.flask_app`
- Run development: `python app.py`
- Run production: `gunicorn app:app`
- Uses threading for async job processing
- Stores uploaded files in temp directories

### Streamlit App (`streamlit_app.py`)
- Entry point: `streamlit_app.py` imports `main` from `skalu.web.streamlit_app`
- Run: `streamlit run streamlit_app.py`
- Uses session state for managing analysis results
- Both apps share logic via `skalu.demo_utils` and `skalu.processing`

## Code Style & Patterns

- Use type hints where helpful but not strictly required.
- Keep functions focused and testable.
- Prefer composition over duplication—extract shared logic to `demo_utils.py`.
- When adding debug output, use the `debug_dir` parameter pattern consistently.
- Progress callbacks should accept `(done: int, total: int)` signature.
- Use descriptive variable names; avoid single-letter names except in tight loops (i, j).

## Common Tasks

### Adding a New Detection Feature

1. Add the core function to `src/skalu/processing.py`
2. Export it in `src/skalu/__init__.py`
3. Add CLI argument in `processing.py:main()` if needed
4. Write tests in `tests/test_skalu.py`
5. Update docstrings and README
6. Use conventional commit: `feat: add <feature>`

### Adding a New Dependency

1. Add to `install_requires` in `setup.py` with minimum version using `>=`
2. Test locally: `pip install -e .`
3. Verify CI passes
4. Never edit `requirements.txt` or `requirements-test.txt` directly

### Fixing a Bug

1. Write a failing test first
2. Fix the bug in the appropriate module
3. Verify test passes
4. Use conventional commit: `fix: <description>`
5. CI will automatically create a patch release

### Updating Documentation

1. Update `README.md` for user-facing changes
2. Update docstrings for API changes
3. Update `TESTING.md` for test-related changes
4. Use conventional commit: `docs: <description>`
5. No release will be triggered

## Important Notes

- **Do not commit `__pycache__`, `.pyc`, or virtual environments.**
- **Do not hardcode paths**—use `os.path.join()` or `pathlib.Path`.
- **Always handle exceptions** when reading files or processing images.
- **Clean up temp files** in finally blocks or context managers.
- **Test on both small and large files** to catch performance issues.
- **The `src/` layout requires installation**—always use `pip install -e .` for development.
- **Streamlit Cloud automatically installs from `requirements.txt`**, which installs from `setup.py`.
