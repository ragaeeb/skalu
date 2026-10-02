FROM python:3.14.7-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /usr/local/bin/uv
WORKDIR /app/packages/engine
COPY packages/engine/pyproject.toml packages/engine/uv.lock ./
RUN uv sync --frozen --no-dev
COPY package.json /app/package.json
COPY packages/engine/skalu.py packages/engine/server.py ./
RUN useradd --create-home engine && chown -R engine /app
USER engine
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
EXPOSE 8080
CMD [".venv/bin/gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "180", "server:app"]
