#!/usr/bin/env bash
# Cloud Run Job entrypoint: sync data ↔ GCS, run nightly suite, rebuild & publish site.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${DATA_BUCKET:?DATA_BUCKET is required}"
: "${SITE_BUCKET:?SITE_BUCKET is required}"

export DATA_DIR="${DATA_DIR:-$ROOT/data}"
mkdir -p "$DATA_DIR"

echo "==> Pull data from gs://${DATA_BUCKET}"
"$ROOT/scripts/sync_data.sh" pull

echo "==> Run nightly"
set +e
uv run llm-connections nightly "$@"
nightly_status=$?
set -e

echo "==> Push data to gs://${DATA_BUCKET}"
"$ROOT/scripts/sync_data.sh" push

echo "==> Build Astro site"
cd "$ROOT/site"
npm ci
DATA_DIR="$DATA_DIR" npm run build

echo "==> Publish dist/ to gs://${SITE_BUCKET}"
gcloud storage rsync --delete-unmatched-destination-objects --recursive "$ROOT/site/dist" "gs://${SITE_BUCKET}"

echo "==> Nightly cloud job finished"
exit "$nightly_status"
