from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


def _day_records(data_dir: Path, d: date) -> list[dict]:
    p = data_dir / f"{d:%Y/%m/%d}.ndjson"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _closes(records: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in sorted(records, key=lambda r: r["ts"]):
        out[r["ticker"]] = r
    return out


def generate(data_dir: Path, reports_dir: Path, day: date) -> Path | None:
    today = _day_records(data_dir, day)
    if not today:
        return None
    closes = _closes(today)
    prior = _closes(_day_records(data_dir, day - timedelta(days=1)))

    lines = [f"# LMEX market open report, {day.isoformat()}", "",
             "Price is TTFT p99 in ms. Down is good.", "",
             "| Ticker | Close | Prior | Move |", "|---|---|---|---|"]
    moves: list[tuple[str, float]] = []
    for tk, r in sorted(closes.items()):
        if r["ttft_p99"] <= 0:
            lines.append(f"| {tk} | halted | n/a | n/a |")
            continue
        p = prior.get(tk)
        if p and p["ttft_p99"] > 0:
            pct = (r["ttft_p99"] - p["ttft_p99"]) / p["ttft_p99"] * 100
            moves.append((tk, pct))
            move = f"{pct:+.1f}%"
            prior_s = f"{p['ttft_p99']:.0f}ms"
        else:
            move, prior_s = "new", "n/a"
        lines.append(f"| {tk} | {r['ttft_p99']:.0f}ms | {prior_s} | {move} |")

    active = {tk: r for tk, r in closes.items() if r["ttft_p99"] > 0}
    if active:
        fast = min(active, key=lambda t: active[t]["ttft_p99"])
        slow = max(active, key=lambda t: active[t]["ttft_p99"])
        lines += ["", f"Fastest tape: {fast} at {active[fast]['ttft_p99']:.0f}ms p99. "
                      f"Slowest: {slow} at {active[slow]['ttft_p99']:.0f}ms."]
    if moves:
        big = max(moves, key=lambda m: abs(m[1]))
        lines.append(f"Biggest mover: {big[0]} ({big[1]:+.1f}%).")
    halted = sorted({r["ticker"] for r in today if r["error_rate"] > 0.5})
    if halted:
        lines.append(f"Trading halted at some point: {', '.join(halted)}.")
    spreads = {tk: r["ttft_p99"] / r["ttft_p50"]
               for tk, r in active.items() if r["ttft_p50"] > 0}
    if spreads:
        wide = max(spreads, key=spreads.get)
        lines.append(f"Widest p50 to p99 spread: {wide} at {spreads[wide]:.1f}x. "
                     "That is the tail your worst user feels.")

    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"{day.isoformat()}.md"
    out.write_text("\n".join(lines) + "\n")
    return out
