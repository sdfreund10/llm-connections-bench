## Usage
```bash
# Download latest connections games
uv run llm-connections update
# Run games between provided dates through provided LLM
uv run llm-connections run 2026-09-01 2026-09-06 openai/gpt-4.1
# Backfill the benchmark suite (skips existing entries; defaults 2026-08-15 → 2026-09-04)
uv run llm-connections backfill
uv run llm-connections backfill 2026-08-15 2026-09-04 --model z-ai/glm-5.3-flash
# Nightly: refresh puzzles and run the model suite for the week leading up to yesterday
uv run llm-connections nightly
```

## Static site

The public benchmark lives in `site/` (Astro). It reads `data/games.json` and `data/connections.json` at build time (`DATA_DIR` overrides the data root).

```bash
cd site && npm install && npm run build
npm run preview   # local preview of dist/
```

Rebuild the site after new CLI runs to publish updated results.

## Deploy

Cloud deploy (GCS buckets, Cloud Run Job, GitHub Actions, CDN/DNS) is documented in [DEPLOY.md](DEPLOY.md).
