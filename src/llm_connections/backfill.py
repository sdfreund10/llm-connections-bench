"""Backfill Connections runs across a fixed model suite and date range."""

from __future__ import annotations

from datetime import date, timedelta

from llm_connections.engine import run_game
from llm_connections.log import GameAlreadyCompletedError, list_results

DEFAULT_START = date(2026, 8, 15)
DEFAULT_END = date(2026, 9, 4)

# Edit this list to add/remove models from the suite.
MODELS: list[str] = [
    # OpenAI
    # "openai/gpt-4.1-nano",
    "openai/gpt-4.1-mini",
    "openai/gpt-4.1",
    "openai/gpt-5.6-luna",
    # "openai/gpt-5.6-sol",

    # Anthropic
    "anthropic/claude-haiku-4.5",
    "anthropic/claude-sonnet-5",
    # "anthropic/claude-opus-5",

    # Google
    "google/gemini-3.5-flash-lite",
    "google/gemini-3.7-flash",
    "google/gemini-3.8-flash",

    # Z.ai
    "z-ai/glm-5.3-flash",
    # "z-ai/glm-5.3",

    # DeepSeek
    # "deepseek/deepseek-v4-flash-0731", # EXTREMELY SLOW - might not be worth it

    # xAI
    "x-ai/grok-4.3",
    # "x-ai/grok-4.6",

    # Qwen
    "qwen/qwen3.8-flash",
    # "qwen/qwen3.8-27b",
    # "qwen/qwen3.8-2.4t-a95b",
]

# Promotion ladders (only if entry underperforms)
# OpenAI: nano → gpt-4.1-mini → gpt-4.1 → gpt-5.6-luna → gpt-5.6-sol → (maybe) gpt-6-astra
# Anthropic: haiku → claude-sonnet-5 → claude-opus-5 → (rarely) claude-fable-5.1
# Google: gemini-3.5-flash-lite → gemini-3.7-flash → gemini-3.8-flash → gemini-3.1-pro-preview
# Z.ai: glm-5.3-flash → glm-5.3
# DeepSeek: flash → deepseek-v4-pro-0813
# xAI: grok-4.3 → grok-4.5 → grok-4.6
# Qwen: qwen3.8-flash → qwen3.8-27b → qwen3.8-2.4t-a95b

def _has_entry(day: date, model: str) -> bool:
    return bool(list_results(day, day, model))


def run_backfill(
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    models: list[str] | None = None,
) -> None:
    if end < start:
        raise ValueError("end date must be on or after start date")

    suite = models if models is not None else MODELS
    ran = skipped = failed = 0

    for model in suite:
        print(f"\n=== {model} ({start} → {end}) ===")
        day = start
        while day <= end:
            if _has_entry(day, model):
                print(f"[{day}] skip — entry exists for {model}")
                skipped += 1
                day += timedelta(days=1)
                continue

            try:
                print(f"[{day}] running {model}")
                run_game(day, model=model, force=False)
                ran += 1
            except GameAlreadyCompletedError as exc:
                print(exc)
                skipped += 1
            except Exception as exc:
                failed += 1
                print(f"[{day}] ERROR for {model}: {exc}")
            day += timedelta(days=1)

    print(f"\nDone — ran={ran} skipped={skipped} failed={failed}")
