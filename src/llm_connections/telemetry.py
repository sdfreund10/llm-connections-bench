"""Sentry error reporting, per-game transactions, and nightly cron check-ins.

Enabled when ``SENTRY_DSN`` is set (Secret Manager on the Cloud Run Job).
Local CLI stays quiet unless you export a DSN for debugging.
"""

from __future__ import annotations

import functools
import os
from datetime import date

import sentry_sdk
from sentry_sdk.crons import capture_checkin
from sentry_sdk.crons.consts import MonitorStatus

# Matches Cloud Scheduler in DEPLOY.md (0 6 * * * America/New_York).
DEFAULT_MONITOR_SLUG = "llm-connections-nightly"
DEFAULT_MONITOR_SCHEDULE = "0 6 * * *"
DEFAULT_MONITOR_TIMEZONE = "America/New_York"


def init_sentry(*, command: str | None = None) -> bool:
    """Initialize the Sentry SDK. Returns True when a DSN was configured."""
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT") or _default_environment(),
        release=os.environ.get("SENTRY_RELEASE") or None,
        traces_sample_rate=_traces_sample_rate(),
        send_default_pii=False,
    )

    scope = sentry_sdk.get_isolation_scope()
    if command:
        scope.set_tag("command", command)
    for env_key, tag in (
        ("CLOUD_RUN_EXECUTION", "cloud_run_execution"),
        ("CLOUD_RUN_JOB", "cloud_run_job"),
        ("CLOUD_RUN_TASK_INDEX", "cloud_run_task_index"),
    ):
        value = os.environ.get(env_key)
        if value:
            scope.set_tag(tag, value)
    return True


def capture_run_failure(
    exc: BaseException,
    *,
    game_date: date,
    model: str,
) -> None:
    """Report a per-game failure that nightly/backfill otherwise swallow."""
    if not _dsn_configured():
        return
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("model", model)
        scope.set_tag("game_date", game_date.isoformat())
        scope.set_context(
            "run",
            {"date": game_date.isoformat(), "model": model},
        )
        sentry_sdk.capture_exception(exc)


def capture_sync_failure(returncode: int) -> None:
    """Report a soft-failed GCS push from nightly mid-suite sync."""
    if not _dsn_configured():
        return
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("stage", "sync_push")
        sentry_sdk.capture_message(
            f"sync_data.sh push exited {returncode}",
            level="error",
        )


def record_game(func):
    """Wrap ``run_game`` in a Sentry performance transaction when DSN is set."""

    @functools.wraps(func)
    def wrapper(date: date, model: str = "openai/gpt-4.1", force: bool = False):
        if not _dsn_configured():
            return func(date=date, model=model, force=force)
        with sentry_sdk.start_transaction(
            op="task.game",
            name=f"run_game {model} {date.isoformat()}",
        ) as transaction:
            transaction.set_tag("model", model)
            transaction.set_tag("game_date", date.isoformat())

            game_metadata = func(date=date, model=model, force=force)

            transaction.set_tag("outcome", game_metadata.outcome)
            transaction.set_data("mistakes", game_metadata.mistakes)
            transaction.set_data("invalid_guesses", game_metadata.invalid_guesses)
            transaction.set_data("solved_groups", game_metadata.solved_groups)
            transaction.set_data("llm_wait_s", game_metadata.llm_wait_s)
            transaction.set_data("input_tokens", game_metadata.input_tokens)
            transaction.set_data("output_tokens", game_metadata.output_tokens)
            transaction.set_data("total_cost", game_metadata.total_cost)
            return game_metadata

    return wrapper


def monitor_nightly_job(func):
    """Cron check-ins around ``run_nightly``; OK when returned failure count is 0."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _crons_enabled():
            return func(*args, **kwargs)
        slug = os.environ.get("SENTRY_MONITOR_SLUG", "").strip() or DEFAULT_MONITOR_SLUG
        schedule = (
            os.environ.get("SENTRY_MONITOR_SCHEDULE", "").strip() or DEFAULT_MONITOR_SCHEDULE
        )
        timezone = (
            os.environ.get("SENTRY_MONITOR_TIMEZONE", "").strip() or DEFAULT_MONITOR_TIMEZONE
        )
        monitor_config = {
            "schedule": {"type": "crontab", "value": schedule},
            "timezone": timezone,
            "checkin_margin": 30,
            # Match Cloud Run Job --task-timeout=24h
            "max_runtime": 1440,
            "failure_issue_threshold": 1,
            "recovery_threshold": 1,
        }

        check_in_id = capture_checkin(
            monitor_slug=slug,
            status=MonitorStatus.IN_PROGRESS,
            monitor_config=monitor_config,
        )
        try:
            num_failed = func(*args, **kwargs)
            capture_checkin(
                monitor_slug=slug,
                check_in_id=check_in_id,
                status=MonitorStatus.OK if num_failed == 0 else MonitorStatus.ERROR,
                monitor_config=monitor_config,
            )
            return num_failed
        except BaseException:
            capture_checkin(
                monitor_slug=slug,
                check_in_id=check_in_id,
                status=MonitorStatus.ERROR,
                monitor_config=monitor_config,
            )
            raise

    return wrapper


def _dsn_configured() -> bool:
    return bool(os.environ.get("SENTRY_DSN", "").strip())


def _default_environment() -> str:
    if os.environ.get("DATA_BUCKET"):
        return "production"
    return "local"


def _traces_sample_rate() -> float:
    raw = os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "1.0").strip()
    try:
        return float(raw)
    except ValueError:
        return 1.0


def _crons_enabled() -> bool:
    if not _dsn_configured():
        return False
    flag = os.environ.get("SENTRY_CRONS", "auto").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    # auto: cloud Job (DATA_BUCKET) or explicit monitor slug
    if os.environ.get("SENTRY_MONITOR_SLUG", "").strip():
        return True
    return bool(os.environ.get("DATA_BUCKET", "").strip())
