#!/usr/bin/env python3
"""Aggregate Artillery JSON into compare-report.html and summary.md.

Input: results/<profile>/<service>.r<round>.json, written by run-all.sh — one
file per SEARCH_MODE profile, service and round. Languages are only compared
within one profile, so every chart shows the same mode for all of them. With
several rounds each value is the median across rounds, with the min–max range.

Stdlib only. This measures API/HTTP handling (the load test), the counterpart to
benchmarks/compare.html which measures the search in-process.

Reads the Artillery v2 report shape: everything lives under `aggregate` as
`counters` (request/response/error tallies), `rates` (request rate) and
`summaries` (latency histograms, overall and per endpoint via the
metrics-by-endpoint plugin).
"""

import json
import re
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"
OUTPUT = SCRIPT_DIR / "compare-report.html"
SUMMARY = SCRIPT_DIR / "summary.md"

# Preferred display order; anything else is appended alphabetically.
ORDER = ["python", "java", "go", "nest", "csharp"]
PROFILE_ORDER = ["baseline", "parallel", "indexed"]
LABELS = {"python": "Python", "java": "Java", "go": "Go", "nest": "Node/NestJS", "csharp": "C#"}
COLORS = {
    "python": "#3776ab",
    "java": "#e76f00",
    "go": "#00add8",
    "nest": "#e0234e",
    "csharp": "#512bd4",
}
ENDPOINTS = ["/health", "/search/file", "/search/many"]
METRICS = ["p50", "p90", "p95", "p99", "mean", "max"]
ROUND_FILE = re.compile(r"^(?P<svc>[a-z0-9_-]+)\.r(?P<round>\d+)\.json$")


def spread(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {"med": statistics.median(values), "lo": min(values), "hi": max(values), "n": len(values)}


def endpoint_latency(agg: dict, endpoint: str) -> dict | None:
    """Per-endpoint latency histogram from the metrics-by-endpoint plugin."""
    s = agg.get("summaries", {}).get(f"plugins.metrics-by-endpoint.response_time.{endpoint}")
    if not s:
        return None
    return {"count": s.get("count"), "p50": s.get("median"), "p90": s.get("p90"), "p95": s.get("p95"),
            "p99": s.get("p99"), "mean": s.get("mean"), "max": s.get("max")}


def overall_stats(agg: dict) -> dict:
    counters = agg.get("counters", {})
    return {
        "requests": counters.get("http.requests", 0),
        "success_2xx": sum(v for k, v in counters.items() if k.startswith("http.codes.2")),
        "failed": counters.get("vusers.failed", 0),
        "rps": agg.get("rates", {}).get("http.request_rate", 0),
    }


def load():
    """{profile: {service: [aggregate, ...]}} in round order."""
    out = defaultdict(lambda: defaultdict(list))
    for profile_dir in sorted(p for p in RESULTS_DIR.glob("*") if p.is_dir()):
        files = []
        for path in profile_dir.glob("*.json"):
            m = ROUND_FILE.match(path.name)
            if m:
                files.append((m["svc"], int(m["round"]), path))
        for svc, _, path in sorted(files, key=lambda f: (f[0], f[1])):
            with open(path, encoding="utf-8") as f:
                out[profile_dir.name][svc].append(json.load(f).get("aggregate", {}))
    return out


def by_order(keys, order):
    return sorted(keys, key=lambda k: (order.index(k) if k in order else len(order), k))


def build(raw):
    profiles = by_order(raw.keys(), PROFILE_ORDER)
    langs = by_order({s for p in raw.values() for s in p}, ORDER)
    data = {}
    for profile in profiles:
        data[profile] = {}
        for svc, rounds in raw[profile].items():
            overall = [overall_stats(a) for a in rounds]
            endpoints = {}
            for ep in ENDPOINTS:
                per_round = [endpoint_latency(a, ep) for a in rounds]
                per_round = [r for r in per_round if r]
                endpoints[ep] = {m: spread([r[m] for r in per_round]) for m in METRICS} if per_round else None
                if endpoints[ep]:
                    endpoints[ep]["count"] = sum(r["count"] or 0 for r in per_round)
            data[profile][svc] = {
                "rounds": len(rounds),
                "rps": spread([o["rps"] for o in overall]),
                "requests": sum(o["requests"] for o in overall),
                "success_2xx": sum(o["success_2xx"] for o in overall),
                "failed": sum(o["failed"] for o in overall),
                "endpoints": endpoints,
            }
    return {
        "generated": str(date.today()),
        "profiles": profiles,
        "languages": [{"id": l, "label": LABELS.get(l, l), "color": COLORS.get(l, "#888")} for l in langs],
        "endpoints": ENDPOINTS,
        "data": data,
    }


def fmt(s, digits=1):
    if not s:
        return "—"
    return f"{s['med']:.{digits}f}" + (f" ({s['lo']:.{digits}f}–{s['hi']:.{digits}f})" if s["n"] > 1 else "")


def write_summary(p):
    rounds = sorted({v["rounds"] for prof in p["data"].values() for v in prof.values()})
    lines = [
        "# Load test summary",
        "",
        f"Generated {p['generated']} by `compare.py` from {'/'.join(map(str, rounds))} round(s). "
        "Latencies in ms (lower is better); with several rounds the value is the median "
        "across rounds and the parentheses give the min–max range. Every service ran the "
        "same `artillery.yml` at the same constant arrival rate.",
        "",
    ]
    for profile in p["profiles"]:
        lines += [f"## `SEARCH_MODE={profile}`", "",
                  "| Language | /search/file p50 | /search/file p95 | /search/many p50 | /search/many p95 | failures |",
                  "|---|---:|---:|---:|---:|---:|"]
        for lang in p["languages"]:
            d = p["data"][profile].get(lang["id"])
            if not d:
                continue
            f, m = d["endpoints"]["/search/file"] or {}, d["endpoints"]["/search/many"] or {}
            lines.append(f"| {lang['label']} | {fmt(f.get('p50'))} | {fmt(f.get('p95'))} | "
                         f"{fmt(m.get('p50'))} | {fmt(m.get('p95'))} | {d['failed']} |")
        lines.append("")
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    raw = load()
    if not raw:
        raise SystemExit(f"no results in {RESULTS_DIR}/<profile>/ — run run-all.sh first")
    payload = build(raw)
    OUTPUT.write_text(HTML_TEMPLATE.replace("/*DATA*/", json.dumps(payload)), encoding="utf-8")
    write_summary(payload)
    print(f"wrote {OUTPUT} and {SUMMARY} (profiles: {', '.join(payload['profiles'])})")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Load test report — API/HTTP</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; color: #1c1c1c; padding: 0 1rem; }
  h1 { border-bottom: 2px solid #ddd; padding-bottom: .4rem; }
  .controls { margin: 1rem 0; display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; }
  .controls label { font-weight: 600; }
  .note { background: #f6f8fa; border-left: 4px solid #c0c7d0; padding: .8rem 1rem; font-size: .9rem; line-height: 1.5; }
  .chart-box { margin: 1.5rem 0 2.5rem; }
  .scroll { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: .82rem; margin-bottom: 2rem; }
  th, td { border: 1px solid #ddd; padding: 5px 8px; text-align: right; white-space: nowrap; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #f4f4f4; }
  caption { text-align: left; font-weight: 600; margin-bottom: .4rem; }
  code { background: #eef; padding: 0 .25rem; border-radius: 3px; }
  .fail { color: #c0392b; font-weight: 600; }
</style>
</head>
<body>
<h1>Load test report (API/HTTP)</h1>
<p><em>Artillery · generated <span id="gen"></span> · lower latency is better</em></p>

<div class="note">
  End-to-end HTTP: the web framework, JSON handling and the server's concurrency model are
  part of every number, and a large share of short requests. Every service runs the same
  <code>artillery.yml</code> at the same constant arrival rate, chosen so each should keep
  up; a median rising to seconds means a service is saturated, not just slower. Languages
  are compared within one <code>SEARCH_MODE</code> profile: <code>baseline</code> runs a
  single-threaded scan per request; <code>parallel</code> splits each file scan into
  chunks, and <code>/search/many</code> also runs one task per word length.
  With several rounds, bars show the median and whiskers the min–max across rounds.
</div>

<div class="controls">
  <span><label for="profile">Profile (SEARCH_MODE):</label> <select id="profile"></select></span>
  <span><label for="metric">Latency metric:</label> <select id="metric"></select></span>
  <span><label><input type="checkbox" id="log"> log scale</label></span>
</div>

<div class="chart-box"><h3>Latency by endpoint</h3><canvas id="latencyChart" height="120"></canvas></div>
<div class="chart-box"><h3>Same language, baseline vs parallel (<code>/search/many</code>, selected metric)</h3><canvas id="modeChart" height="90"></canvas></div>
<div id="tables" class="scroll"></div>

<script>
const DATA = /*DATA*/;
document.getElementById('gen').textContent = DATA.generated;
const METRICS = ['p50', 'p90', 'p95', 'p99', 'mean', 'max'];

function fill(id, values, initial) {
  const sel = document.getElementById(id);
  for (const v of values) { const o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o); }
  if (initial && values.includes(initial)) sel.value = initial;
  return sel;
}
const profileSel = fill('profile', DATA.profiles, 'parallel');
const metricSel = fill('metric', METRICS, 'p95');

const whiskers = {
  id: 'whiskers',
  afterDatasetsDraw(chart) {
    const scale = chart.scales.y, ctx = chart.ctx;
    ctx.save(); ctx.strokeStyle = '#333'; ctx.lineWidth = 1;
    chart.data.datasets.forEach((ds, i) => {
      const meta = chart.getDatasetMeta(i);
      if (!ds.ranges || meta.hidden) return;
      meta.data.forEach((bar, j) => {
        const r = ds.ranges[j];
        if (!r || r[0] == null || r[0] === r[1]) return;
        const a = scale.getPixelForValue(r[0]), b = scale.getPixelForValue(r[1]), w = Math.min(4, bar.width / 3);
        ctx.beginPath();
        ctx.moveTo(bar.x, a); ctx.lineTo(bar.x, b);
        ctx.moveTo(bar.x - w, a); ctx.lineTo(bar.x + w, a);
        ctx.moveTo(bar.x - w, b); ctx.lineTo(bar.x + w, b);
        ctx.stroke();
      });
    });
    ctx.restore();
  },
};

const stat = (profile, lang, ep, metric) => {
  const d = (DATA.data[profile] || {})[lang];
  return d && d.endpoints[ep] ? d.endpoints[ep][metric] : null;
};

const charts = {};
function chart(id, labels, datasets, yTitle, log) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type: 'bar', plugins: [whiskers], data: { labels, datasets },
    options: { responsive: true, plugins: { legend: { position: 'bottom' } },
      scales: { y: { type: log ? 'logarithmic' : 'linear', title: { display: true, text: yTitle } } } },
  });
}

function render() {
  const profile = profileSel.value, metric = metricSel.value, log = document.getElementById('log').checked;
  chart('latencyChart', DATA.endpoints, DATA.languages.map(l => ({
    label: l.label, backgroundColor: l.color,
    data: DATA.endpoints.map(ep => (stat(profile, l.id, ep, metric) || {}).med ?? null),
    ranges: DATA.endpoints.map(ep => { const s = stat(profile, l.id, ep, metric); return s ? [s.lo, s.hi] : null; }),
  })), 'ms (' + metric + ', SEARCH_MODE=' + profile + ')', log);

  const shades = ['#9aa5b1', '#3d4f63', '#c08b30'];
  chart('modeChart', DATA.languages.map(l => l.label), DATA.profiles.map((p, i) => ({
    label: p, backgroundColor: shades[i % shades.length],
    data: DATA.languages.map(l => (stat(p, l.id, '/search/many', metric) || {}).med ?? null),
    ranges: DATA.languages.map(l => { const s = stat(p, l.id, '/search/many', metric); return s ? [s.lo, s.hi] : null; }),
  })), 'ms (' + metric + ')', log);

  const fmt = (s, d = 1) => !s ? '' : s.med.toFixed(d) + (s.n > 1 ? ' <small>(' + s.lo.toFixed(d) + '–' + s.hi.toFixed(d) + ')</small>' : '');
  let h = '<table><caption>Overall, SEARCH_MODE=' + profile + '</caption><tr><th>Language</th><th>rounds</th><th>requests</th><th>2xx</th><th>failures</th><th>req/sec</th></tr>';
  for (const l of DATA.languages) {
    const d = (DATA.data[profile] || {})[l.id];
    if (!d) continue;
    h += '<tr><td>' + l.label + '</td><td>' + d.rounds + '</td><td>' + d.requests + '</td><td>' + d.success_2xx +
      '</td><td' + (d.failed ? ' class="fail"' : '') + '>' + d.failed + '</td><td>' + fmt(d.rps) + '</td></tr>';
  }
  h += '</table>';
  for (const ep of DATA.endpoints) {
    h += '<table><caption><code>' + ep + '</code> latency (ms), SEARCH_MODE=' + profile + '</caption><tr><th>Language</th><th>count</th>' +
      METRICS.map(m => '<th>' + m + '</th>').join('') + '</tr>';
    for (const l of DATA.languages) {
      const d = (DATA.data[profile] || {})[l.id];
      const e = d && d.endpoints[ep];
      if (!e) continue;
      h += '<tr><td>' + l.label + '</td><td>' + e.count + '</td>' + METRICS.map(m => '<td>' + fmt(e[m]) + '</td>').join('') + '</tr>';
    }
    h += '</table>';
  }
  document.getElementById('tables').innerHTML = h;
}
[profileSel, metricSel, document.getElementById('log')].forEach(e => e.addEventListener('change', render));
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
