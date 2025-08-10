FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libfreetype6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY skalu.py .
COPY README.md .

# Create directories
RUN mkdir -p /data /output

# Set default environment variables
ENV INPUT_DIR=/data
ENV OUTPUT_DIR=/output

# Create entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command processes all images in the input directory
# This can be overridden by docker run command
CMD ["all"]