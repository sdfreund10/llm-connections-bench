from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from llm_connections import telemetry


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


class TestNightlyCheckin:
    def test_noop_locally_without_force(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.delenv("DATA_BUCKET", raising=False)
        monkeypatch.delenv("SENTRY_MONITOR_SLUG", raising=False)
        monkeypatch.setenv("SENTRY_CRONS", "auto")

        with patch("llm_connections.telemetry.capture_checkin") as checkin:
            with telemetry.nightly_checkin() as finish:
                finish(True)

        checkin.assert_not_called()

    def test_sends_ok_when_cloud_and_success(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.setenv("DATA_BUCKET", "bucket")
        monkeypatch.setenv("SENTRY_CRONS", "auto")

        with patch(
            "llm_connections.telemetry.capture_checkin",
            return_value="check-1",
        ) as checkin:
            with telemetry.nightly_checkin() as finish:
                finish(True)

        assert checkin.call_count == 2
        assert checkin.call_args_list[0].kwargs["status"] == telemetry.MonitorStatus.IN_PROGRESS
        assert checkin.call_args_list[1].kwargs["status"] == telemetry.MonitorStatus.OK
        assert checkin.call_args_list[1].kwargs["check_in_id"] == "check-1"
        assert checkin.call_args_list[0].kwargs["monitor_slug"] == "llm-connections-nightly"

    def test_sends_error_on_failure_flag(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.setenv("SENTRY_CRONS", "1")

        with patch(
            "llm_connections.telemetry.capture_checkin",
            return_value="check-1",
        ) as checkin:
            with telemetry.nightly_checkin() as finish:
                finish(False)

        assert checkin.call_args_list[1].kwargs["status"] == telemetry.MonitorStatus.ERROR

    def test_sends_error_on_exception(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
        monkeypatch.setenv("SENTRY_CRONS", "1")

        with patch(
            "llm_connections.telemetry.capture_checkin",
            return_value="check-1",
        ) as checkin:
            with pytest.raises(RuntimeError, match="boom"):
                with telemetry.nightly_checkin() as _finish:
                    raise RuntimeError("boom")

        assert checkin.call_args_list[1].kwargs["status"] == telemetry.MonitorStatus.ERROR
