from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def _day_path(data_dir: Path, ts: str) -> Path:
    d = datetime.fromisoformat(ts)
    return data_dir / f"{d:%Y/%m/%d}.ndjson"


def append_records(data_dir: Path, records: list[dict]) -> None:
    for r in records:
        p = _day_path(data_dir, r["ts"])
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(r) + "\n")


def write_manifest(data_dir: Path) -> list[str]:
    days = sorted(
        (str(p.relative_to(data_dir)) for p in data_dir.glob("*/*/*.ndjson")),
        reverse=True,
    )
    (data_dir / "manifest.json").write_text(json.dumps({"days": days}, indent=2))
    return days


def load_recent(data_dir: Path, n_days: int) -> list[dict]:
    days = json.loads((data_dir / "manifest.json").read_text())["days"][:n_days]
    out: list[dict] = []
    for day in days:
        for line in (data_dir / day).read_text().splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def _newest_report(data_dir: Path) -> str | None:
    reports_dir = data_dir.parent / "reports"
    if not reports_dir.exists():
        return None
    reports = sorted(reports_dir.glob("*.md"), reverse=True)
    return f"reports/{reports[0].name}" if reports else None


def build_latest(data_dir: Path, tickers: list[dict], delisted: set[str],
                 now: datetime) -> dict:
    records = load_recent(data_dir, 4)
    latest: dict = {"updated": now.isoformat(),
                    "report": _newest_report(data_dir), "tickers": {}}
    for t in tickers:
        tk = t["ticker"]
        mine = sorted((r for r in records if r["ticker"] == tk),
                      key=lambda r: r["ts"])
        last = mine[-1] if mine else None
        prev = None
        if last:
            cutoff = datetime.fromisoformat(last["ts"]) - timedelta(hours=22)
            older = [r for r in mine if datetime.fromisoformat(r["ts"]) <= cutoff]
            prev = older[-1] if older else None
        if tk in delisted or last is None or \
                datetime.fromisoformat(last["ts"]) < now - timedelta(hours=48):
            status = "DELISTED"
        elif last["error_rate"] > 0.5:
            status = "HALTED"
        else:
            status = "TRADING"
        latest["tickers"][tk] = {"last": last, "prev": prev, "status": status}
    (data_dir / "latest.json").write_text(json.dumps(latest, indent=2))
    return latest
