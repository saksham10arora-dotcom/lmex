# LMEX

**The LLM Latency Exchange.** Free-tier LLM APIs trade as tickers. The price is
TTFT p99 in milliseconds. Down is good.

Every hour, a GitHub Actions cron benchmarks each provider with
[llm-latency-bench](https://pypi.org/project/llm-latency-bench/) and commits the
results to this repo. The dashboard turns that history into candlestick charts
with the colors inverted on purpose: a green candle means latency fell. There is
a composite index, trading halts when a provider starts erroring, and a market
open report published daily at 00:00 UTC.

**Live board: <https://saksham10arora-dotcom.github.io/lmex/>**

## How it works

```
GitHub Actions cron (hourly at :07)
        |
        v
llm-latency-bench CLI  ->  scripts/run_bench.py  ->  data/YYYY/MM/DD.ndjson
                                                     data/latest.json
                                                     reports/YYYY-MM-DD.md
        |
        v
git commit [skip ci]  ->  GitHub Pages dashboard reads the raw files
```

No servers. The exchange is a cron job, the tape is a git log, and the
exchange floor is a static page.

## The tickers

| Ticker | Provider | Model | Trades |
|---|---|---|---|
| GROQ | Groq | llama-3.3-70b-versatile | hourly |
| GMNI | Google Gemini | gemini-2.5-flash | twice daily, free tier is 20 req/day |
| CBRS | Cerebras | gpt-oss-120b | hourly, cross-listed with OSS |
| L8B | Groq | llama-3.1-8b-instant | hourly |
| OSS | Groq | gpt-oss-120b | hourly |
| QWEN | Groq | qwen3-32b | every 2 hours |
| OPRT | OpenRouter | gemma-4-31b (free) | every 4 hours, the illiquid one |

Statuses: TRADING, HALTED (error rate above 50% on the last run), DELISTED
(no API key configured or no data for 48 hours).

Honesty note on sample size: each hourly tick is a small run (6 to 10
requests), so an hourly "p99" is really that hour's worst request. The
daily candles aggregate 24 hourly samples, which is where the tail starts
meaning something. Small n keeps the whole exchange inside free tiers; the
tradeoff is disclosed here instead of hidden.

## Why p99 and not the mean

The mean blends fast and slow regimes into one number that describes neither.
Tail latency is what your worst user actually feels, and free tiers have wild
tails: rate limiters kick in, queues build, and the p50 stays innocent while
the p99 triples. That story is easiest to see on a chart, so this repo draws
the chart. The measurement rationale lives in the
[llm-bench README](https://github.com/saksham10arora-dotcom/llm-bench).

## Run it yourself

```bash
git clone https://github.com/saksham10arora-dotcom/lmex
cd lmex
pip install -r requirements-dev.txt llm-latency-bench
python -m pytest -q

# one bench pass with the no-key mock provider
python scripts/run_bench.py --tickers tests/fixtures/mock_tickers.json --force

# dashboard against local data
python -m http.server 8000   # then open http://localhost:8000/docs/
```

To fork the exchange, set repo secrets for the tickers you want listed:
`GROQ_API_KEY`, `GEMINI_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`.
Missing keys just delist the ticker. Edit `tickers.json` to list your own.

## License

MIT.
