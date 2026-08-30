"""Build the Kaggle release from the repo's NDJSON tape.

Kaggle consumers want one flat table, not 59 date-partitioned NDJSON files.
This flattens the tape into a single CSV, joins the ticker -> provider mapping
that otherwise lives in tickers.json, and writes the dataset-metadata.json that
carries the data card and per-column descriptions.

    python scripts/build_kaggle.py

Outputs into kaggle/:
    lmex_latency.csv       one row per benchmark run
    dataset-metadata.json  card + column descriptions, pushed by the Kaggle CLI
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "kaggle"
SLUG = "c0sbyy/llm-inference-latency-benchmark"

# Emitted in this order. Derived columns come last so the raw tape stays
# recognisable to anyone who has read the NDJSON.
RAW_FIELDS = [
    "ts", "ticker", "model", "n", "errors", "error_rate",
    "ttft_p50", "ttft_p95", "ttft_p99",
    "total_p50", "total_p95", "total_p99",
    "tok_per_sec",
]
DERIVED_FIELDS = ["provider", "date", "hour_utc", "ttft_tail_ratio"]

# When every request in a run failed, the collector writes 0.0 into these
# columns. That is "no measurement", not "zero latency", and a reader doing
# df.ttft_p99.mean() would silently understate the tail by ~28%. Emit empty
# instead so pandas reads NaN and skips them. Same principle the collector
# already applies within a run: errors never pollute a percentile.
MEASUREMENT_FIELDS = [
    "ttft_p50", "ttft_p95", "ttft_p99",
    "total_p50", "total_p95", "total_p99",
    "tok_per_sec",
]

# Every column gets a description -- Kaggle scores this, and it is the
# difference between a table someone can use and one they have to guess at.
COLUMN_DOCS = {
    "ts": "UTC timestamp of the benchmark run, ISO 8601 with offset.",
    "ticker": "Short symbol for the provider/model pair (GROQ, L8B, OSS, QWEN, CBRS, GMNI, OPRT).",
    "model": "Exact model identifier passed to the provider's API.",
    "n": "Number of requests in this run. Small by design to stay inside free tiers; see the sample-size note.",
    "errors": "Count of failed requests in the run. Excluded from all latency percentiles.",
    "error_rate": "errors / n, from 0.0 to 1.0. A run above 0.5 marks the ticker HALTED on the live board. When 1.0, every latency column in the row is null.",
    "ttft_p50": "Median time to first token, milliseconds. Dispatch to first content chunk, including queueing and prefill. Null when the run had no successful request.",
    "ttft_p95": "95th percentile time to first token, milliseconds.",
    "ttft_p99": "99th percentile time to first token, milliseconds. The headline metric: what the worst request in the run felt.",
    "total_p50": "Median end-to-end latency, milliseconds. Dispatch to last content chunk.",
    "total_p95": "95th percentile end-to-end latency, milliseconds.",
    "total_p99": "99th percentile end-to-end latency, milliseconds.",
    "tok_per_sec": "Decode throughput: (completion_tokens - 1) / (total - TTFT). Excludes prefill so it measures generation speed only.",
    "provider": "Inference provider serving the model (groq, cerebras, google, openrouter). Derived from the ticker.",
    "date": "UTC calendar date of the run (YYYY-MM-DD). Convenience column for daily grouping.",
    "hour_utc": "UTC hour of the run, 0-23. Convenience column for time-of-day analysis.",
    "ttft_tail_ratio": "ttft_p99 / ttft_p50. How much worse the tail is than the typical request. 1.0 means flat; higher means a heavy tail.",
}

# tickers.json stores base_url, not a provider name. Map host -> provider so
# consumers can group by provider without doing this join themselves.
HOST_TO_PROVIDER = {
    "api.groq.com": "groq",
    "api.cerebras.ai": "cerebras",
    "generativelanguage.googleapis.com": "google",
    "openrouter.ai": "openrouter",
}


def ticker_providers() -> dict[str, str]:
    tickers = json.loads((ROOT / "tickers.json").read_text())
    out = {}
    for t in tickers:
        host = t["base_url"].split("/")[2]
        out[t["ticker"]] = HOST_TO_PROVIDER.get(host, "unknown")
    return out


def read_rows() -> list[dict]:
    rows = []
    for path in sorted(DATA.glob("*/*/*.ndjson")):
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["ts"])
    return rows


def enrich(row: dict, providers: dict[str, str]) -> dict:
    ts = datetime.fromisoformat(row["ts"])
    p50, p99 = row["ttft_p50"], row["ttft_p99"]
    out = {k: row.get(k) for k in RAW_FIELDS}

    # A run with no successful request has no latency to report. n, errors and
    # error_rate stay populated -- the failure itself is a real observation.
    if row["error_rate"] >= 1.0:
        for field in MEASUREMENT_FIELDS:
            out[field] = ""

    out["provider"] = providers.get(row["ticker"], "unknown")
    out["date"] = ts.date().isoformat()
    out["hour_utc"] = ts.hour
    out["ttft_tail_ratio"] = round(p99 / p50, 3) if p50 else ""
    return out


def build_description(rows: list[dict]) -> str:
    dates = sorted({r["date"] for r in rows})
    tickers = sorted({r["ticker"] for r in rows})

    # Quantify the null convention from the data itself, so the card cannot
    # drift out of sync with what actually shipped.
    measured = [r["ttft_p99"] for r in rows if r["ttft_p99"] != ""]
    n_failed = len(rows) - len(measured)
    pct_failed = round(100 * n_failed / len(rows), 1)
    mean_without = sum(measured) / len(measured)
    mean_with = sum(measured) / len(rows)  # as if nulls were stored as 0.0
    understate = round(100 * (1 - mean_with / mean_without))
    return f"""# Hourly LLM Inference Latency Benchmark

{len(rows):,} hourly latency measurements across {len(tickers)} LLM inference endpoints, \
collected continuously from {dates[0]} to {dates[-1]}. Every row is one benchmark \
run reporting p50/p95/p99 for time-to-first-token and end-to-end latency, plus \
decode throughput and error rate.

Most published LLM latency numbers are means. A mean blends fast and slow regimes \
into one number that describes neither, and free-tier endpoints have violent tails: \
rate limiters engage, queues build, and the median stays innocent while the p99 \
triples. This dataset reports percentiles so the tail is visible.

## Files

- `lmex_latency.csv` -- one row per benchmark run, {len(RAW_FIELDS) + len(DERIVED_FIELDS)} columns, ready for `pd.read_csv`.

## Quickstart

```python
import pandas as pd

df = pd.read_csv("lmex_latency.csv", parse_dates=["ts"])

# Which endpoint has the worst tail relative to its typical request?
print(df.groupby("ticker")["ttft_tail_ratio"].median().sort_values(ascending=False))

# Does latency vary by time of day?
print(df.groupby("hour_utc")["ttft_p99"].median())
```

## Missing values are deliberate

Free-tier endpoints fail often: **{pct_failed}% of runs had every request error out**, \
usually a rate-limit or quota rejection. Those rows carry null latency columns \
rather than zeros, because a failed run has no latency to report. `n`, `errors` \
and `error_rate` stay populated, since the failure itself is a real observation \
worth studying.

This matters for your analysis. If these had been stored as `0.0`, a plain \
`df["ttft_p99"].mean()` would return {mean_with:.0f} ms instead of the correct \
{mean_without:.0f} ms -- understating the tail by {understate}%. pandas skips \
nulls automatically, so the default behaviour is now the correct one. To study \
availability instead of latency, use `error_rate`, which is never null.

## How it was collected

An hourly GitHub Actions cron benchmarks each endpoint with \
[llm-latency-bench](https://pypi.org/project/llm-latency-bench/) \
(`pip install llm-latency-bench`) and appends the result to a git-tracked NDJSON \
tape. There is no server: the collector is a cron job and the raw history is the \
git log. Source and collection code: \
[github.com/saksham10arora-dotcom/lmex](https://github.com/saksham10arora-dotcom/lmex)

Measurement decisions, documented rather than assumed:

- **Percentiles are nearest-rank** on the raw samples. No interpolation, no smoothing.
- **TTFT is dispatch to first content chunk**, deliberately including connection setup, queueing, and prefill, because that is what a user waits through.
- **Total latency ends at the last content chunk**, not at trailing usage frames or connection teardown.
- **Throughput is decode rate only**, `(tokens - 1) / (total - TTFT)`. Including prefill would mislabel two phases as one.
- **Errors are counted and excluded from percentiles.** A failed request has no valid latency.
- **Warmup requests run to completion before measurement begins**, so connection setup never leaks into the numbers.
- All timing uses a monotonic clock.

## Sample size: read this before quoting a p99

Each run is small ({rows[0]['n']}-10 requests) to stay inside free-tier quotas. \
An hourly "p99" is therefore that hour's slowest request, not a stable tail \
estimate. Aggregate across hours or days before drawing conclusions about tail \
behavior -- grouping by `date` or `ticker` puts hundreds of samples behind each \
number. This limitation is disclosed here rather than hidden; the free-tier \
constraint is what makes continuous multi-month collection possible at all.

## Endpoints covered

| Ticker | Provider | Model |
|---|---|---|
| GROQ | Groq | llama-3.3-70b-versatile |
| L8B | Groq | llama-3.1-8b-instant |
| OSS | Groq | openai/gpt-oss-120b |
| QWEN | Groq | qwen/qwen3-32b |
| CBRS | Cerebras | gpt-oss-120b |
| GMNI | Google | gemini-2.5-flash |
| OPRT | OpenRouter | google/gemma-4-31b-it (free) |

Cadence varies by endpoint because free-tier quotas differ: hourly for most, \
every 2h for QWEN, every 4h for OPRT, twice daily for GMNI (20 requests/day cap). \
Row counts per ticker differ accordingly.

## Suggested uses

- Compare tail latency across inference providers on identical workloads
- Study time-of-day and day-of-week effects on free-tier serving
- Model latency distributions where the mean is known to mislead
- Detect regime changes when a provider alters its serving stack

## License

MIT. Attribution appreciated but not required.
"""


def main() -> None:
    providers = ticker_providers()
    rows = read_rows()
    if not rows:
        raise SystemExit("no NDJSON records found under data/")
    enriched = [enrich(r, providers) for r in rows]

    OUT.mkdir(exist_ok=True)
    csv_path = OUT / "lmex_latency.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RAW_FIELDS + DERIVED_FIELDS)
        w.writeheader()
        w.writerows(enriched)

    metadata = {
        "title": "Hourly LLM Inference Latency Benchmark",
        "id": SLUG,
        "subtitle": (
            f"{len(rows):,} hourly p50/p95/p99 latency measurements across "
            f"{len({r['ticker'] for r in rows})} LLM inference endpoints"
        ),
        "description": build_description(enriched),
        "isPrivate": False,
        "licenses": [{"name": "MIT"}],
        "keywords": [
            "artificial-intelligence",
            "nlp",
            "computer-science",
            "time series analysis",
            "internet",
        ],
        "resources": [
            {
                "path": "lmex_latency.csv",
                "description": (
                    "One row per benchmark run. Latency columns are milliseconds; "
                    "percentiles are nearest-rank over that run's requests."
                ),
                "schema": {
                    "fields": [
                        {"name": name, "description": COLUMN_DOCS[name]}
                        for name in RAW_FIELDS + DERIVED_FIELDS
                    ]
                },
            }
        ],
    }
    (OUT / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    dates = sorted({r["date"] for r in enriched})
    print(f"wrote {csv_path.relative_to(ROOT)}  ({len(enriched):,} rows, {dates[0]} to {dates[-1]})")
    print(f"wrote {(OUT / 'dataset-metadata.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
