#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}"
echo "==============================================================="
echo "                Skalu - Setup Script                           "
echo "==============================================================="
echo -e "${NC}"

# Create project structure
echo -e "${YELLOW}Creating project structure...${NC}"
mkdir -p input output

# Create empty .gitkeep files
touch input/.gitkeep
touch output/.gitkeep

# Make entrypoint.sh executable
echo -e "${YELLOW}Setting permissions...${NC}"
chmod +x entrypoint.sh

# Check if Docker is installed
if command -v docker &> /dev/null; then
    echo -e "${GREEN}Docker is installed.${NC}"
else
    echo -e "${YELLOW}Docker not found. Please install Docker to use this project.${NC}"
    echo "Visit https://docs.docker.com/get-docker/ for installation instructions."
fi

# Build the Docker image if Docker is installed
if command -v docker &> /dev/null; then
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker build -t skalu .
    echo -e "${GREEN}Docker image built successfully!${NC}"
fi

echo -e "${GREEN}Setup complete!${NC}"
echo -e "You can now:"
echo -e "1. Put your images in the ${BLUE}input${NC} folder"
echo -e "2. Run ${BLUE}make run${NC} or ${BLUE}docker-compose up${NC} to process them"
echo -e "3. Find the results in the ${BLUE}output${NC} folder"
echo ""
echo -e "For more information, run ${BLUE}make help${NC}"