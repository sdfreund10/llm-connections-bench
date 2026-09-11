import json

from llm_connections import applog


def test_configure_text_format(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.delenv("DATA_BUCKET", raising=False)
    applog.configure_logging(force=True)

    applog.event(
        "hello",
        stage="game",
        model="m",
        game_date="2026-09-01",
        status="done",
        ran=1,
    )

    out = capsys.readouterr().out.strip()
    assert "hello" in out
    assert "stage=game" in out
    assert "model=m" in out
    assert "date=2026-09-01" in out
    assert "status=done" in out
    assert "ran=1" in out


def test_configure_json_format(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "json")
    applog.configure_logging(force=True)

    applog.event(
        "nightly done",
        stage="nightly",
        status="failed",
        ran=1,
        skipped=2,
        failed=3,
    )

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["severity"] == "INFO"
    assert payload["message"] == "nightly done"
    assert payload["stage"] == "nightly"
    assert payload["status"] == "failed"
    assert payload["ran"] == 1
    assert payload["skipped"] == 2
    assert payload["failed"] == 3


def test_auto_json_when_data_bucket_set(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "auto")
    monkeypatch.setenv("DATA_BUCKET", "my-bucket")
    applog.configure_logging(force=True)

    applog.event("sync", stage="sync", status="done")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["stage"] == "sync"


def test_event_includes_structured_fields(monkeypatch, capsys):
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.delenv("DATA_BUCKET", raising=False)
    applog.configure_logging(force=True)

    applog.event(
        "skip — entry exists",
        stage="game",
        model="model-a",
        game_date="2026-09-01",
        status="skipped",
    )

    out = capsys.readouterr().out
    assert "skip — entry exists" in out
    assert "stage=game" in out
    assert "model=model-a" in out
    assert "date=2026-09-01" in out
    assert "status=skipped" in out
