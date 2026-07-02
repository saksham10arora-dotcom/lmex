from datetime import date

from scripts.report import generate
from scripts.store import append_records


def rec(ts, ticker, p99, p50=100.0, err=0.0):
    return {"ts": ts, "ticker": ticker, "model": "m", "n": 8, "errors": 0,
            "error_rate": err, "ttft_p50": p50, "ttft_p95": p99 - 10,
            "ttft_p99": p99, "total_p50": 500.0, "total_p95": 700.0,
            "total_p99": 900.0, "tok_per_sec": 100.0}


def test_generate_report(tmp_path):
    data, reports = tmp_path / "data", tmp_path / "reports"
    append_records(data, [
        rec("2026-07-01T10:07:00+00:00", "GROQ", 300.0),
        rec("2026-07-02T10:07:00+00:00", "GROQ", 150.0),
        rec("2026-07-02T23:07:00+00:00", "GROQ", 200.0),
        rec("2026-07-02T10:07:00+00:00", "GMNI", 400.0, err=0.8),
    ])
    out = generate(data, reports, date(2026, 7, 2))
    text = out.read_text()
    assert out.name == "2026-07-02.md"
    assert "GROQ" in text and "-33.3%" in text
    assert "GMNI" in text and "halted" in text.lower()
    assert "—" not in text  # no em-dashes, hard rule


def test_generate_missing_day_returns_none(tmp_path):
    assert generate(tmp_path / "data", tmp_path / "reports",
                    date(2026, 7, 2)) is None
