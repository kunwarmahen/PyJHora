FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# NOTE: the build context is the repository root (see web/docker-compose.yml), so all
# COPY paths below are relative to PyJHora/. This lets us vendor the jhora library
# `src/` into the image — astrology.py imports jhora from ../../src, which resolves to
# /src inside the container (/app/../../src -> /src), so it must exist in the image.

# Copy + install Python deps first for layer caching.
COPY web/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Vendor the jhora astrology library so `from jhora...` works in the container.
COPY src /src

# Copy the backend application code.
COPY web/backend /app

# Expose port
EXPOSE 8000

# Command to run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
