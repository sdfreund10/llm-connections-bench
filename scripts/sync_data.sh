#!/usr/bin/env bash
# Pull/push games.json + connections.json between local data/ and GCS.
# No-ops (exit 0) when DATA_BUCKET is unset — local development stays filesystem-only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
PREFIX="${DATA_PREFIX:-}"

usage() {
  echo "Usage: $0 pull|push" >&2
  echo "  Requires DATA_BUCKET (e.g. connections-bench-data-prod)." >&2
  echo "  Optional: DATA_DIR (default: <repo>/data), DATA_PREFIX." >&2
  exit 2
}

if [[ $# -ne 1 ]]; then
  usage
fi

CMD="$1"
if [[ "$CMD" != "pull" && "$CMD" != "push" ]]; then
  usage
fi

if [[ -z "${DATA_BUCKET:-}" ]]; then
  echo "DATA_BUCKET unset — skipping sync $CMD (local mode)."
  exit 0
fi

object_uri() {
  local name="$1"
  if [[ -n "$PREFIX" ]]; then
    echo "gs://${DATA_BUCKET}/${PREFIX%/}/${name}"
  else
    echo "gs://${DATA_BUCKET}/${name}"
  fi
}

mkdir -p "$DATA_DIR"

FILES=(games.json connections.json)

case "$CMD" in
  pull)
    for f in "${FILES[@]}"; do
      src="$(object_uri "$f")"
      echo "Pulling $src → $DATA_DIR/$f"
      gcloud storage cp "$src" "$DATA_DIR/$f"
    done
    ;;
  push)
    for f in "${FILES[@]}"; do
      local_path="$DATA_DIR/$f"
      if [[ ! -f "$local_path" ]]; then
        echo "Missing local file: $local_path" >&2
        exit 1
      fi
      dest="$(object_uri "$f")"
      echo "Pushing $local_path → $dest"
      gcloud storage cp "$local_path" "$dest"
    done
    ;;
esac
