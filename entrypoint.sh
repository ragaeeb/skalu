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

# Check command argument
if [ "$1" = "all" ]; then
    # Process all images in the input directory
    process_directory "${INPUT_DIR}"
elif [ -f "$1" ]; then
    # Process a single specified image file
    process_single_image "$1"
elif [ -d "$1" ]; then
    # Process all images in a specified directory
    process_directory "$1"
else
    echo "Usage:"
    echo "  docker run skalu all                   # Process all images in /data volume"
    echo "  docker run skalu /data/image.jpg       # Process specific image"
    echo "  docker run skalu /data/document.pdf       # Process specific document"
    echo "  docker run skalu /custom/folder        # Process all images in custom folder"
    exit 1
fi

# Fix permissions on output files
chmod -R 777 "${OUTPUT_DIR}"

echo "Processing complete! Results available in ${OUTPUT_DIR}"