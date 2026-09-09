"""Nightly: refresh puzzle archive and run the model suite for one date."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from llm_connections.backfill import MODELS
from llm_connections.engine import run_game
from llm_connections.game import download_connections
from llm_connections.log import GameAlreadyCompletedError, list_results


def _has_entry(day: date, model: str) -> bool:
    return bool(list_results(day, day, model))

def _get_date_range() -> tuple[date, date]:
    end_date = datetime.now(timezone.utc).date()
    beginning_date = end_date - timedelta(days=7)
    return beginning_date, end_date

def _run_game_for_date(target: date, model: str) -> None:
    if _has_entry(target, model):
        print(f"[{target}] skip — entry exists for {model}")
        return 'skipped'
    try:
        print(f"[{target}] running {model}")
        run_game(target, model=model, force=False)
        return 'done'
    except GameAlreadyCompletedError as exc:
        print(exc)
        return 'skipped'
    except Exception as exc:
        failed += 1
        print(f"[{target}] ERROR for {model}: {exc}")
        return 'failed'

def run_nightly(
    *,
    models: list[str] | None = None,
) -> int:
    """
    Update connections.json, then run each model for the target date.
    Returns the number of hard failures (non-zero → Job should fail).
    """
    download_connections()
    # Run last week of data. Already completed entries will be skipped, but new models will immediately start with a week of data.
    beginning_date, end_date = _get_date_range()
    suite = models if models is not None else MODELS

    print(f"Nightly target date: {target}")
    print(f"Models: {len(suite)}")

    ran = skipped = failed = 0
    for model in suite:
        for date in range(beginning_date, end_date):
            result = _run_game_for_date(date, model)
            if result == 'done':
                ran += 1
            elif result == 'skipped':
                skipped += 1
            elif result == 'failed':
                failed += 1

    print(f"\nNightly done — ran={ran} skipped={skipped} failed={failed}")
    return failed
