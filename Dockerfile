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

COPY app.py demo_utils.py skalu.py ./

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENV PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["sh", "-c", "gunicorn --workers 1 --threads 8 --timeout 3600 --bind 0.0.0.0:${PORT} app:app"]
