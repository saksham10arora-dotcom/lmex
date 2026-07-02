from scripts.normalize import error_record, normalize, percentile


def bench_fixture():
    return {
        "meta": {"model": "demo", "timestamp": "2026-07-02T10:07:00+00:00"},
        "results": [
            {"ttft_ns": 100_000_000, "total_ns": 1_000_000_000,
             "completion_tokens": 50, "prompt_tokens": 10, "error": None},
            {"ttft_ns": 200_000_000, "total_ns": 2_000_000_000,
             "completion_tokens": 50, "prompt_tokens": 10, "error": None},
            {"ttft_ns": 0, "total_ns": 0,
             "completion_tokens": 0, "prompt_tokens": 0, "error": "timeout"},
        ],
    }


def test_percentile_nearest_rank():
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.0
    assert percentile([5.0], 99) == 5.0
    assert percentile([], 50) == 0.0


def test_normalize_basic():
    rec = normalize("GROQ", bench_fixture())
    assert rec["ticker"] == "GROQ" and rec["model"] == "demo"
    assert rec["ts"] == "2026-07-02T10:07:00+00:00"
    assert rec["n"] == 3 and rec["errors"] == 1
    assert rec["error_rate"] == 0.3333
    assert rec["ttft_p50"] == 100.0 and rec["ttft_p99"] == 200.0
    assert rec["total_p99"] == 2000.0
    assert rec["tok_per_sec"] == 33.3  # 100 tokens over 3.0s


def test_normalize_all_errors():
    bench = bench_fixture()
    for r in bench["results"]:
        r["error"] = "boom"
    rec = normalize("GROQ", bench)
    assert rec["error_rate"] == 1.0 and rec["ttft_p99"] == 0.0


def test_error_record():
    rec = error_record("OPRT", "some/model", 10, "2026-07-02T00:07:00+00:00")
    assert rec["error_rate"] == 1.0 and rec["n"] == 10 and rec["errors"] == 10
