# Multi-stage build for optimal image size
# Stage 1: Builder - Install dependencies using UV
# Stage 2: Runtime - Slim image with Camoufox system dependencies

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder

# UV optimization flags for faster builds and runtime
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency files first (cached layer)
COPY pyproject.toml ./

# Install dependencies only (no project install yet)
# This layer is cached unless dependencies change
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# Copy all application code
COPY . /app

# Install the project in non-editable mode
# This allows us to copy just the venv without source code
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-editable --no-dev

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim-bookworm

# Install system dependencies required by Camoufox (Firefox-based)
# These are essential for running a headless browser
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core libraries
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    libpci3 \
    libasound2 \
    # Font rendering
    fonts-liberation \
    libfontconfig1 \
    # Additional Firefox dependencies
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libnss3 \
    libnspr4 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code from builder
COPY --from=builder /app/src /app

# Set working directory to /app
WORKDIR /app

# Activate virtual environment by adding to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Set Python to run in unbuffered mode (logs appear immediately)
ENV PYTHONUNBUFFERED=1

# Pre-download Camoufox browser binaries (Firefox) during build
# This prevents 2-3 minute download during runtime, significantly reducing crawl time
RUN echo "📦 Downloading Camoufox/Firefox binaries (~750MB, this may take 2-3 minutes)..." && \
    camoufox fetch && \
    echo "✓ Browser binaries downloaded to /root/.cache/camoufox" && \
    echo "✓ Verifying browser installation..." && \
    python -c "from camoufox.sync_api import Camoufox; b = Camoufox(headless=True); print('✓ Browser ready!')"

# Create output directory
RUN mkdir -p /app/output

# Expose port for API (used with --full mode)
EXPOSE 8000

# Default: Run scraper (contest mode)
# Use start.sh script to run with proper volume mounting
CMD ["python", "scraper/scraper.py"]
