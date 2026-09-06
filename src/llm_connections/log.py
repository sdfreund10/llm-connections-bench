import datetime
import json
from pathlib import Path
from typing import Any
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "games.json")

STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"

class GameAlreadyCompletedError(Exception):
    """Raised when a completed game is re-run without force=True."""

def _date_key(date: datetime.date | datetime.datetime) -> str:
    day = date.date() if isinstance(date, datetime.datetime) else date
    return day.isoformat()


def _log_path() -> Path:
    return Path(LOG_FILE)


def _load_log() -> dict[str, Any]:
    path = _log_path()
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _save_log(data: dict[str, Any]) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def _get_run(data: dict[str, Any], date_key: str, llm_model: str) -> dict[str, Any] | None:
    entry = data.get(date_key, {}).get(llm_model)
    return entry if isinstance(entry, dict) else None


def _set_run(data: dict[str, Any], date_key: str, llm_model: str, run: dict[str, Any]) -> None:
    data.setdefault(date_key, {})[llm_model] = run


def _is_completed(run: dict[str, Any] | None) -> bool:
    return run is not None and run.get("status") == STATUS_COMPLETED


def start_run(date: datetime.date, llm_model: str, force: bool = False) -> None:
    data = _load_log()
    date_key = _date_key(date)
    existing = _get_run(data, date_key, llm_model)

    if _is_completed(existing) and not force:
        raise GameAlreadyCompletedError(
            f"Game for {date_key} with model {llm_model} is already completed. "
            "Pass force=True to overwrite."
        )

    _set_run(data, date_key, llm_model, {
        "status": STATUS_IN_PROGRESS,
        "guesses": [],
    })
    _save_log(data)


def log_guess(date: datetime.date, llm_model: str, guess: dict) -> None:
    data = _load_log()
    date_key = _date_key(date)
    run = _get_run(data, date_key, llm_model)
    if run is None or run.get("status") != STATUS_IN_PROGRESS:
        raise ValueError(
            f"No in-progress run for {date_key} / {llm_model}. Call start_run first."
        )

    run["guesses"].append(guess)
    _save_log(data)


def complete_run(
    date: datetime.date,
    llm_model: str,
    *,
    outcome: str,
    mistakes: int,
    invalid_guesses: int,
) -> None:
    data = _load_log()
    date_key = _date_key(date)
    run = _get_run(data, date_key, llm_model)
    if run is None:
        raise ValueError(
            f"No run for {date_key} / {llm_model}. Call start_run first."
        )

    run["status"] = STATUS_COMPLETED
    run["outcome"] = outcome
    run["mistakes"] = mistakes
    run["invalid_guesses"] = invalid_guesses
    _save_log(data)


def list_results(
    start: datetime.date,
    end: datetime.date,
    llm_model: str,
) -> list[dict[str, Any]]:
    data = _load_log()
    results = []
    day = start
    while day <= end:
        date_key = day.isoformat()
        run = _get_run(data, date_key, llm_model)
        if run is not None:
            results.append({"date": date_key, **run})
        day += datetime.timedelta(days=1)
    return results