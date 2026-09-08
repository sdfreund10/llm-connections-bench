## Usage
```bash
# Download latest connections games
uv run llm-connections update
# Run games between provided dates through provided LLM
uv run llm-connections run 2026-09-01 2026-09-06 openai/gpt-4.1
```

## Static site

The public benchmark lives in `site/` (Astro). It reads `data/games.json` and `data/connections.json` at build time.

```bash
cd site && npm install && npm run build
npm run preview   # local preview of dist/
```

Rebuild the site after new CLI runs to publish updated results.