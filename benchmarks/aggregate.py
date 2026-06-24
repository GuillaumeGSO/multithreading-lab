#!/usr/bin/env python3
"""Aggregate per-language bench JSON (results/*.json) into a single
self-contained compare.html with a Chart.js grouped bar chart.

Stdlib only. The chart focuses on language implementation (algorithm +
in-process concurrency), not API/HTTP handling: a mode selector switches
between the concurrency modes, a checkbox toggles a log scale, and file vs
multi-length cases are charted separately so the fan-out story stands apart
from single-file scans.
"""

import glob
import json
import os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
CASES_PATH = os.path.join(HERE, "cases.json")
OUT_PATH = os.path.join(HERE, "compare.html")

# Preferred display order; anything else is appended alphabetically.
ORDER = ["python", "java", "go", "cpp", "nest"]
COLORS = {
    "python": "#3776ab",
    "java": "#e76f00",
    "go": "#00add8",
    "cpp": "#9b4f96",
    "nest": "#e0234e",
}


def load_results():
    results = {}
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        lang = data.get("language") or os.path.splitext(os.path.basename(path))[0]
        results[lang] = data
    return results


def main():
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    case_order = [{"name": c["name"], "kind": c["kind"]} for c in cases]

    results = load_results()
    if not results:
        raise SystemExit(f"no result files in {RESULTS_DIR} — run run-all.sh first")

    langs = sorted(
        results.keys(),
        key=lambda l: (ORDER.index(l) if l in ORDER else len(ORDER), l),
    )
    languages = [{"id": l, "label": results[l].get("label", l), "color": COLORS.get(l, "#888")} for l in langs]

    # results[lang][case_name] = {count, modes:{mode:{median_ms,min_ms}}}
    by_lang = {}
    for l in langs:
        by_case = {}
        for c in results[l].get("cases", []):
            by_case[c["name"]] = {"count": c.get("count"), "modes": c.get("modes", {})}
        by_lang[l] = by_case

    meta = {l: results[l].get("meta", {}) for l in langs}
    throughput = {l: results[l].get("throughput") for l in langs if results[l].get("throughput")}

    payload = {
        "generated": str(date.today()),
        "languages": languages,
        "cases": case_order,
        "byLang": by_lang,
        "meta": meta,
        "throughput": throughput,
    }

    html = HTML_TEMPLATE.replace("/*DATA*/", json.dumps(payload))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {OUT_PATH} ({len(langs)} languages)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Language concurrency benchmark — in-process</title>
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
</style>
</head>
<body>
<h1>Language concurrency benchmark</h1>
<p><em>In-process (no HTTP) · generated <span id="gen"></span> · median of <span id="iters">N</span> runs (<span id="warmup">?</span> warmup, split degree <span id="split">?</span>), lower is better</em></p>

<div class="note">
  This measures <strong>language implementation</strong> — the search algorithm and
  its in-process concurrency — not API/HTTP handling (that is what the Artillery
  load test covers). Read the modes as:
  <ul>
    <li><code>baseline</code> — single-threaded scan.</li>
    <li><code>indexed</code> — positional inverted index (Java only): seeds candidates from pinned hints, O(result) when hints are present. Falls back to scan when no pinned hints.</li>
    <li><code>split</code> — one file scanned in N contiguous chunks across threads (intra-file parallelism).</li>
    <li><code>fanout</code> — one thread/task per word length (per-length fan-out).</li>
    <li><code>nested</code> — per-length fan-out where each length is also split (threads spawning work).</li>
  </ul>
  Caveats: <strong>Python</strong> threads share the GIL, so <code>split</code>/<code>nested</code>
  rarely beat <code>baseline</code> — Python scales at the process/API layer instead, not via
  threads here. <em>python</em>'s <code>baseline</code> dispatches each query to the faster of two
  strategies (a positional/frequency index when a pinned hint or strict mode can exploit it,
  otherwise a lean on-load scan), so per-query cost is the min of the two. <strong>Java</strong>'s
  <code>indexed</code> mode mirrors this dispatch: it builds a pos→char→Set index per (lang, length)
  and seeds a tight candidate set from pinned hints, reducing work to O(result) instead of O(vocabulary).
  <strong>Go/C++</strong> use real threads/goroutines, so <code>nested</code> can oversubscribe the
  2-CPU box; <strong>Nest</strong>'s fixed worker pool and <strong>Java</strong>'s virtual threads
  instead queue/absorb the extra work. These searches are sub-millisecond, so thread-creation
  overhead often dominates any speedup.
</div>

<div class="controls">
  <span><label for="mode">Mode:</label> <select id="mode"></select></span>
  <span><label><input type="checkbox" id="log"> log scale</label></span>
  <span><label><input type="checkbox" id="useMin"> use min (instead of median)</label></span>
</div>

<div class="chart-box"><h3>Single-file searches (<code>/search/file</code>)</h3><canvas id="fileChart" height="120"></canvas></div>
<div class="chart-box"><h3>Multi-length searches (<code>/search/many</code>)</h3><canvas id="manyChart" height="120"></canvas></div>

<h2>Throughput under concurrent load</h2>
<div class="note">
  Many searches in flight at once (each a single-threaded scan dispatched via the
  language's request-handling primitive), bounded by the container's 2 CPUs. This is
  the in-process analog of the API load test — higher ops/sec is better. Expect
  <strong>Python</strong> near one core (GIL serializes threads); <strong>Go/Java/C++</strong> near two;
  <strong>Nest</strong> bounded by its worker-pool size and message-passing overhead.
</div>
<div class="chart-box"><canvas id="tputChart" height="90"></canvas></div>
<div id="tputTable"></div>

<div id="tables"></div>

<script>
const DATA = /*DATA*/;
document.getElementById('gen').textContent = DATA.generated;

// Show the actual pacing used. meta is per-language; collapse to a single value
// when they all match, otherwise list the distinct values.
function metaField(key) {
  const vals = [...new Set(Object.values(DATA.meta || {})
    .map(m => m && m[key]).filter(v => v != null))];
  return vals.length ? vals.join(' / ') : '?';
}
document.getElementById('iters').textContent = metaField('iterations');
document.getElementById('warmup').textContent = metaField('warmup');
document.getElementById('split').textContent = metaField('split_degree');

const FILE_MODES = ['baseline', 'indexed', 'split'];
const MANY_MODES = ['baseline', 'fanout', 'nested'];
const ALL_MODES = ['baseline', 'indexed', 'split', 'fanout', 'nested'];

const fileCases = DATA.cases.filter(c => c.kind === 'file').map(c => c.name);
const manyCases = DATA.cases.filter(c => c.kind === 'many').map(c => c.name);

// Populate the mode selector with the modes that actually exist in the data.
const present = new Set();
for (const lang of DATA.languages)
  for (const cn of Object.keys(DATA.byLang[lang.id] || {}))
    for (const m of Object.keys(DATA.byLang[lang.id][cn].modes || {})) present.add(m);
const modeSel = document.getElementById('mode');
for (const m of ALL_MODES) if (present.has(m)) {
  const o = document.createElement('option'); o.value = m; o.textContent = m; modeSel.appendChild(o);
}

function value(langId, caseName, mode, useMin) {
  const c = (DATA.byLang[langId] || {})[caseName];
  if (!c || !c.modes[mode]) return null;
  return useMin ? c.modes[mode].min_ms : c.modes[mode].median_ms;
}

function datasets(caseNames, mode, useMin) {
  return DATA.languages.map(l => ({
    label: l.label,
    data: caseNames.map(cn => value(l.id, cn, mode, useMin)),
    backgroundColor: l.color,
  }));
}

function shortLabels(names) {
  return names.map(n => n.split('—')[0].trim());
}

let fileChart, manyChart;
function makeChart(canvasId, caseNames, mode, useMin, log) {
  return new Chart(document.getElementById(canvasId), {
    type: 'bar',
    data: { labels: shortLabels(caseNames), datasets: datasets(caseNames, mode, useMin) },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y == null ? 'n/a' : ctx.parsed.y.toFixed(4)} ms` } },
      },
      scales: { y: { type: log ? 'logarithmic' : 'linear', title: { display: true, text: 'ms (' + (useMin ? 'min' : 'median') + ')' } } },
    },
  });
}

function render() {
  const mode = modeSel.value;
  const log = document.getElementById('log').checked;
  const useMin = document.getElementById('useMin').checked;
  // file chart: 'fanout'/'nested' don't apply -> fall back to 'split' then 'baseline'.
  const fileMode = FILE_MODES.includes(mode) && present.has(mode) ? mode : (present.has('split') ? 'split' : 'baseline');
  const manyMode = MANY_MODES.includes(mode) ? mode : 'baseline';
  if (fileChart) fileChart.destroy();
  if (manyChart) manyChart.destroy();
  fileChart = makeChart('fileChart', fileCases, fileMode, useMin, log);
  manyChart = makeChart('manyChart', manyCases, manyMode, useMin, log);
}
modeSel.addEventListener('change', render);
document.getElementById('log').addEventListener('change', render);
document.getElementById('useMin').addEventListener('change', render);
render();

// --- throughput chart + table ---
const tput = DATA.throughput || {};
const tputLangs = DATA.languages.filter(l => tput[l.id]);
if (tputLangs.length) {
  new Chart(document.getElementById('tputChart'), {
    type: 'bar',
    data: {
      labels: tputLangs.map(l => l.label),
      datasets: [{
        label: 'ops/sec',
        data: tputLangs.map(l => tput[l.id].ops_per_sec),
        backgroundColor: tputLangs.map(l => l.color),
      }],
    },
    options: {
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ctx.parsed.x.toFixed(1) + ' ops/sec' } },
      },
      scales: { x: { title: { display: true, text: 'ops/sec (higher is better)' } } },
    },
  });
  const tt = document.getElementById('tputTable');
  const sample = tput[tputLangs[0].id];
  let h = '<table><caption>concurrency ' + sample.concurrency + ', ' + sample.ops +
    ' ops, workload: <code>' + sample.workload + '</code></caption>' +
    '<tr><th>Language</th><th>ops/sec</th><th>median latency (ms)</th><th>elapsed (ms)</th><th>words/op</th></tr>';
  for (const l of tputLangs) {
    const t = tput[l.id];
    h += '<tr><td>' + l.label + '</td><td>' + t.ops_per_sec.toFixed(1) + '</td><td>' +
      t.median_latency_ms.toFixed(3) + '</td><td>' + t.elapsed_ms.toFixed(1) + '</td><td>' +
      (t.count == null ? '' : t.count) + '</td></tr>';
  }
  tt.innerHTML = h + '</table>';
}

// --- detail tables: one per case, language x mode (median ms) ---
const tables = document.getElementById('tables');
for (const c of DATA.cases) {
  const modes = c.kind === 'file' ? FILE_MODES : MANY_MODES;
  const t = document.createElement('table');
  let head = '<caption>' + c.name + '</caption><tr><th>Language</th><th>count</th>';
  for (const m of modes) head += '<th>' + m + ' (med / min ms)</th>';
  head += '</tr>';
  let rows = '';
  for (const l of DATA.languages) {
    const cc = (DATA.byLang[l.id] || {})[c.name];
    if (!cc) continue;
    rows += '<tr><td>' + l.label + '</td><td>' + (cc.count == null ? '' : cc.count) + '</td>';
    for (const m of modes) {
      const mm = cc.modes[m];
      rows += '<td>' + (mm ? mm.median_ms.toFixed(4) + ' / ' + mm.min_ms.toFixed(4) : '') + '</td>';
    }
    rows += '</tr>';
  }
  t.innerHTML = head + rows;
  tables.appendChild(t);
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
