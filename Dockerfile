# syntax=docker/dockerfile:1

# ---------- Stage 1: build the React SPA ----------
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY smbcrawler-ui/frontend/package.json smbcrawler-ui/frontend/package-lock.json* ./
RUN npm install
COPY smbcrawler-ui/frontend/ ./
RUN npm run build   # -> /frontend/dist

# ---------- Stage 2: backend + smbcrawler ----------
FROM python:3.12-slim AS backend

# Runtime libs for impacket / lxml / python-magic / markitdown(+exiftool) / psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 libmagic-mgc \
        exiftool \
        poppler-utils \
        gcc libpq5 \
        git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    XDG_DATA_HOME=/data/xdg

WORKDIR /app

# 1) smbcrawler from the sibling checkout (kept unmodified). hatch-vcs reads smbcrawler/.git.
COPY smbcrawler/ /opt/smbcrawler/
RUN pip install /opt/smbcrawler

# 2) backend deps -- installed from pyproject before the source for layer caching
COPY smbcrawler-ui/backend/pyproject.toml ./
RUN python - <<'PY'
import subprocess, tomllib
proj = tomllib.load(open("pyproject.toml", "rb"))["project"]
deps = proj["dependencies"] + proj.get("optional-dependencies", {}).get("dev", [])
subprocess.check_call(["pip", "install", *deps])
PY

# 3) backend source + built SPA, then register the package (no deps -- already installed)
COPY smbcrawler-ui/backend/ ./
COPY --from=frontend /frontend/dist ./app/static
RUN pip install --no-deps -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
