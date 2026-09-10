import json
from datetime import date, datetime

import pytest

from llm_connections.log import (
    GameAlreadyCompletedError,
    complete_run,
    has_completed_entry,
    list_results,
    log_guess,
    start_run,
    _date_key,
    _load_log,
)


MODEL = "openai/gpt-4.1"
DAY = date(2026, 9, 1)


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "games.json"
    monkeypatch.setattr("llm_connections.log.LOG_FILE", str(path))
    return path


class TestDateKey:
    def test_formats_date(self):
        assert _date_key(DAY) == "2026-09-01"

    def test_formats_datetime(self):
        assert _date_key(datetime(2026, 9, 1, 15, 30)) == "2026-09-01"


class TestLoadLog:
    def test_missing_file_returns_empty(self, log_path):
        assert _load_log() == {}

    def test_empty_file_returns_empty(self, log_path):
        log_path.write_text("")
        assert _load_log() == {}


class TestStartRun:
    def test_creates_in_progress_entry(self, log_path):
        start_run(DAY, MODEL)

        data = json.loads(log_path.read_text())
        assert data["2026-09-01"][MODEL] == {
            "status": "in_progress",
            "guesses": [],
        }

    def test_allows_restart_of_in_progress(self, log_path):
        start_run(DAY, MODEL)
        log_guess(DAY, MODEL, {"guess": ["A", "B", "C", "D"]})
        start_run(DAY, MODEL)

        data = json.loads(log_path.read_text())
        assert data["2026-09-01"][MODEL]["guesses"] == []

    def test_blocks_completed_without_force(self, log_path):
        start_run(DAY, MODEL)
        complete_run(
            DAY,
            MODEL,
            outcome="solved",
            mistakes=0,
            invalid_guesses=0,
            solved_groups=4,
            llm_wait_s=1.0,
        )

        with pytest.raises(GameAlreadyCompletedError, match="already completed"):
            start_run(DAY, MODEL)

    def test_force_overwrites_completed(self, log_path):
        start_run(DAY, MODEL)
        complete_run(
            DAY,
            MODEL,
            outcome="solved",
            mistakes=0,
            invalid_guesses=0,
            solved_groups=4,
            llm_wait_s=1.0,
        )
        start_run(DAY, MODEL, force=True)

        data = json.loads(log_path.read_text())
        assert data["2026-09-01"][MODEL]["status"] == "in_progress"
        assert data["2026-09-01"][MODEL]["guesses"] == []


class TestLogGuess:
    def test_appends_guess_to_in_progress_run(self, log_path):
        start_run(DAY, MODEL)
        log_guess(DAY, MODEL, {"guess": ["HAIL", "RAIN", "SLEET", "SNOW"], "success": True})

        data = json.loads(log_path.read_text())
        assert data["2026-09-01"][MODEL]["guesses"] == [
            {"guess": ["HAIL", "RAIN", "SLEET", "SNOW"], "success": True}
        ]

    def test_raises_without_start_run(self, log_path):
        with pytest.raises(ValueError, match="No in-progress run"):
            log_guess(DAY, MODEL, {"guess": []})

    def test_raises_after_complete(self, log_path):
        start_run(DAY, MODEL)
        complete_run(
            DAY,
            MODEL,
            outcome="lost",
            mistakes=4,
            invalid_guesses=0,
            solved_groups=1,
            llm_wait_s=0.5,
        )

        with pytest.raises(ValueError, match="No in-progress run"):
            log_guess(DAY, MODEL, {"guess": []})


class TestCompleteRun:
    def test_writes_outcome_and_metrics(self, log_path):
        start_run(DAY, MODEL)
        log_guess(DAY, MODEL, {"guess": ["A", "B", "C", "D"]})
        complete_run(
            DAY,
            MODEL,
            outcome="solved",
            mistakes=1,
            invalid_guesses=2,
            solved_groups=4,
            llm_wait_s=3.5,
            input_tokens=100,
            output_tokens=50,
            total_cost=0.01,
        )

        data = json.loads(log_path.read_text())
        run = data["2026-09-01"][MODEL]
        assert run["status"] == "completed"
        assert run["outcome"] == "solved"
        assert run["mistakes"] == 1
        assert run["invalid_guesses"] == 2
        assert run["solved_groups"] == 4
        assert run["llm_wait_s"] == 3.5
        assert run["input_tokens"] == 100
        assert run["output_tokens"] == 50
        assert run["total_cost"] == 0.01
        assert len(run["guesses"]) == 1

    def test_raises_without_start_run(self, log_path):
        with pytest.raises(ValueError, match="No run for"):
            complete_run(
                DAY,
                MODEL,
                outcome="solved",
                mistakes=0,
                invalid_guesses=0,
                solved_groups=4,
                llm_wait_s=0.0,
            )


class TestHasCompletedEntry:
    def test_false_when_missing(self, log_path):
        assert has_completed_entry(DAY, MODEL) is False

    def test_false_when_in_progress(self, log_path):
        start_run(DAY, MODEL)
        assert has_completed_entry(DAY, MODEL) is False

    def test_true_when_completed(self, log_path):
        start_run(DAY, MODEL)
        complete_run(
            DAY,
            MODEL,
            outcome="solved",
            mistakes=0,
            invalid_guesses=0,
            solved_groups=4,
            llm_wait_s=1.0,
        )
        assert has_completed_entry(DAY, MODEL) is True


class TestListResults:
    def test_returns_runs_in_range(self, log_path):
        for day in (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 4)):
            start_run(day, MODEL)
            complete_run(
                day,
                MODEL,
                outcome="solved",
                mistakes=0,
                invalid_guesses=0,
                solved_groups=4,
                llm_wait_s=1.0,
            )

        results = list_results(date(2026, 9, 1), date(2026, 9, 3), MODEL)

        assert [r["date"] for r in results] == ["2026-09-01", "2026-09-02"]
        assert all(r["status"] == "completed" for r in results)

    def test_skips_other_models(self, log_path):
        start_run(DAY, MODEL)
        complete_run(
            DAY,
            MODEL,
            outcome="solved",
            mistakes=0,
            invalid_guesses=0,
            solved_groups=4,
            llm_wait_s=1.0,
        )
        start_run(DAY, "other/model")
        complete_run(
            DAY,
            "other/model",
            outcome="lost",
            mistakes=4,
            invalid_guesses=0,
            solved_groups=0,
            llm_wait_s=1.0,
        )

        results = list_results(DAY, DAY, MODEL)
        assert len(results) == 1
        assert results[0]["outcome"] == "solved"

    def test_empty_range(self, log_path):
        assert list_results(DAY, DAY, MODEL) == []
