#!/bin/bash
set -e

# Function to process all images in a directory
process_directory() {
    INPUT_DIR=$1
    OUTPUT_JSON="${OUTPUT_DIR}/structures.json"
    echo "Processing all images in ${INPUT_DIR}"
    python /app/skalu.py "${INPUT_DIR}" --output "${OUTPUT_JSON}"
}

# Function to process a single image
process_single_image() {
    IMAGE_PATH=$1
    BASE_NAME=$(basename "$IMAGE_PATH" | cut -f 1 -d '.')
    OUTPUT_JSON="${OUTPUT_DIR}/${BASE_NAME}_structures.json"
    echo "Processing image ${IMAGE_PATH}"
    python /app/skalu.py "${IMAGE_PATH}" --output "${OUTPUT_JSON}"
}

# Allow running the web app directly via this helper script
start_web() {
    echo "Starting web server"
    exec gunicorn -b 0.0.0.0:${PORT:-10000} app:app
}

# Check command argument
case "$1" in
    all|'')
        process_directory "${INPUT_DIR}"
        ;;
    web)
        start_web
        ;;
    *)
        if [ -f "$1" ]; then
            process_single_image "$1"
        elif [ -d "$1" ]; then
            process_directory "$1"
        else
            echo "Usage:"
            echo "  docker run skalu all                   # Process all images in /data volume"
            echo "  docker run skalu /data/image.jpg       # Process specific image"
            echo "  docker run skalu /data/document.pdf    # Process specific document"
            echo "  docker run skalu /custom/folder        # Process all images in custom folder"
            echo "  docker run -p 10000:10000 skalu web    # Start the web demo"
            exit 1
        fi
        ;;
esac

# Fix permissions on output files
chmod -R 777 "${OUTPUT_DIR}"

echo "Processing complete! Results available in ${OUTPUT_DIR}"
