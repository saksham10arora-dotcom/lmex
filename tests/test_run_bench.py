import json
from datetime import datetime, timezone

from scripts.run_bench import run_once

TICKERS = [
    {"ticker": "MOCK", "provider": "mock", "model": "demo", "n": 3,
     "cadence": "hourly"},
    {"ticker": "MISS", "provider": "openai", "model": "x",
     "base_url": "https://x", "env_key": "NO_SUCH_KEY_SET_EVER",
     "n": 3, "cadence": "hourly"},
    {"ticker": "OPRT", "provider": "openai", "model": "y",
     "base_url": "https://y", "env_key": "NO_SUCH_KEY_SET_EVER",
     "n": 3, "cadence": "daily"},
]
NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)


def fake_runner_ok(cmd):
    out = cmd[cmd.index("--json") + 1]
    json_body = {"meta": {"model": "demo", "timestamp": NOW.isoformat()},
                 "results": [{"ttft_ns": 100_000_000, "total_ns": 1_000_000_000,
                              "completion_tokens": 10, "prompt_tokens": 5,
                              "error": None}]}
    with open(out, "w") as f:
        json.dump(json_body, f)
    return 0


def test_run_once_mock_and_delisted(tmp_path):
    recs = run_once(TICKERS, tmp_path / "data", tmp_path / "reports", NOW,
                    runner=fake_runner_ok)
    assert [r["ticker"] for r in recs] == ["MOCK"]
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    assert latest["tickers"]["MOCK"]["status"] == "TRADING"
    assert latest["tickers"]["MISS"]["status"] == "DELISTED"


def test_run_once_cli_failure_writes_error_record(tmp_path):
    recs = run_once(TICKERS[:1], tmp_path / "data", tmp_path / "reports", NOW,
                    runner=lambda cmd: 1)
    assert recs[0]["error_rate"] == 1.0
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    assert latest["tickers"]["MOCK"]["status"] == "HALTED"


def test_force_ignores_cadence(tmp_path):
    recs = run_once([TICKERS[0] | {"cadence": "daily"}], tmp_path / "data",
                    tmp_path / "reports", NOW, force=True,
                    runner=fake_runner_ok)
    assert len(recs) == 1
