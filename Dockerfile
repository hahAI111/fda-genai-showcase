# Enterprise GenAI Content Studio — Production Dockerfile
# Multi-stage build: install deps in builder, run in slim image
FROM python:3.11-slim AS builder

WORKDIR /app

# System build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata only (layer cache optimization)
COPY pyproject.toml README.md ./
# Stub src package so hatchling can build
RUN mkdir -p src && touch src/__init__.py

# Install all Python dependencies into /root/.local
RUN pip install --upgrade pip \
    && pip install --user --no-cache-dir hatchling \
    && pip install --user --no-cache-dir -e ".[dev]" || \
       pip install --user --no-cache-dir \
           fastapi \
           "uvicorn[standard]" \
           "openai>=1.60.0" \
           "azure-identity>=1.19.0" \
           "azure-storage-blob>=12.24.0" \
           "azure-search-documents>=11.6.0" \
           "mcp[cli]>=1.6.0" \
           "pydantic>=2.10.0" \
           "pydantic-settings>=2.7.0" \
           "structlog>=24.4.0" \
           "opentelemetry-api>=1.29.0" \
           "opentelemetry-sdk>=1.29.0" \
           "opentelemetry-instrumentation-fastapi>=0.50b0" \
           "httpx>=0.28.0" \
           "rich>=13.0.0" \
           "python-pptx>=1.0.0" \
           "Pillow>=10.0.0" \
           "google-genai>=1.0.0" \
           "google-auth>=2.36.0"

# ── Final runtime image ────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ src/
COPY skills/ skills/
COPY sample_data/ sample_data/
COPY pyproject.toml README.md ./

# Create output directories (writeable by app)
RUN mkdir -p output/generated-media output/generated-ppts logs

# Environment
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install package in editable mode in final stage
RUN pip install --no-cache-dir -e . 2>/dev/null || true

EXPOSE 8000

# Healthcheck — calls /health after 60s startup grace period
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Copy startup wrapper (catches import errors before uvicorn)
COPY startup.sh ./
RUN chmod +x startup.sh

CMD ["bash", "startup.sh"]
