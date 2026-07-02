from __future__ import annotations

import math


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = max(1, math.ceil(p / 100 * len(sorted_vals)))
    return sorted_vals[k - 1]


def _stats(vals_ms: list[float]) -> tuple[float, float, float]:
    s = sorted(vals_ms)
    return (round(percentile(s, 50), 1), round(percentile(s, 95), 1),
            round(percentile(s, 99), 1))


def normalize(ticker: str, bench: dict) -> dict:
    meta = bench["meta"]
    results = bench["results"]
    ok = [r for r in results if not r.get("error")]
    n = len(results)
    ttft = _stats([r["ttft_ns"] / 1e6 for r in ok])
    total = _stats([r["total_ns"] / 1e6 for r in ok])
    dur_s = sum(r["total_ns"] for r in ok) / 1e9
    toks = sum(r["completion_tokens"] for r in ok)
    return {
        "ts": meta["timestamp"],
        "ticker": ticker,
        "model": meta["model"],
        "n": n,
        "errors": n - len(ok),
        "error_rate": round((n - len(ok)) / n, 4) if n else 1.0,
        "ttft_p50": ttft[0], "ttft_p95": ttft[1], "ttft_p99": ttft[2],
        "total_p50": total[0], "total_p95": total[1], "total_p99": total[2],
        "tok_per_sec": round(toks / dur_s, 1) if dur_s > 0 else 0.0,
    }


def error_record(ticker: str, model: str, n: int, ts: str) -> dict:
    return {
        "ts": ts, "ticker": ticker, "model": model, "n": n, "errors": n,
        "error_rate": 1.0,
        "ttft_p50": 0.0, "ttft_p95": 0.0, "ttft_p99": 0.0,
        "total_p50": 0.0, "total_p95": 0.0, "total_p99": 0.0,
        "tok_per_sec": 0.0,
    }
