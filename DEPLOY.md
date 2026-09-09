# Deploying llm-connections to Google Cloud

This document covers one-time GCP setup and how the nightly Job + GitHub Actions fit together.

## Architecture

| Piece | Name / notes |
|-------|----------------|
| Data bucket | `connections-bench-data-prod` (private) — `games.json`, `connections.json` |
| Site bucket | `connections-bench-assets-prod` (private) — Astro `dist/` via HTTPS LB + Cloud CDN |
| Nightly worker | Cloud Run **Job** running `scripts/nightly_cloud.sh` |
| Site (code) deploys | GitHub Action `.github/workflows/deploy-site.yml` |
| Image builds | GitHub Action `.github/workflows/build-image.yml` → Artifact Registry |
| Secrets | `OPENROUTER_API_KEY` in Secret Manager (Job only) |

Local development does **not** use GCS. Omit `DATA_BUCKET` and keep using `data/` on disk.

## Data sync

[`scripts/sync_data.sh`](scripts/sync_data.sh) pulls/pushes JSON at job boundaries:

```bash
export DATA_BUCKET=connections-bench-data-prod
./scripts/sync_data.sh pull   # → data/
./scripts/sync_data.sh push   # ← data/
```

If `DATA_BUCKET` is unset, pull/push no-op (exit 0).

Core CLI modules (`game.py`, `log.py`) always read/write local files.

## Nightly CLI (local)

```bash
uv run llm-connections nightly
uv run llm-connections nightly --date 2026-09-08
uv run llm-connections nightly --model openai/gpt-4.1-mini
```

Default date is **yesterday** in `NIGHTLY_TZ` (default `UTC`).

## Cloud Run Job

Image entrypoint: [`scripts/nightly_cloud.sh`](scripts/nightly_cloud.sh)

1. Pull JSON from `$DATA_BUCKET`
2. `uv run llm-connections nightly`
3. Push JSON back
4. Build Astro (`site/`)
5. `gcloud storage rsync` `site/dist` → `$SITE_BUCKET`

### Create the Job (after first image push)

```bash
export PROJECT_ID=YOUR_PROJECT
export REGION=us-central1
export AR_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/llm-connections"
export IMAGE="${AR_REPO}/llm-connections-nightly:main"

# Service account for the Job (needs storage on both buckets + secret access)
gcloud iam service-accounts create llm-connections-nightly \
  --display-name="llm-connections nightly job"

# Grant bucket access (adjust if using finer-grained roles)
gsutil iam ch \
  "serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com:roles/storage.objectAdmin" \
  gs://connections-bench-data-prod
gsutil iam ch \
  "serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com:roles/storage.objectAdmin" \
  gs://connections-bench-assets-prod

# Store OpenRouter key
echo -n "YOUR_KEY" | gcloud secrets create openrouter-api-key --data-file=-
gcloud secrets add-iam-policy-binding openrouter-api-key \
  --member="serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud run jobs create llm-connections-nightly \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="DATA_BUCKET=connections-bench-data-prod,SITE_BUCKET=connections-bench-assets-prod,NIGHTLY_TZ=America/New_York" \
  --set-secrets="OPENROUTER_API_KEY=openrouter-api-key:latest" \
  --task-timeout=24h \
  --max-retries=0 \
  --memory=2Gi \
  --cpu=2
```

### Scheduler (concurrency 1)

```bash
gcloud scheduler jobs create http llm-connections-nightly-daily \
  --location="$REGION" \
  --schedule="0 6 * * *" \
  --time-zone="America/New_York" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/llm-connections-nightly:run" \
  --http-method=POST \
  --oauth-service-account-email="llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com"
```

Use a dedicated invoker SA if you prefer least privilege; grant it `roles/run.invoker` on the Job.

## Site hosting (CDN + DNS)

Keep `connections-bench-assets-prod` **private**. Put an HTTPS load balancer with a **backend bucket** and Cloud CDN in front:

1. Backend bucket → `connections-bench-assets-prod` (enable CDN)
2. URL map + HTTPS proxy + forwarding rule
3. Google-managed certificate for your domain
4. DNS A/AAAA (or CNAME) to the LB IP

Do **not** grant `allUsers` objectViewer on the assets bucket when using this pattern.

Optional after deploy: invalidate CDN (`gcloud compute url-maps invalidate-cdn-cache ...`) — add later once the map exists.

## Seed data bucket (first time)

From a machine with local `data/` and gcloud auth:

```bash
export DATA_BUCKET=connections-bench-data-prod
./scripts/sync_data.sh push
```

## GitHub Actions + Workload Identity Federation

Workflows expect a GitHub Environment named **`prod`** with these **variables** (not secrets):

| Variable | Example |
|----------|---------|
| `GCP_PROJECT_ID` | your GCP project id |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER` |
| `GCP_SERVICE_ACCOUNT` | `llm-connections-gha@PROJECT_ID.iam.gserviceaccount.com` |
| `ARTIFACT_REGISTRY_REPO` | `us-central1-docker.pkg.dev/PROJECT_ID/llm-connections` |
| `DATA_BUCKET` | `connections-bench-data-prod` (optional; workflow has default) |
| `SITE_BUCKET` | `connections-bench-assets-prod` (optional; workflow has default) |

### Recommended: separate GHA service account

Create `llm-connections-gha` with:

- `roles/storage.objectViewer` on the **data** bucket
- `roles/storage.objectAdmin` on the **assets** bucket
- `roles/artifactregistry.writer` on the Artifact Registry repo

Do **not** give this SA the OpenRouter secret; nightly LLM calls stay on the Job SA.

### Wire WIF (summary)

1. Enable IAM Credentials API
2. Create a workload identity pool + GitHub OIDC provider (attribute condition: your repo)
3. Bind the pool principal to `llm-connections-gha` with `roles/iam.workloadIdentityUser`
4. Set the provider resource name and SA email as GitHub Environment variables

Official guide: [Authenticate to Google Cloud from GitHub Actions](https://github.com/google-github-actions/auth).

### Workflows

- **`deploy-site.yml`** — on `site/**` changes to `main` (or manual): pull JSON → `astro build` → rsync to assets bucket
- **`build-image.yml`** — on Dockerfile/src/script changes: build/push `:main` and `:<sha>`; update the Cloud Run Job image when ready:

```bash
gcloud run jobs update llm-connections-nightly \
  --region="$REGION" \
  --image="${AR_REPO}/llm-connections-nightly:SHA"
```

## Astro `DATA_DIR`

[`site/src/lib/data.ts`](site/src/lib/data.ts) reads:

```text
DATA_DIR  (env)  or  <cwd>/../data
```

CI and the Job set `DATA_DIR` explicitly when needed.

## Watch: `games.json` size

If nightly logging, backfill skip checks, or `astro build` get slow, consider archiving old dates into historical files. See [`FUTURE.md`](FUTURE.md).
