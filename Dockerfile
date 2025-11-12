FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy dependency manifests first to leverage Docker cache
COPY requirements.txt requirements_dev.txt ./

# Install system and Python dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libfreetype6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv pip install --system -r requirements.txt

ENV PATH="/root/.local/bin:${PATH}"

# Copy the rest of the application code
COPY . .

# Ensure data directories exist for optional batch processing
ENV INPUT_DIR=/data \
    OUTPUT_DIR=/output \
    PYTHONUNBUFFERED=1
RUN mkdir -p "$INPUT_DIR" "$OUTPUT_DIR" && \
    chmod +x /app/entrypoint.sh

# Expose the port Render assigns (defaults to 10000 locally)
EXPOSE 10000

# Use the helper script so the container can run either the CLI or the web demo
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
