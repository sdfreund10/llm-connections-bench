from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from llm_connections import telemetry
from llm_connections.engine import run_game
from llm_connections.nightly import run_nightly


class TestInitSentry:
    def test_noop_without_dsn(self, monkeypatch):
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        with patch("llm_connections.telemetry.sentry_sdk.init") as init:
            assert telemetry.init_sentry(command="nightly") is False
        init.assert_not_called()

    def test_inits_with_dsn_and_tags(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.setenv("DATA_BUCKET", "bucket")
        monkeypatch.setenv("CLOUD_RUN_EXECUTION", "exec-123")
        monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("SENTRY_RELEASE", raising=False)

        scope = MagicMock()
        with (
            patch("llm_connections.telemetry.sentry_sdk.init") as init,
            patch(
                "llm_connections.telemetry.sentry_sdk.get_isolation_scope",
                return_value=scope,
            ),
        ):
            assert telemetry.init_sentry(command="nightly") is True

        init.assert_called_once()
        kwargs = init.call_args.kwargs
        assert kwargs["dsn"] == "https://key@example.com/1"
        assert kwargs["environment"] == "production"
        assert kwargs["send_default_pii"] is False
        scope.set_tag.assert_any_call("command", "nightly")
        scope.set_tag.assert_any_call("cloud_run_execution", "exec-123")


class TestCaptureHelpers:
    def test_capture_run_failure_skipped_without_dsn(self, monkeypatch):
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        with patch("llm_connections.telemetry.sentry_sdk.capture_exception") as capture:
            telemetry.capture_run_failure(
                RuntimeError("boom"),
                game_date=date(2026, 9, 1),
                model="m",
            )
        capture.assert_not_called()

    def test_capture_run_failure_sends_exception(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        scope = MagicMock()
        scope.__enter__ = MagicMock(return_value=scope)
        scope.__exit__ = MagicMock(return_value=False)
        exc = RuntimeError("boom")

        with (
            patch("llm_connections.telemetry.sentry_sdk.new_scope", return_value=scope),
            patch("llm_connections.telemetry.sentry_sdk.capture_exception") as capture,
        ):
            telemetry.capture_run_failure(
                exc,
                game_date=date(2026, 9, 1),
                model="openai/gpt-4.1",
            )

        scope.set_tag.assert_any_call("model", "openai/gpt-4.1")
        scope.set_tag.assert_any_call("game_date", "2026-09-01")
        capture.assert_called_once_with(exc)

    def test_capture_sync_failure(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        scope = MagicMock()
        scope.__enter__ = MagicMock(return_value=scope)
        scope.__exit__ = MagicMock(return_value=False)

        with (
            patch("llm_connections.telemetry.sentry_sdk.new_scope", return_value=scope),
            patch("llm_connections.telemetry.sentry_sdk.capture_message") as capture,
        ):
            telemetry.capture_sync_failure(3)

        scope.set_tag.assert_called_once_with("stage", "sync_push")
        capture.assert_called_once_with(
            "sync_data.sh push exited 3",
            level="error",
        )


def _sample_metadata(**overrides) -> SimpleNamespace:
    data = {
        "outcome": "solved",
        "mistakes": 1,
        "invalid_guesses": 0,
        "solved_groups": 4,
        "llm_wait_s": 2.5,
        "input_tokens": 100,
        "output_tokens": 50,
        "total_cost": 0.01,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class TestRecordGame:
    def test_passthrough_without_dsn(self, monkeypatch):
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        metadata = _sample_metadata()

        @telemetry.record_game
        def stub(date, model="openai/gpt-4.1", force=False):
            return metadata

        with patch("llm_connections.telemetry.sentry_sdk.start_transaction") as start:
            assert stub(date(2026, 9, 1), model="m") is metadata
        start.assert_not_called()

    def test_records_transaction_from_metadata(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        metadata = _sample_metadata()
        txn = MagicMock()
        txn.__enter__ = MagicMock(return_value=txn)
        txn.__exit__ = MagicMock(return_value=False)

        @telemetry.record_game
        def stub(date, model="openai/gpt-4.1", force=False):
            return metadata

        with patch(
            "llm_connections.telemetry.sentry_sdk.start_transaction",
            return_value=txn,
        ) as start:
            assert stub(date(2026, 9, 1), model="openai/gpt-4.1") is metadata

        start.assert_called_once_with(
            op="task.game",
            name="run_game openai/gpt-4.1 2026-09-01",
        )
        txn.set_tag.assert_any_call("model", "openai/gpt-4.1")
        txn.set_tag.assert_any_call("game_date", "2026-09-01")
        txn.set_tag.assert_any_call("outcome", "solved")
        txn.set_data.assert_any_call("mistakes", 1)
        txn.set_data.assert_any_call("llm_wait_s", 2.5)
        txn.set_data.assert_any_call("total_cost", 0.01)

    def test_run_game_is_wrapped(self):
        assert run_game.__wrapped__.__name__ == "run_game"


class TestMonitorNightlyJob:
    def test_passthrough_when_crons_disabled(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.delenv("DATA_BUCKET", raising=False)
        monkeypatch.delenv("SENTRY_MONITOR_SLUG", raising=False)
        monkeypatch.setenv("SENTRY_CRONS", "auto")

        @telemetry.monitor_nightly_job
        def stub(*, models=None):
            return 2

        with patch("llm_connections.telemetry.capture_checkin") as checkin:
            assert stub(models=["m"]) == 2
        checkin.assert_not_called()

    def test_sends_ok_when_zero_failures(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.setenv("DATA_BUCKET", "bucket")
        monkeypatch.setenv("SENTRY_CRONS", "auto")

        @telemetry.monitor_nightly_job
        def stub(*, models=None):
            return 0

        with patch(
            "llm_connections.telemetry.capture_checkin",
            return_value="check-1",
        ) as checkin:
            assert stub() == 0

        assert checkin.call_count == 2
        assert checkin.call_args_list[0].kwargs["status"] == telemetry.MonitorStatus.IN_PROGRESS
        assert checkin.call_args_list[1].kwargs["status"] == telemetry.MonitorStatus.OK
        assert checkin.call_args_list[1].kwargs["check_in_id"] == "check-1"
        assert checkin.call_args_list[0].kwargs["monitor_slug"] == "llm-connections-nightly"

    def test_sends_error_when_failures(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.setenv("SENTRY_CRONS", "1")

        @telemetry.monitor_nightly_job
        def stub(*, models=None):
            return 3

        with patch(
            "llm_connections.telemetry.capture_checkin",
            return_value="check-1",
        ) as checkin:
            assert stub() == 3

        assert checkin.call_args_list[1].kwargs["status"] == telemetry.MonitorStatus.ERROR

    def test_sends_error_on_exception(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.setenv("SENTRY_CRONS", "1")

        @telemetry.monitor_nightly_job
        def stub(*, models=None):
            raise RuntimeError("boom")

        with patch(
            "llm_connections.telemetry.capture_checkin",
            return_value="check-1",
        ) as checkin:
            with pytest.raises(RuntimeError, match="boom"):
                stub()

        assert checkin.call_args_list[1].kwargs["status"] == telemetry.MonitorStatus.ERROR

    def test_run_nightly_is_wrapped(self):
        assert run_nightly.__wrapped__.__name__ == "run_nightly"
