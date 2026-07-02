/* LMEX dashboard. Fetches NDJSON data committed by the bench workflow. */
(function () {
  "use strict";

  var LOCAL = location.hostname === "localhost" || location.hostname === "127.0.0.1";
  var RAW = LOCAL ? "../" : "https://raw.githubusercontent.com/saksham10arora-dotcom/lmex/main/";
  var DAYS_TO_LOAD = 14;

  var state = { records: [], latest: null, ticker: null, bucket: 21600, chart: null, series: null };

  function toUnix(ts) { return Math.floor(new Date(ts).getTime() / 1000); }

  function fetchJson(path) {
    return fetch(RAW + path, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(path + " " + r.status);
      return r.json();
    });
  }

  function fetchText(path) {
    return fetch(RAW + path, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(path + " " + r.status);
      return r.text();
    });
  }

  function parseNdjson(text) {
    return text.split("\n").filter(Boolean).map(function (l) { return JSON.parse(l); });
  }

  function emptyState(msg) {
    var el = document.getElementById("empty-state");
    el.hidden = false;
    el.textContent = msg;
    document.getElementById("tape-inner").textContent = msg;
  }

  /* ---------- tape ---------- */

  function renderTape() {
    var inner = document.getElementById("tape-inner");
    inner.textContent = "";
    Object.keys(state.latest.tickers).forEach(function (tk) {
      var t = state.latest.tickers[tk];
      var sym = document.createElement("span");
      sym.className = "sym";
      sym.textContent = tk;
      inner.appendChild(sym);
      var val = document.createElement("span");
      if (!t.last || t.status === "DELISTED") {
        val.textContent = " DELISTED";
        val.className = "";
      } else {
        var txt = " " + t.last.ttft_p99.toFixed(0) + "ms";
        if (t.prev && t.prev.ttft_p99 > 0) {
          var pct = (t.last.ttft_p99 - t.prev.ttft_p99) / t.prev.ttft_p99 * 100;
          txt += " " + (pct >= 0 ? "▲" : "▼") + Math.abs(pct).toFixed(1) + "%";
          val.className = pct >= 0 ? "up" : "down";
        }
        if (t.status === "HALTED") txt += " [HALTED]";
        val.textContent = txt;
      }
      inner.appendChild(val);
    });
  }

  /* ---------- board ---------- */

  function td(text, cls) {
    var el = document.createElement("td");
    el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function renderBoard() {
    var tbody = document.querySelector("#board tbody");
    tbody.textContent = "";
    Object.keys(state.latest.tickers).forEach(function (tk) {
      var t = state.latest.tickers[tk];
      var tr = document.createElement("tr");
      tr.appendChild(td(tk));
      var badge = document.createElement("span");
      badge.className = "badge " + t.status;
      badge.textContent = t.status;
      var tdStatus = document.createElement("td");
      tdStatus.appendChild(badge);
      tr.appendChild(tdStatus);
      if (t.last) {
        tr.appendChild(td(t.last.ttft_p50.toFixed(0) + "ms"));
        tr.appendChild(td(t.last.ttft_p95.toFixed(0) + "ms"));
        tr.appendChild(td(t.last.ttft_p99.toFixed(0) + "ms"));
        tr.appendChild(td(String(t.last.tok_per_sec)));
        tr.appendChild(td((t.last.error_rate * 100).toFixed(0) + "%"));
        if (t.prev && t.prev.ttft_p99 > 0) {
          var pct = (t.last.ttft_p99 - t.prev.ttft_p99) / t.prev.ttft_p99 * 100;
          tr.appendChild(td((pct >= 0 ? "+" : "") + pct.toFixed(1) + "%",
            pct >= 0 ? "delta-up" : "delta-down"));
        } else tr.appendChild(td("n/a"));
      } else {
        for (var i = 0; i < 6; i++) tr.appendChild(td("-"));
      }
      tbody.appendChild(tr);
    });
  }

  /* ---------- composite ---------- */

  function renderComposite() {
    var vals = [];
    Object.keys(state.latest.tickers).forEach(function (tk) {
      var t = state.latest.tickers[tk];
      if (!t.last || t.status === "DELISTED" || t.last.ttft_p99 <= 0) return;
      var mine = state.records.filter(function (r) {
        return r.ticker === tk && r.ttft_p99 > 0;
      });
      if (mine.length < 2) return;
      var mean = mine.reduce(function (s, r) { return s + r.ttft_p99; }, 0) / mine.length;
      vals.push(t.last.ttft_p99 / mean * 100);
    });
    document.getElementById("composite").textContent = vals.length
      ? (vals.reduce(function (s, v) { return s + v; }, 0) / vals.length).toFixed(1)
      : "n/a";
  }

  /* ---------- chart ---------- */

  function candles(ticker, bucketSec) {
    var mine = state.records.filter(function (r) {
      return r.ticker === ticker && r.ttft_p99 > 0;
    }).sort(function (a, b) { return toUnix(a.ts) - toUnix(b.ts); });
    var buckets = {};
    var order = [];
    mine.forEach(function (r) {
      var b = Math.floor(toUnix(r.ts) / bucketSec) * bucketSec;
      if (!buckets[b]) { buckets[b] = []; order.push(b); }
      buckets[b].push(r.ttft_p99);
    });
    return order.map(function (b) {
      var v = buckets[b];
      return { time: b, open: v[0], close: v[v.length - 1],
               high: Math.max.apply(null, v), low: Math.min.apply(null, v) };
    });
  }

  function renderChart() {
    var el = document.getElementById("chart");
    if (!state.chart) {
      state.chart = LightweightCharts.createChart(el, {
        layout: { background: { type: "solid", color: "#12161b" }, textColor: "#6b7683" },
        grid: { vertLines: { color: "#1f262e" }, horzLines: { color: "#1f262e" } },
        timeScale: { timeVisible: true, borderColor: "#1f262e" },
        rightPriceScale: { borderColor: "#1f262e" },
      });
      /* Inverted on purpose: rising latency is a red candle, falling is green. */
      state.series = state.chart.addCandlestickSeries({
        upColor: "#e5484d", wickUpColor: "#e5484d", borderUpColor: "#e5484d",
        downColor: "#30a46c", wickDownColor: "#30a46c", borderDownColor: "#30a46c",
      });
      new ResizeObserver(function () {
        state.chart.applyOptions({ width: el.clientWidth });
        state.chart.timeScale().fitContent();
      }).observe(el);
    }
    var data = candles(state.ticker, state.bucket);
    document.getElementById("empty-state").hidden = data.length > 0;
    state.series.setData(data);
    state.chart.timeScale().fitContent();
  }

  /* ---------- controls ---------- */

  function renderControls() {
    var wrap = document.getElementById("ticker-buttons");
    wrap.textContent = "";
    Object.keys(state.latest.tickers).forEach(function (tk) {
      var b = document.createElement("button");
      b.textContent = tk;
      b.className = tk === state.ticker ? "active" : "";
      b.addEventListener("click", function () {
        state.ticker = tk;
        renderControls();
        renderChart();
      });
      wrap.appendChild(b);
    });
    document.querySelectorAll("#bucket-buttons button").forEach(function (b) {
      b.classList.toggle("active", Number(b.dataset.bucket) === state.bucket);
    });
  }

  document.querySelectorAll("#bucket-buttons button").forEach(function (b) {
    b.addEventListener("click", function () {
      state.bucket = Number(b.dataset.bucket);
      renderControls();
      renderChart();
    });
  });

  /* ---------- report ---------- */

  function renderReport() {
    if (!state.latest.report) return;
    fetchText(state.latest.report).then(function (text) {
      document.getElementById("report").textContent = text;
    }).catch(function () { /* keep default */ });
  }

  /* ---------- boot ---------- */

  fetchJson("data/latest.json").then(function (latest) {
    state.latest = latest;
    return fetchJson("data/manifest.json");
  }).then(function (manifest) {
    var days = manifest.days.slice(0, DAYS_TO_LOAD);
    return Promise.all(days.map(function (d) {
      return fetchText("data/" + d).then(parseNdjson).catch(function () { return []; });
    }));
  }).then(function (chunks) {
    state.records = chunks.flat();
    var tickers = Object.keys(state.latest.tickers);
    if (!tickers.length || !state.records.length) {
      emptyState("market opens at the next hourly candle");
      return;
    }
    state.ticker = tickers.find(function (tk) {
      return state.latest.tickers[tk].status !== "DELISTED";
    }) || tickers[0];
    renderTape();
    renderBoard();
    renderComposite();
    renderControls();
    renderChart();
    renderReport();
  }).catch(function () {
    emptyState("market opens at the next hourly candle");
  });
})();
