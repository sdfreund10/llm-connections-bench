from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from llm_connections.nightly import _get_date_range


def test_get_date_range(monkeypatch):
    fixed = datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc)

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed.replace(tzinfo=None)
            return fixed.astimezone(tz)

    monkeypatch.setattr("llm_connections.nightly.datetime", FakeDateTime)
    assert _get_date_range() == (date(2026, 9, 2), date(2026, 9, 9))
