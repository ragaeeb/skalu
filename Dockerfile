FROM oven/bun:1.4.0 AS frontend-builder

WORKDIR /app/frontend
COPY frontend ./frontend

WORKDIR /app/frontend/frontend
RUN bun install --frozen-lockfile
RUN bun run build


FROM python:3.14-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libgl1 \
        libglib2.0-0 \
        libfreetype6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

COPY app.py demo_utils.py skalu.py pyproject.toml ./
COPY backend ./backend
COPY --from=frontend-builder /app/frontend/frontend/dist ./frontend/dist

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENV PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "app.py"]
