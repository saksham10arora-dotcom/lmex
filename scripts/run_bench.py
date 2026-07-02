from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.cadence import is_due
from scripts.normalize import error_record, normalize
from scripts.report import generate
from scripts.store import append_records, build_latest, write_manifest

PROMPT = "Explain p99 latency in one sentence."


def _run_cli(cmd: list[str]) -> int:
    return subprocess.run(cmd, timeout=600).returncode


def _bench_cmd(t: dict, key: str | None, out: str) -> list[str]:
    cmd = ["llm-bench", "--provider", t["provider"], "--model", t["model"],
           "--prompt", PROMPT, "-n", str(t["n"]), "--warmup", "1",
           "--max-tokens", str(t.get("max_tokens", 64)),
           "--timeout", "30", "--json", out]
    if t.get("base_url"):
        cmd += ["--base-url", t["base_url"]]
    if key:
        cmd += ["--api-key", key]
    return cmd


def run_once(tickers: list[dict], data_dir: Path, reports_dir: Path,
             now: datetime, force: bool = False, runner=_run_cli) -> list[dict]:
    delisted: set[str] = set()
    records: list[dict] = []
    for t in tickers:
        key = os.environ.get(t["env_key"]) if t.get("env_key") else None
        if t.get("env_key") and not key:
            delisted.add(t["ticker"])
            continue
        if not force and not is_due(t["cadence"], now.hour):
            continue
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out = f.name
        try:
            code = runner(_bench_cmd(t, key, out))
            bench = json.loads(Path(out).read_text()) if code == 0 else None
        except Exception:
            bench = None
        finally:
            Path(out).unlink(missing_ok=True)
        if bench and bench.get("results"):
            records.append(normalize(t["ticker"], bench))
        else:
            records.append(error_record(t["ticker"], t["model"], t["n"],
                                        now.isoformat()))
    if records:
        append_records(data_dir, records)
    data_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(data_dir)
    if now.hour == 0:
        generate(data_dir, reports_dir, (now - timedelta(days=1)).date())
    build_latest(data_dir, tickers, delisted, now)
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--tickers", default=root / "tickers.json", type=Path)
    ap.add_argument("--data-dir", default=root / "data", type=Path)
    ap.add_argument("--reports-dir", default=root / "reports", type=Path)
    ap.add_argument("--hour", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    if args.hour is not None:
        now = now.replace(hour=args.hour)
    tickers = json.loads(Path(args.tickers).read_text())
    recs = run_once(tickers, args.data_dir, args.reports_dir, now,
                    force=args.force)
    print(f"benched {len(recs)} tickers: {[r['ticker'] for r in recs]}")


if __name__ == "__main__":
    main()
