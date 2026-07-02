import json
from datetime import datetime, timezone

from scripts.store import append_records, build_latest, load_recent, write_manifest


def rec(ts, ticker="GROQ", p99=200.0, err=0.0):
    return {"ts": ts, "ticker": ticker, "model": "m", "n": 8, "errors": 0,
            "error_rate": err, "ttft_p50": 100.0, "ttft_p95": 150.0,
            "ttft_p99": p99, "total_p50": 500.0, "total_p95": 700.0,
            "total_p99": 900.0, "tok_per_sec": 100.0}


NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)


def test_append_creates_day_files(tmp_path):
    append_records(tmp_path, [rec("2026-07-02T10:07:00+00:00"),
                              rec("2026-07-01T23:07:00+00:00")])
    assert (tmp_path / "2026/07/02.ndjson").exists()
    assert (tmp_path / "2026/07/01.ndjson").exists()


def test_manifest_newest_first(tmp_path):
    append_records(tmp_path, [rec("2026-07-01T10:07:00+00:00"),
                              rec("2026-07-02T10:07:00+00:00")])
    days = write_manifest(tmp_path)
    assert days == ["2026/07/02.ndjson", "2026/07/01.ndjson"]
    assert json.loads((tmp_path / "manifest.json").read_text())["days"] == days


def test_load_recent_limits_days(tmp_path):
    append_records(tmp_path, [rec("2026-06-30T10:07:00+00:00"),
                              rec("2026-07-01T10:07:00+00:00"),
                              rec("2026-07-02T10:07:00+00:00")])
    write_manifest(tmp_path)
    assert len(load_recent(tmp_path, 2)) == 2


def test_build_latest_statuses(tmp_path):
    tickers = [{"ticker": "GROQ"}, {"ticker": "GMNI"}, {"ticker": "OPRT"}]
    append_records(tmp_path, [
        rec("2026-07-01T11:07:00+00:00", "GROQ", p99=300.0),
        rec("2026-07-02T11:07:00+00:00", "GROQ", p99=250.0),
        rec("2026-07-02T11:07:00+00:00", "GMNI", err=0.75),
    ])
    write_manifest(tmp_path)
    latest = build_latest(tmp_path, tickers, {"OPRT"}, NOW)
    assert latest["tickers"]["GROQ"]["status"] == "TRADING"
    assert latest["tickers"]["GROQ"]["prev"]["ttft_p99"] == 300.0
    assert latest["tickers"]["GMNI"]["status"] == "HALTED"
    assert latest["tickers"]["OPRT"]["status"] == "DELISTED"
    assert (tmp_path / "latest.json").exists()


def test_build_latest_stale_is_delisted(tmp_path):
    append_records(tmp_path, [rec("2026-06-28T11:07:00+00:00")])
    write_manifest(tmp_path)
    latest = build_latest(tmp_path, [{"ticker": "GROQ"}], set(), NOW)
    assert latest["tickers"]["GROQ"]["status"] == "DELISTED"
