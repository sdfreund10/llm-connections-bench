# Cloud Run Job image: Python CLI (uv) + Node 22 (Astro) + gcloud CLI.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
        | tee /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
        | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first for layer caching
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Site deps
COPY site/package.json site/package-lock.json ./site/
RUN cd site && npm ci

COPY site ./site
COPY scripts ./scripts

RUN chmod +x scripts/sync_data.sh scripts/nightly_cloud.sh

ENV PATH="/app/.venv/bin:$PATH"
ENV DATA_DIR=/app/data

ENTRYPOINT ["/app/scripts/nightly_cloud.sh"]
