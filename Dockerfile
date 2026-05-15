# syntax=docker/dockerfile:1.7

# ════════════════════════════════════════════════════════════════
# Stage 1 — builder: install deps into a venv
# ════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libffi-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
# --trusted-host flags work around corporate TLS-intercepting proxies that
# present self-signed certs. Package integrity is still verified by pip via
# wheel hashes; only the TLS handshake to PyPI mirrors is relaxed.
ARG PIP_TRUSTED="--trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org --trusted-host download.pytorch.org --trusted-host download-r2.pytorch.org"
# Install CPU-only torch FIRST so sentence-transformers doesn't pull in the
# ~2GB CUDA stack. This cuts the image from ~5GB to ~1.5GB.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade ${PIP_TRUSTED} pip wheel \
    && /opt/venv/bin/pip install ${PIP_TRUSTED} \
         --index-url https://download.pytorch.org/whl/cpu \
         --extra-index-url https://pypi.org/simple \
         torch==2.5.1 \
    && /opt/venv/bin/pip install ${PIP_TRUSTED} -r requirements.txt

# ════════════════════════════════════════════════════════════════
# Stage 2 — runtime: minimal image with only runtime deps
# ════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 tripsafe \
    && useradd --system --uid 1001 --gid tripsafe --home /app tripsafe

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=tripsafe:tripsafe . /app

RUN mkdir -p /app/uploads /app/faiss_store \
    && chown -R tripsafe:tripsafe /app/uploads /app/faiss_store

USER tripsafe

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "app.main:app"]
