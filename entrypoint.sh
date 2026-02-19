#!/bin/bash
set -e

process_directory() {
    local input_dir=$1
    local output_json="${OUTPUT_DIR:-/output}/structures.json"
    echo "Processing all images in ${input_dir}"
    python /app/skalu.py "${input_dir}" --output "${output_json}"
}

process_single() {
    local file_path=$1
    local base_name
    base_name=$(basename "${file_path}" | cut -f1 -d'.')
    local output_json="${OUTPUT_DIR:-/output}/${base_name}_structures.json"
    echo "Processing ${file_path}"
    python /app/skalu.py "${file_path}" --output "${output_json}"
}

case "$1" in
    all|'')
        process_directory "${INPUT_DIR:-/data}"
        ;;
    *)
        if [ -f "$1" ]; then
            process_single "$1"
        elif [ -d "$1" ]; then
            process_directory "$1"
        else
            echo "Error: $1 is not a valid file or directory."
            exit 1
        fi
        ;;
esac

chmod -R 777 "${OUTPUT_DIR:-/output}" 2>/dev/null || true
echo "Done."
