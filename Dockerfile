# syntax=docker/dockerfile:1

# Base stage: Python runtime with system deps for simulators
FROM python:3.11-slim as base

# Install system dependencies for MuJoCo, PyBullet, and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglew2.2 \
    libglu1-mesa \
    libx11-6 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build stage: install package with editable mode + all extras
FROM base as build

# Copy dependency definitions first for layer caching
COPY pyproject.toml pytest.ini ./
COPY src/ src/
COPY README.md README.md

# Upgrade pip and install with extras
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev,tracking]"

# Runtime stage: keep only installed packages, not build artifacts
FROM base as runtime

# Copy installed site-packages from build stage
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin/surg-rl /usr/local/bin/surg-rl

# Copy source code (needed because editable install symlinks to src/)
COPY src/ /app/src/
COPY scenes/ /app/scenes/
COPY configs/ /app/configs/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Default entrypoint
ENTRYPOINT ["python", "-m", "surg_rl.cli"]
CMD ["version"]
