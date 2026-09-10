from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from llm_connections.log import GameAlreadyCompletedError
from llm_connections.nightly import _get_date_range, _run_game_for_date, _sync_results, run_nightly


def test_get_date_range(monkeypatch):
    fixed = datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc)

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed.replace(tzinfo=None)
            return fixed.astimezone(tz)

    monkeypatch.setattr("llm_connections.nightly.datetime", FakeDateTime)
    assert _get_date_range() == (date(2026, 9, 1), date(2026, 9, 8))


class TestRunGameForDate:
    def test_skips_when_completed_entry_exists(self, capsys):
        with (
            patch("llm_connections.nightly.has_completed_entry", return_value=True),
            patch("llm_connections.nightly.run_game") as run,
        ):
            result = _run_game_for_date(date(2026, 9, 1), "model-a")

        assert result == "skipped"
        run.assert_not_called()
        assert "skip" in capsys.readouterr().out

    def test_returns_done_on_success(self):
        with (
            patch("llm_connections.nightly.has_completed_entry", return_value=False),
            patch("llm_connections.nightly.run_game") as run,
        ):
            result = _run_game_for_date(date(2026, 9, 1), "model-a")

        assert result == "done"
        run.assert_called_once_with(date(2026, 9, 1), model="model-a", force=False)

    def test_returns_skipped_on_already_completed(self):
        with (
            patch("llm_connections.nightly.has_completed_entry", return_value=False),
            patch(
                "llm_connections.nightly.run_game",
                side_effect=GameAlreadyCompletedError("already done"),
            ),
        ):
            assert _run_game_for_date(date(2026, 9, 1), "model-a") == "skipped"

    def test_returns_failed_on_other_errors(self, capsys):
        with (
            patch("llm_connections.nightly.has_completed_entry", return_value=False),
            patch(
                "llm_connections.nightly.run_game",
                side_effect=RuntimeError("network"),
            ),
            patch("llm_connections.nightly.capture_run_failure") as capture,
        ):
            assert _run_game_for_date(date(2026, 9, 1), "model-a") == "failed"

        assert "ERROR" in capsys.readouterr().out
        capture.assert_called_once()
        assert capture.call_args.kwargs["game_date"] == date(2026, 9, 1)
        assert capture.call_args.kwargs["model"] == "model-a"


class TestRunNightly:
    def test_downloads_then_counts_failures(self, capsys):
        with (
            patch("llm_connections.nightly.download_connections") as download,
            patch(
                "llm_connections.nightly._get_date_range",
                return_value=(date(2026, 9, 1), date(2026, 9, 2)),
            ),
            patch(
                "llm_connections.nightly._run_game_for_date",
                side_effect=["done", "failed", "skipped", "failed"],
            ) as run_one,
            patch("llm_connections.nightly._sync_results") as sync,

        ):
            failed = run_nightly(models=["m1", "m2"])

        download.assert_called_once()
        assert run_one.call_count == 4
        assert failed == 2
        assert "ran=1 skipped=1 failed=2" in capsys.readouterr().out
        sync.assert_called_once()

    def test_uses_default_models_when_none_passed(self):
        with (
            patch("llm_connections.nightly.download_connections"),
            patch(
                "llm_connections.nightly._get_date_range",
                return_value=(date(2026, 9, 1), date(2026, 9, 1)),
            ),
            patch("llm_connections.nightly.MODELS", ["default-a"]),
            patch(
                "llm_connections.nightly._run_game_for_date",
                return_value="done",
            ) as run_one,
            patch("llm_connections.nightly._sync_results") as sync,
        ):
            assert run_nightly(models=None) == 0

        run_one.assert_called_once_with(date(2026, 9, 1), "default-a")
        sync.assert_called_once()


def test_sync_results_reports_soft_failure():
    completed = MagicMock(returncode=2)
    with (
        patch("subprocess.run", return_value=completed) as run,
        patch("llm_connections.nightly.capture_sync_failure") as capture,
    ):
        _sync_results()

    run.assert_called_once()
    capture.assert_called_once_with(2)