# Deploying llm-connections to Google Cloud

One-time GCP + GitHub setup for the public site and nightly benchmark job. Most steps can be done in the **Google Cloud Console**; `gcloud` equivalents are included where helpful, with notes on what each command does.

Local development does **not** use GCS. Leave `DATA_BUCKET` unset and use `data/` on disk.

## Architecture

| Piece | Name / notes |
|-------|----------------|
| Data bucket | `connections-bench-data-prod` (private) — `games.json`, `connections.json` |
| Site bucket | `connections-bench-assets-prod` (private) — Astro `dist/` behind HTTPS LB + Cloud CDN |
| Nightly worker | Cloud Run **Job** running [`scripts/nightly_cloud.sh`](scripts/nightly_cloud.sh) |
| Site (code) deploys | GitHub Action [`.github/workflows/deploy-site.yml`](.github/workflows/deploy-site.yml) |
| Image builds | GitHub Action [`.github/workflows/build-image.yml`](.github/workflows/build-image.yml) → Artifact Registry |
| Secrets | `OPENROUTER_API_KEY` and `SENTRY_DSN` in Secret Manager (Job SA only — not the GitHub Actions SA) |

```text
Cloud Scheduler
    → Cloud Run Job (pull data → nightly CLI → push data → astro build → rsync site)
GitHub Actions (site/**)
    → pull data → astro build → rsync site
GitHub Actions (image)
    → docker build/push → Artifact Registry → (manual) update Job image
Public users
    → DNS → HTTPS LB + Cloud CDN → private assets bucket
```

---

## 1. Buckets (Console)

Create two **private** buckets (no public `allUsers` access):

| Bucket | Purpose |
|--------|---------|
| `connections-bench-data-prod` | Durable JSON the Job and CI sync |
| `connections-bench-assets-prod` | Published static site (`index.html` at **bucket root**, not under `dist/`) |

**Website config on the assets bucket** (required so `/` serves `index.html`):

1. Cloud Storage → `connections-bench-assets-prod` → **Configuration**
2. Edit website configuration
3. **Main page**: `index.html`
4. Optional **Not found page**: `404.html` if present in the Astro build

Without this, HTTPS may reach the bucket but `/` will not render the homepage (`/index.html` may still work).

### Seed the data bucket (first time)

From a laptop with local `data/` and `gcloud` logged into the project:

```bash
export DATA_BUCKET=connections-bench-data-prod
./scripts/sync_data.sh push
```

[`scripts/sync_data.sh`](scripts/sync_data.sh) copies `games.json` and `connections.json` between local `data/` and the bucket. `pull` downloads; `push` uploads. If `DATA_BUCKET` is unset, both no-op (local mode).

---

## 2. Artifact Registry (Console)

GitHub builds the nightly Job image and pushes it here. **Create the repo before the first image workflow run** — a missing repo often surfaces as a confusing “permission denied” on upload.

1. **Artifact Registry** → **Create repository**
2. Format: **Docker**
3. Name: `llm-connections`
4. Location: `us-central1` (or match `ARTIFACT_REGISTRY_REPO`)

Image path shape:

```text
us-central1-docker.pkg.dev/PROJECT_ID/llm-connections/llm-connections-nightly:main
```

---

## 3. Service accounts (Console)

Create two service accounts under **IAM & Admin → Service accounts**:

### `llm-connections-gha` (GitHub Actions)

Used only by CI. Does **not** need OpenRouter.

Suggested roles (project-level is fine for a small project; tighten to buckets/repos later):

| Role | Why |
|------|-----|
| Storage Object Viewer | Read `games.json` / `connections.json` for site builds |
| Storage Object Admin | Write Astro `dist/` into the assets bucket (or Object Admin on that bucket only) |
| Artifact Registry Writer | `docker push` to `llm-connections` |

### `llm-connections-nightly` (Cloud Run Job)

| Access | Why |
|--------|-----|
| Object Admin on **both** buckets | Pull/push JSON; publish `dist/` |
| Secret Manager Secret Accessor on `openrouter-api-key` | LLM calls |
| Secret Manager Secret Accessor on `sentry-dsn` | Sentry error + cron reporting |
| (Invoker setup) | Scheduler must be allowed to run the Job — see below |

---

## 4. Secret Manager (Console)

1. **Secret Manager** → **Create secret** → name `openrouter-api-key` → paste OpenRouter API key
2. **Create secret** → name `sentry-dsn` → paste the DSN from Sentry project **Settings → Client Keys (DSN)** (org `steve-freund`, project `connections-bench`)
3. Grant **Secret Manager Secret Accessor** on both secrets to `llm-connections-nightly@…`

Do **not** grant these secrets to the GHA service account.

Sentry is a no-op when `SENTRY_DSN` is unset (local CLI). On the Job, the SDK reports swallowed per-game failures, soft GCS sync failures, and sends **Cron** check-ins for monitor slug `llm-connections-nightly` (schedule `0 6 * * *` / `America/New_York` — keep in sync with Cloud Scheduler, or override with `SENTRY_MONITOR_SCHEDULE` / `SENTRY_MONITOR_TIMEZONE`).

Python hot-path logs (nightly/backfill/game/sync/update) go to stdout as structured fields (`stage`, `model`, `date`, `status`, suite counts). With `DATA_BUCKET` set the Job emits **JSON** lines (Cloud Logging–friendly); locally the default is compact text. Override with `LOG_FORMAT=json` or `LOG_FORMAT=text`. Shell stage banners in `nightly_cloud.sh` stay human-readable.

---

## 5. Workload Identity Federation for GitHub (Console)

Lets Actions impersonate `llm-connections-gha` with short-lived tokens (no JSON key file).

### 5a. Pool + provider

1. Enable **IAM Service Account Credentials API** (APIs & Services)
2. **IAM & Admin → Workload Identity Federation → Create pool** (e.g. pool id `github`)
3. Add a provider:
   - Type: **OpenID Connect (OIDC)**
   - Issuer: `https://token.actions.githubusercontent.com`
   - Attribute mapping (typical):

     ```text
     google.subject=assertion.sub
     attribute.actor=assertion.actor
     attribute.repository=assertion.repository
     attribute.repository_owner=assertion.repository_owner
     attribute.ref=assertion.ref
     ```

   - Attribute condition (lock to this repo):

     ```text
     assertion.repository == "sdfreund10/llm-connections-bench"
     ```

### 5b. Grant access (impersonation)

On the pool’s **Grant access** screen:

- Access method: **Service account impersonation**
- Service account: `llm-connections-gha@…`
- Principals: attribute **`repository`** = `sdfreund10/llm-connections-bench`

That allows only workflows from this GitHub repo to act as the GHA SA.

### 5c. Copy the provider resource name

For GitHub, you need the **provider** name, **not** a `principal://…` string:

```text
projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
```

Console: open the provider → copy **Provider name**.  
`PROJECT_NUMBER` is numeric (e.g. `770645610227`), not the project id string.

---

## 6. GitHub Environment `prod`

Repo → **Settings → Environments → `prod`**.

Add **Variables** (not Secrets) — these are not sensitive; security is the WIF/IAM binding:

| Variable | Example | What it is |
|----------|---------|------------|
| `GCP_PROJECT_ID` | `llm-connections-benchmark` | Project id string |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/…/providers/…` | Full provider resource name from §5c |
| `GCP_SERVICE_ACCOUNT` | `llm-connections-gha@….iam.gserviceaccount.com` | SA email |
| `ARTIFACT_REGISTRY_REPO` | `us-central1-docker.pkg.dev/PROJECT_ID/llm-connections` | Registry + repo (no image name) |
| `DATA_BUCKET` | `connections-bench-data-prod` | Optional (workflow has default) |
| `SITE_BUCKET` | `connections-bench-assets-prod` | Optional (workflow has default) |

Workflows reference `vars.*` and set `environment: prod`. If you put values under **Actions secrets** instead, auth will fail with an empty provider (see Troubleshooting).

### Workflows

| Workflow | When it runs | What it does |
|----------|--------------|--------------|
| `test.yml` | PRs + every push to `main` | `uv run pytest` |
| `deploy-site.yml` | `site/**` on `main`, or manual | Auth → pull JSON → `astro build` → rsync to assets bucket |
| `build-image.yml` | Dockerfile/src/scripts/lockfiles on `main`, or manual | Test → build/push `:main` and `:<sha>` |

**Path filters:** editing only `.github/workflows/*.yml` does **not** run deploy-site or build-image. Use **Actions → Run workflow**, or touch a watched path.

After a new image is pushed, point the Job at it (Console: Cloud Run → Job → Edit → Container image, or):

```bash
# Updates which container image the Job runs on the next execution.
# Does not run the Job by itself.
gcloud run jobs update llm-connections-nightly \
  --region=us-central1 \
  --image="us-central1-docker.pkg.dev/PROJECT_ID/llm-connections/llm-connections-nightly:SHA"
```

---

## 7. Cloud Run Job (Console)

Entrypoint in the image: [`scripts/nightly_cloud.sh`](scripts/nightly_cloud.sh)

1. Pull JSON from `$DATA_BUCKET` into local `data/`
2. `uv run llm-connections nightly` (optional container args become `"$@"` — e.g. `--date 2026-09-08`)
3. Push JSON back to the data bucket
4. `npm ci` + `astro build` in `site/`
5. `gcloud storage rsync` of `site/dist/` → **contents at assets bucket root** (not a `dist/` folder)

**Create Job** (Cloud Run → Jobs):

- Image: `…/llm-connections-nightly:main` (after first successful build-image)
- Service account: `llm-connections-nightly`
- Env: `DATA_BUCKET`, `SITE_BUCKET` (optional `NIGHTLY_TZ`, e.g. `America/New_York`; optional `SENTRY_ENVIRONMENT=production`, `SENTRY_RELEASE=<image tag>`)
- Secret env: `OPENROUTER_API_KEY` ← `openrouter-api-key`; `SENTRY_DSN` ← `sentry-dsn`
- Timeout: long enough for the full model suite (up to 24h)
- Memory/CPU: start around 2 GiB / 2 vCPU

### Optional CLI create (annotated)

```bash
export PROJECT_ID=YOUR_PROJECT
export REGION=us-central1
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/llm-connections/llm-connections-nightly:main"

# Creates an identity the Job runtime will use for GCS + Secret Manager.
gcloud iam service-accounts create llm-connections-nightly \
  --display-name="llm-connections nightly job"

# Allows that SA to read/write objects in the data and site buckets.
gsutil iam ch \
  "serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com:roles/storage.objectAdmin" \
  gs://connections-bench-data-prod
gsutil iam ch \
  "serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com:roles/storage.objectAdmin" \
  gs://connections-bench-assets-prod

# Stores the OpenRouter key as a managed secret (not in the image or env file in git).
echo -n "YOUR_KEY" | gcloud secrets create openrouter-api-key --data-file=-

# Stores the Sentry DSN (Client Keys in the Sentry project UI).
echo -n "YOUR_SENTRY_DSN" | gcloud secrets create sentry-dsn --data-file=-

# Lets the Job SA read those secrets at runtime.
gcloud secrets add-iam-policy-binding openrouter-api-key \
  --member="serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding sentry-dsn \
  --member="serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Registers the Job definition (image, SA, env, secrets, resources). Does not schedule it.
gcloud run jobs create llm-connections-nightly \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="DATA_BUCKET=connections-bench-data-prod,SITE_BUCKET=connections-bench-assets-prod,NIGHTLY_TZ=America/New_York,SENTRY_ENVIRONMENT=production" \
  --set-secrets="OPENROUTER_API_KEY=openrouter-api-key:latest,SENTRY_DSN=sentry-dsn:latest" \
  --task-timeout=24h \
  --max-retries=0 \
  --memory=2Gi \
  --cpu=2
```

To add Sentry to an **existing** Job:

```bash
# One-time secret (skip if already created):
echo -n "YOUR_SENTRY_DSN" | gcloud secrets create sentry-dsn --data-file=-
gcloud secrets add-iam-policy-binding sentry-dsn \
  --member="serviceAccount:llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud run jobs update llm-connections-nightly \
  --region="$REGION" \
  --update-secrets="SENTRY_DSN=sentry-dsn:latest" \
  --update-env-vars="SENTRY_ENVIRONMENT=production"
```

---

## 8. Cloud Scheduler (Console)

1. **Cloud Scheduler** → Create job
2. Frequency: e.g. `0 6 * * *` with time zone `America/New_York`
3. Target: **HTTP** POST to the Cloud Run Jobs “run” API for `llm-connections-nightly`, **or** use the Console’s Cloud Run Job trigger helper if shown
4. Auth: OIDC / OAuth as a SA that has **Cloud Run Invoker** on the Job
5. Keep concurrency at **1** so two nightlies never pull–modify–push `games.json` at once

### Optional CLI create (annotated)

```bash
# Fires an authenticated HTTP request once a day that starts a Job execution.
# The OAuth SA must be allowed to invoke the Job (roles/run.invoker).
gcloud scheduler jobs create http llm-connections-nightly-daily \
  --location="$REGION" \
  --schedule="0 6 * * *" \
  --time-zone="America/New_York" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/llm-connections-nightly:run" \
  --http-method=POST \
  --oauth-service-account-email="llm-connections-nightly@${PROJECT_ID}.iam.gserviceaccount.com"
```

Prefer a dedicated invoker SA with only `roles/run.invoker` if you want least privilege.

---

## 9. HTTPS load balancer + CDN + DNS (Console)

Keep the assets bucket **private**. Public traffic hits the LB only.

### Load balancer

1. **Network services → Load balancing → Create** → HTTPS application load balancer
2. Backend: **Backend bucket** → `connections-bench-assets-prod` → enable **Cloud CDN**
3. Frontend: HTTPS, Google-managed certificate for your hostname(s)  
   Example: `connections-bench.sfreund.tools`
4. Note the forwarding-rule **IPv4** (and IPv6 if any)

### Critical: CDN read access on the private bucket

Without this you get **Access Denied** even with a valid cert and DNS.

On `connections-bench-assets-prod` → Permissions → Grant access:

| Principal | Role |
|-----------|------|
| `service-PROJECT_NUMBER@cloud-cdn-fill.google.com.iam.gserviceaccount.com` | Storage Object Viewer |

(`PROJECT_NUMBER` is numeric.)

Do **not** grant `allUsers` objectViewer when using this pattern.

Also set the bucket **website main page** to `index.html` (§1).

### DNS (e.g. Porkbun)

| Type | Host | Answer |
|------|------|--------|
| `A` | subdomain or `@` | Load balancer IPv4 |
| `AAAA` | same | LB IPv6, if you have one |

Remove conflicting parking records. Cert stays **PROVISIONING** until public DNS points at the LB; then becomes **ACTIVE** (often minutes, up to ~24h).

### Manual site upload (smoke test)

```bash
cd site && npm ci && npm run build
# Syncs files *inside* dist/ to the bucket root (index.html at gs://bucket/index.html).
gcloud storage rsync --delete dist "gs://connections-bench-assets-prod"
```

---

## Local CLI reminders

```bash
# Refresh puzzles + run model suite for yesterday (or --date / --model)
uv run llm-connections nightly

# Hydrate or publish JSON when DATA_BUCKET is set
./scripts/sync_data.sh pull
./scripts/sync_data.sh push
```

Astro reads `DATA_DIR` or `<cwd>/../data` at build time ([`site/src/lib/data.ts`](site/src/lib/data.ts)).

---

## Troubleshooting

### GitHub: `must specify exactly one of "workload_identity_provider" or "credentials_json"`

The auth input was **empty**. Workflows use `vars.GCP_WORKLOAD_IDENTITY_PROVIDER` on environment **`prod`**.

- Put values in **Environment variables** on `prod`, not Actions **Secrets**
- Names must match exactly
- Provider value must be `projects/NUMBER/.../providers/ID`, not `principal://…`

### GitHub: `artifactregistry.repositories.uploadArtifacts` denied (or may not exist)

Usually one of:

1. **Docker repo not created** in Artifact Registry (`llm-connections` in `us-central1`) — create it first
2. GHA SA missing **Artifact Registry Writer**
3. `ARTIFACT_REGISTRY_REPO` / `GCP_SERVICE_ACCOUNT` vars wrong

### Site: `Access Denied` over HTTPS

LB/CDN reached GCS but cannot read objects. Grant  
`service-PROJECT_NUMBER@cloud-cdn-fill.google.com.iam.gserviceaccount.com`  
**Storage Object Viewer** on `connections-bench-assets-prod`. Confirm CDN is enabled on the backend bucket.

### Site: HTTPS works but `/` doesn’t show the app

- Set bucket website **main page** to `index.html`
- Confirm `gs://connections-bench-assets-prod/index.html` exists (rsync of `dist/` contents to bucket **root**, not a `dist/` prefix)
- Try `/index.html`; if that works and `/` doesn’t, it’s the website config
- CDN may cache an old error briefly after fixes

### `deploy-site` / `build-image` didn’t run after a push

Path filters. Only changing workflow YAML (or unrelated paths) skips them. Use **workflow_dispatch** or push under `site/**` / `src/**` / etc.

### Nightly Job: data looks stale or site didn’t update

Check Job logs for which step failed (pull, nightly, push, npm build, rsync). A crash after models run but before push leaves GCS on the previous snapshot; the next successful run continues from that.

---

## Watch: `games.json` size

If nightly logging, skip checks, or `astro build` get slow, consider archiving old dates into historical files. See [`FUTURE.md`](FUTURE.md).
