"""Sentry error reporting and nightly cron check-ins.

Enabled when ``SENTRY_DSN`` is set (Secret Manager on the Cloud Run Job).
Local CLI stays quiet unless you export a DSN for debugging.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Callable

import sentry_sdk
from sentry_sdk.crons import capture_checkin
from sentry_sdk.crons.consts import MonitorStatus

# Matches Cloud Scheduler in DEPLOY.md (0 6 * * * America/New_York).
DEFAULT_MONITOR_SLUG = "llm-connections-nightly"
DEFAULT_MONITOR_SCHEDULE = "0 6 * * *"
DEFAULT_MONITOR_TIMEZONE = "America/New_York"

FinishCheckin = Callable[[bool], None]


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


@contextmanager
def nightly_checkin() -> Iterator[FinishCheckin]:
    """Send Sentry Cron check-ins for the cloud nightly Job.

    Enabled when ``SENTRY_DSN`` is set and either ``DATA_BUCKET`` is set
    (Cloud Run Job) or ``SENTRY_MONITOR_SLUG`` / ``SENTRY_CRONS=1`` forces it.
    Disable with ``SENTRY_CRONS=0``.

    Yields ``finish(success: bool)``. Call it after ``run_nightly`` so a
    non-zero failure count marks the monitor ERROR even without an exception.
    """
    if not _crons_enabled():
        yield lambda _success: None
        return

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
    finished = False

    def finish(success: bool) -> None:
        nonlocal finished
        if finished:
            return
        capture_checkin(
            monitor_slug=slug,
            check_in_id=check_in_id,
            status=MonitorStatus.OK if success else MonitorStatus.ERROR,
            monitor_config=monitor_config,
        )
        finished = True

    try:
        yield finish
    except BaseException:
        finish(False)
        raise
    else:
        if not finished:
            finish(True)


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
