"""WSGI entry point for running the Flask demo via ``python app.py`` or gunicorn."""
from skalu.web.flask_app import create_app, main

app = create_app()

if __name__ == "__main__":  # pragma: no cover - convenience execution
    main()
