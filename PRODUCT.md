# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

CLI (established): Python 3.14+, `uv`, OpenRouter API, local JSON in `data/`.

Static site (delegated): Astro — data-driven static generation from `data/games.json` and `data/connections.json`; no runtime server required for the public surface.

## Users

**Primary:** Steve Freund — runs and compares how different LLMs play NYT Connections puzzles from the terminal.

**Secondary:** Public readers of the static site — browse longitudinal model performance without running the CLI themselves.

## Product Purpose

Benchmark large language models on real NYT Connections puzzles and make the results shareable. The CLI produces reproducible, logged game runs; the planned static website publishes daily outcomes and long-term success metrics so performance can be compared across models and over time.

**Success means:** logged CLI runs that feed a public-facing site where anyone can see how models perform on Connections — not just a one-off terminal session.

## Positioning

A **longitudinal Connections benchmark** — track win rates, mistake patterns, and trends across models and dates on the same puzzle corpus. Neighboring LLM leaderboard sites measure broad capability; this product measures sustained word-association puzzle performance on a fixed, daily-updating archive with full guess-and-reasoning logs.

## Operating Context

- **Data source:** Puzzle archive downloaded from [Eyefyre/NYT-Connections-Answers](https://github.com/Eyefyre/NYT-Connections-Answers) (`uv run llm-connections update`).
- **Game corpus:** Puzzles from 2026-08-01 onward (see `Game.load_all` filter).
- **Execution:** `uv run llm-connections run <start> <end> <model>` sends each puzzle to an LLM via OpenRouter; guesses use structured JSON (`guess` + `reasoning`).
- **Logging:** Per-date, per-model runs in `data/games.json` — status, outcome, mistakes, invalid guesses, and full guess history.
- **Inspection:** `uv run llm-connections list <start> <end> <model>` summarizes results in the terminal.
- **Rules:** Standard Connections — four groups of four, game ends on four wrong guesses or all groups solved.
- **Secrets:** `OPENROUTER_API_KEY` in `.env` (local only; never published).
- **Public surface:** Static website — daily results, season standings, About/methodology, and baseline SEO (canonical, Open Graph, sitemap).

## Capabilities and Constraints

**Confirmed today**

- Download and cache puzzle data locally.
- Run arbitrary OpenRouter model IDs against a date range.
- Skip or force-overwrite completed runs (`--force`).
- Persist every guess with reasoning for later analysis and display.
- List and summarize results by model and date range.
- Static site with date archive, standings, guess replay, About page, and source/author links.

**Explicitly undecided**

- Which models to feature on the public site vs. run ad hoc.
- Charts / longitudinal visualizations beyond standings.
- Custom social card images.

**Terminology**

- **Run** — one model's attempt at one date's puzzle.
- **Outcome** — `solved` or `lost`.
- **Mistakes** — incorrect group guesses (max 4 before loss).
- **Invalid guesses** — malformed or rule-violating submissions rejected before scoring.

## Brand Commitments

- **Name:** llm-connections
- **Voice:** NYT Connections–adjacent — puzzle/game feel, playful but clear; not corporate or generic "AI benchmark" tone.
- **Constraint:** Not affiliated with The New York Times or Connections; do not imply official partnership or endorsement.

## Evidence on Hand

| Asset | Path | Notes |
|---|---|---|
| Puzzle archive | `data/connections.json` | Downloaded from Eyefyre repo |
| Run logs | `data/games.json` | Per-date, per-model results with guesses |
| Model catalog | `data/llm_options.json` | OpenRouter model options |
| CLI usage | `README.md` | Minimal; covers update and run |
| Tests | `tests/test_game.py` | Game logic and download behavior |

**Absences (do not fabricate):** testimonials, press coverage, official NYT relationship, pricing, licensing claims, or third-party endorsements.

## Product Principles

1. **Reproducible runs** — same puzzle data and logging format so results are comparable across models and dates.
2. **Longitudinal over snapshot** — the public value is trends and aggregates, not just today's score.
3. **CLI is source of truth** — the site displays logged data; it does not invent or edit run outcomes.
4. **Puzzle-native presentation** — the static site should feel like Connections culture, not a generic ML dashboard.
5. **Shareability by design** — every run should be worth publishing without manual cleanup.

## Accessibility & Inclusion

- Static site should meet baseline web accessibility (semantic HTML, sufficient contrast, keyboard navigation for interactive elements).
- CLI output is terminal-native; no product-specific accessibility requirement beyond readable defaults.
