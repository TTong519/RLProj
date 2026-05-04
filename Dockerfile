# syntax=docker/dockerfile:1

ARG BUILDPLATFORM
ARG TARGETPLATFORM

FROM --platform=$BUILDPLATFORM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglew2.2 \
    libglu1-mesa \
    libx11-6 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml pytest.ini ./
COPY src/ src/
COPY README.md README.md

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev,tracking]"

COPY scenes/ /app/scenes/
COPY configs/ /app/configs/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "surg_rl.cli"]
CMD ["version"]
