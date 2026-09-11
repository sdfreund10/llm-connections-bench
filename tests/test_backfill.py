from datetime import date
from unittest.mock import patch

import pytest

from llm_connections import applog
from llm_connections.backfill import run_backfill
from llm_connections.log import GameAlreadyCompletedError


class TestRunBackfill:
    def test_rejects_inverted_range(self):
        with pytest.raises(ValueError, match="end date must be on or after start date"):
            run_backfill(start=date(2026, 9, 5), end=date(2026, 9, 1), models=["m"])

    def test_skips_completed_runs_and_counts_results(self, monkeypatch, capsys):
        monkeypatch.setenv("LOG_FORMAT", "text")
        monkeypatch.delenv("DATA_BUCKET", raising=False)
        applog.configure_logging(force=True)
        start = date(2026, 9, 1)
        end = date(2026, 9, 3)

        def has_completed(day, model):
            return day == date(2026, 9, 2)

        def run_game(day, model=None, force=False):
            if day == date(2026, 9, 3):
                raise RuntimeError("boom")

        with (
            patch("llm_connections.backfill.has_completed_entry", side_effect=has_completed),
            patch("llm_connections.backfill.run_game", side_effect=run_game) as run,
            patch("llm_connections.backfill.capture_run_failure") as capture,
        ):
            run_backfill(start=start, end=end, models=["model-a"])

        assert run.call_count == 2
        out = capsys.readouterr().out
        assert "backfill done" in out
        assert "ran=1" in out
        assert "skipped=1" in out
        assert "failed=1" in out
        capture.assert_called_once()
        assert capture.call_args.kwargs["model"] == "model-a"
        assert capture.call_args.kwargs["game_date"] == date(2026, 9, 3)

    def test_treats_already_completed_error_as_skip(self, monkeypatch, capsys):
        monkeypatch.setenv("LOG_FORMAT", "text")
        monkeypatch.delenv("DATA_BUCKET", raising=False)
        applog.configure_logging(force=True)
        with (
            patch("llm_connections.backfill.has_completed_entry", return_value=False),
            patch(
                "llm_connections.backfill.run_game",
                side_effect=GameAlreadyCompletedError("done"),
            ),
        ):
            run_backfill(
                start=date(2026, 9, 1),
                end=date(2026, 9, 1),
                models=["model-a"],
            )

        out = capsys.readouterr().out
        assert "backfill done" in out
        assert "ran=0" in out
        assert "skipped=1" in out
        assert "failed=0" in out

    def test_uses_default_models_when_none_passed(self):
        with (
            patch("llm_connections.backfill.has_completed_entry", return_value=True),
            patch("llm_connections.backfill.MODELS", ["a", "b"]),
            patch("llm_connections.backfill.run_game") as run,
        ):
            run_backfill(
                start=date(2026, 9, 1),
                end=date(2026, 9, 1),
                models=None,
            )

        run.assert_not_called()
