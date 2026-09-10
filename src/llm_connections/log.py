from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Any
import os

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
LOG_FILE = os.path.join(DATA_DIR, "games.json")

STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"

class GameAlreadyCompletedError(Exception):
    """Raised when a completed game is re-run without force=True."""

def _date_key(date: date | datetime) -> str:
    day = date.date() if isinstance(date, datetime) else date
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

def has_completed_entry(day: date, model: str) -> bool:
    data = _load_log()
    date_key = _date_key(day)
    run = _get_run(data, date_key, model)
    return _is_completed(run)


def start_run(date: date, llm_model: str, force: bool = False) -> None:
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


def log_guess(date: date, llm_model: str, guess: dict) -> None:
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
    date: date,
    llm_model: str,
    *,
    outcome: str,
    mistakes: int,
    invalid_guesses: int,
    solved_groups: int,
    llm_wait_s: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_cost: float = 0.0,
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
    run["solved_groups"] = solved_groups
    run["llm_wait_s"] = llm_wait_s
    run["input_tokens"] = input_tokens
    run["output_tokens"] = output_tokens
    run["total_cost"] = total_cost
    _save_log(data)


def list_results(
    start: date,
    end: date,
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
        day += timedelta(days=1)
    return results