.PHONY: build run clean help

# Image name for Docker
IMAGE_NAME = skalu

help:
	@echo "Skalu - Horizontal Line Detection Tool"
	@echo ""
	@echo "Available commands:"
	@echo "  make build      Build the Docker image"
	@echo "  make run        Run the container to process images in ./input"
	@echo "  make clean      Remove output files and Docker containers"
	@echo "  make help       Show this help message"
	@echo ""
	@echo "To process a specific image:"
	@echo "  docker run -v $(PWD)/input:/data -v $(PWD)/output:/output $(IMAGE_NAME) /data/image.jpg"

build:
	@echo "Building Docker image..."
	@docker build -t $(IMAGE_NAME) .
	@echo "Image built successfully!"

run: build
	@echo "Creating input/output directories if they don't exist..."
	@mkdir -p input output
	@echo "Running the container to process all images in ./input..."
	@docker run --rm -v $(PWD)/input:/data -v $(PWD)/output:/output $(IMAGE_NAME) all
	@echo "Processing complete! Results available in ./output"

clean:
	@echo "Cleaning up..."
	@rm -rf output/*
	@docker rm -f $$(docker ps -a -q --filter ancestor=$(IMAGE_NAME) --format="{{.ID}}") 2>/dev/null || true
	@echo "Cleanup complete!"