"""Nightly: refresh puzzle archive and run the model suite for one date."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from llm_connections.applog import event
from llm_connections.backfill import MODELS
from llm_connections.engine import run_game
from llm_connections.game import download_connections
from llm_connections.log import GameAlreadyCompletedError, has_completed_entry
from llm_connections.telemetry import capture_run_failure, capture_sync_failure, monitor_nightly_job

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync_data.sh"


def _get_date_range() -> tuple[date, date]:
    end_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    beginning_date = end_date - timedelta(days=7)
    return beginning_date, end_date


def _run_game_for_date(target: date, model: str) -> str:
    if has_completed_entry(target, model):
        event(
            "skip — entry exists",
            stage="game",
            model=model,
            game_date=target,
            status="skipped",
        )
        return "skipped"
    try:
        event(
            "running game",
            stage="game",
            model=model,
            game_date=target,
            status="running",
        )
        run_game(target, model=model, force=False)
        return "done"
    except GameAlreadyCompletedError as exc:
        event(
            str(exc),
            stage="game",
            model=model,
            game_date=target,
            status="skipped",
        )
        return "skipped"
    except Exception as exc:
        event(
            f"ERROR for {model}: {exc}",
            stage="game",
            level=logging.ERROR,
            model=model,
            game_date=target,
            status="failed",
        )
        capture_run_failure(exc, game_date=target, model=model)
        return "failed"


@monitor_nightly_job
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

    event(
        "nightly suite starting",
        stage="nightly",
        status="running",
        models=len(suite),
        start=beginning_date.isoformat(),
        end=end_date.isoformat(),
    )

    ran = skipped = failed = 0
    for model in suite:
        day = beginning_date
        model_updates = 0
        while day <= end_date:
            result = _run_game_for_date(day, model)
            day += timedelta(days=1)
            if result == "done":
                ran += 1
                model_updates += 1
            elif result == "skipped":
                skipped += 1
            elif result == "failed":
                failed += 1

        # sync results back to once per model.
        if model_updates > 0:
            _sync_results()

    event(
        "nightly done",
        stage="nightly",
        status="done" if failed == 0 else "failed",
        ran=ran,
        skipped=skipped,
        failed=failed,
    )
    return failed


def _sync_results() -> None:
    """
    ONLY USE IN CLOUD.
    Pushes data files up to GCS.
    """
    import subprocess

    event("pushing data to GCS", stage="sync", status="running")
    result = subprocess.run(
        [str(SCRIPT), "push"],
        check=False,  # don't raise on failure
    )
    if result.returncode != 0:
        event(
            "sync_data.sh push failed",
            stage="sync",
            level=logging.WARNING,
            status="failed",
            returncode=result.returncode,
        )
        capture_sync_failure(result.returncode)
    else:
        event("sync_data.sh push ok", stage="sync", status="done")
