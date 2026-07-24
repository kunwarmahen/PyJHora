FROM python:3.11-slim

WORKDIR /app

# Unbuffered stdout. Python block-buffers stdout (~8KB) whenever it isn't a TTY,
# which is exactly the case under `docker logs`. Every diagnostic in this backend
# is a bare print() — [scheduler], [digest], [email:noop], [email:error], [push] —
# so without this they sit in the buffer for hours or days on a quiet instance
# while uvicorn's own lines (logging module → stderr) appear immediately. The
# result is a container that looks like it is logging normally while telling you
# nothing about the thing you are debugging. Cost is negligible; never remove it.
ENV PYTHONUNBUFFERED=1

# No compiler toolchain: every pinned dependency resolves to a manylinux wheel
# except http-ece (a pure-Python sdist pulled in by pywebpush), which needs only
# setuptools. build-essential used to live here and cost 354MB — a third of the
# image, re-shipped to the NAS on every deploy. If a future dependency does need
# to compile, add it in a `FROM python:3.11-slim AS build` stage and copy the
# wheels forward rather than putting gcc back in the runtime image.

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
