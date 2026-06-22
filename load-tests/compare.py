#!/usr/bin/env python3
"""Aggregate per-language Artillery JSON (results/*.json) into a single
self-contained compare-report.html with Chart.js charts.

Stdlib only. This measures API/HTTP handling (the load test), the counterpart
to benchmarks/compare.html which measures in-process algorithm + concurrency.

Reads Artillery v2 report shape: everything lives under `aggregate` as
`counters` (request/response/error tallies), `rates` (request rate) and
`summaries` (latency histograms, overall and per-endpoint via the
metrics-by-endpoint plugin).
"""

import json
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"
OUTPUT = SCRIPT_DIR / "compare-report.html"

# Preferred display order; anything else is appended alphabetically.
ORDER = ["python", "java", "go", "cpp", "nest"]
COLORS = {
    "python": "#3776ab",
    "java": "#e76f00",
    "go": "#00add8",
    "cpp": "#9b4f96",
    "nest": "#e0234e",
}
ENDPOINTS = ["/health", "/search/file", "/search/many"]


def load_results() -> dict[str, dict]:
    results = {}
    for env in ORDER:
        path = RESULTS_DIR / f"{env}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                results[env] = json.load(f)
    # Append any extra result files not in ORDER.
    for path in sorted(RESULTS_DIR.glob("*.json")):
        env = path.stem
        if env not in results:
            with open(path, encoding="utf-8") as f:
                results[env] = json.load(f)
    return results


def endpoint_latency(agg: dict, endpoint: str) -> dict | None:
    """Per-endpoint latency histogram from the metrics-by-endpoint plugin."""
    key = f"plugins.metrics-by-endpoint.response_time.{endpoint}"
    s = agg.get("summaries", {}).get(key)
    if not s:
        return None
    return {
        "count": s.get("count"),
        "p50": s.get("median"),
        "p90": s.get("p90"),
        "p95": s.get("p95"),
        "p99": s.get("p99"),
        "max": s.get("max"),
        "mean": s.get("mean"),
    }


def overall_stats(agg: dict) -> dict:
    counters = agg.get("counters", {})
    rates = agg.get("rates", {})
    success = sum(v for k, v in counters.items() if k.startswith("http.codes.2"))
    errors = {
        k[len("errors."):]: v for k, v in counters.items() if k.startswith("errors.")
    }
    return {
        "requests": counters.get("http.requests", 0),
        "responses": counters.get("http.responses", 0),
        "success_2xx": success,
        "failed": counters.get("vusers.failed", 0),
        "errors": errors,
        "rps": rates.get("http.request_rate", 0),
    }


def main() -> None:
    results = load_results()
    if not results:
        raise SystemExit(f"no result files in {RESULTS_DIR} — run run-all.sh first")

    langs = sorted(
        results.keys(),
        key=lambda l: (ORDER.index(l) if l in ORDER else len(ORDER), l),
    )
    languages = [{"id": l, "color": COLORS.get(l, "#888")} for l in langs]

    by_lang = {}
    for l in langs:
        agg = results[l].get("aggregate", {})
        by_lang[l] = {
            "overall": overall_stats(agg),
            "endpoints": {ep: endpoint_latency(agg, ep) for ep in ENDPOINTS},
        }

    payload = {
        "generated": str(date.today()),
        "languages": languages,
        "endpoints": ENDPOINTS,
        "byLang": by_lang,
    }

    html = HTML_TEMPLATE.replace("/*DATA*/", json.dumps(payload))
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(langs)} languages)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Comparative load test report — API/HTTP</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; color: #1c1c1c; padding: 0 1rem; }
  h1 { border-bottom: 2px solid #ddd; padding-bottom: .4rem; }
  .controls { margin: 1rem 0; display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; }
  .controls label { font-weight: 600; }
  .note { background: #f6f8fa; border-left: 4px solid #c0c7d0; padding: .8rem 1rem; font-size: .9rem; line-height: 1.5; }
  .chart-box { margin: 1.5rem 0 2.5rem; }
  table { border-collapse: collapse; width: 100%; font-size: .82rem; margin-bottom: 2rem; }
  th, td { border: 1px solid #ddd; padding: 5px 8px; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #f4f4f4; position: sticky; top: 0; }
  caption { text-align: left; font-weight: 600; margin-bottom: .4rem; }
  code { background: #eef; padding: 0 .25rem; border-radius: 3px; }
  .fail { color: #c0392b; font-weight: 600; }
</style>
</head>
<body>
<h1>Comparative load test report</h1>
<p><em>API/HTTP (Artillery) · generated <span id="gen"></span> · lower latency / higher throughput is better</em></p>

<div class="note">
  This measures <strong>API/HTTP handling</strong> under concurrent load — request
  routing, serialization and the server's concurrency model end-to-end — not the
  raw search algorithm (that is what <code>benchmarks/compare.html</code> covers
  in-process). Latencies are wall-clock per request; throughput is the sustained
  request rate. All implementations run the same <code>artillery.yml</code> against
  the three endpoints; only the target port changes per language.
</div>

<div class="controls">
  <span><label for="metric">Latency metric:</label> <select id="metric"></select></span>
  <span><label><input type="checkbox" id="log"> log scale</label></span>
</div>

<div class="chart-box"><h3>Latency by endpoint</h3><canvas id="latencyChart" height="120"></canvas></div>

<h2>Throughput</h2>
<div class="note">
  Sustained request rate (req/sec) achieved during the run, bounded by the
  container's CPUs. Higher is better.
</div>
<div class="chart-box"><canvas id="tputChart" height="90"></canvas></div>

<div id="tables"></div>

<script>
const DATA = /*DATA*/;
document.getElementById('gen').textContent = DATA.generated;

const METRICS = [
  { id: 'p50', label: 'p50 (median)' },
  { id: 'p90', label: 'p90' },
  { id: 'p95', label: 'p95' },
  { id: 'p99', label: 'p99' },
  { id: 'mean', label: 'mean' },
  { id: 'max', label: 'max' },
];
const metricSel = document.getElementById('metric');
for (const m of METRICS) {
  const o = document.createElement('option');
  o.value = m.id; o.textContent = m.label; metricSel.appendChild(o);
}
metricSel.value = 'p95';

function latency(langId, endpoint, metric) {
  const ep = (DATA.byLang[langId] || {}).endpoints[endpoint];
  return ep ? ep[metric] : null;
}

function datasets(metric) {
  return DATA.languages.map(l => ({
    label: l.id,
    data: DATA.endpoints.map(ep => latency(l.id, ep, metric)),
    backgroundColor: l.color,
  }));
}

let latencyChart;
function render() {
  const metric = metricSel.value;
  const log = document.getElementById('log').checked;
  if (latencyChart) latencyChart.destroy();
  latencyChart = new Chart(document.getElementById('latencyChart'), {
    type: 'bar',
    data: { labels: DATA.endpoints, datasets: datasets(metric) },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y == null ? 'n/a' : ctx.parsed.y.toFixed(1)} ms` } },
      },
      scales: { y: { type: log ? 'logarithmic' : 'linear', title: { display: true, text: 'ms (' + metric + ')' } } },
    },
  });
}
metricSel.addEventListener('change', render);
document.getElementById('log').addEventListener('change', render);
render();

// --- throughput chart ---
new Chart(document.getElementById('tputChart'), {
  type: 'bar',
  data: {
    labels: DATA.languages.map(l => l.id),
    datasets: [{
      label: 'req/sec',
      data: DATA.languages.map(l => DATA.byLang[l.id].overall.rps),
      backgroundColor: DATA.languages.map(l => l.color),
    }],
  },
  options: {
    indexAxis: 'y',
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ctx.parsed.x.toFixed(1) + ' req/sec' } },
    },
    scales: { x: { title: { display: true, text: 'req/sec (higher is better)' } } },
  },
});

// --- tables ---
const tables = document.getElementById('tables');
function fmt(v, d) { return v == null ? '' : v.toFixed(d); }

// Overall table: metric rows x language columns.
{
  const t = document.createElement('table');
  let head = '<caption>Overall</caption><tr><th>Metric</th>';
  for (const l of DATA.languages) head += '<th>' + l.id + '</th>';
  head += '</tr>';
  const rows = [
    ['Total requests', l => l.overall.requests],
    ['2xx responses', l => l.overall.success_2xx],
    ['Failures', l => l.overall.failed],
    ['Req/sec', l => l.overall.rps.toFixed(1)],
  ];
  let body = '';
  for (const [label, fn] of rows) {
    body += '<tr><td>' + label + '</td>';
    for (const l of DATA.languages) {
      const v = fn(DATA.byLang[l.id]);
      const cls = (label === 'Failures' && v > 0) ? ' class="fail"' : '';
      body += '<td' + cls + '>' + v + '</td>';
    }
    body += '</tr>';
  }
  t.innerHTML = head + body;
  tables.appendChild(t);
}

// One latency table per endpoint: language rows x percentile columns.
for (const ep of DATA.endpoints) {
  const t = document.createElement('table');
  let head = '<caption><code>' + ep + '</code> latency (ms)</caption>' +
    '<tr><th>Language</th><th>count</th><th>p50</th><th>p90</th><th>p95</th><th>p99</th><th>mean</th><th>max</th></tr>';
  let body = '';
  for (const l of DATA.languages) {
    const e = DATA.byLang[l.id].endpoints[ep];
    if (!e) continue;
    body += '<tr><td>' + l.id + '</td><td>' + (e.count == null ? '' : e.count) + '</td><td>' +
      fmt(e.p50, 1) + '</td><td>' + fmt(e.p90, 1) + '</td><td>' + fmt(e.p95, 1) + '</td><td>' +
      fmt(e.p99, 1) + '</td><td>' + fmt(e.mean, 1) + '</td><td>' + fmt(e.max, 1) + '</td></tr>';
  }
  t.innerHTML = head + body;
  tables.appendChild(t);
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
