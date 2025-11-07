#!/bin/bash
set -e

# Create output directory if it doesn't exist
# This ensures persistent storage is available for volume mount
mkdir -p ./output

# Parse arguments
FULL_MODE=false
for arg in "$@"; do
    if [ "$arg" = "--full" ]; then
        FULL_MODE=true
        break
    fi
done

# Run the container with volume mount for persistent data
# Volume mount maps: ./output (host) -> /app/output (container)
# This preserves: flights.db (cookie cache), logs/, output.json
if [ "$FULL_MODE" = true ]; then
    echo "🚀 Starting API server (full mode)..."
    echo "📡 API will be available at: http://localhost:8000"
    docker run -v ./output:/app/output -p 8000:8000 farecraft:latest python -m api.main
else
    echo "🚀 Starting scraper (contest mode)..."
    echo "📄 Results will be saved to: ./output/output.json"
    docker run -v ./output:/app/output farecraft:latest python scraper/scraper.py
fi
