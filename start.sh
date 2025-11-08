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

# Stop and remove any existing farecraft containers to avoid port conflicts
echo "🧹 Cleaning up old containers..."
docker ps -a --filter "ancestor=prajwalsrinivas7/farecraft" --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true

# Run the container with volume mount for persistent data
# Volume mount maps: ./output (host) -> /app/output (container)
# This preserves: flights.db (cookie cache), logs/, output.json
# --rm: Automatically remove container when it exits
if [ "$FULL_MODE" = true ]; then
    echo "🚀 Starting API server (full mode)..."
    echo "📡 API will be available at: http://localhost:8000"
    docker run --rm -v ./output:/app/output -p 8000:8000 prajwalsrinivas7/farecraft python -m api.main
else
    echo "🚀 Starting scraper (contest mode)..."
    echo "📄 Results will be saved to: ./output/output.json"
    docker run --rm -v ./output:/app/output prajwalsrinivas7/farecraft python scraper/scraper.py
fi
