#!/usr/bin/env python3
"""Aggregate per-language bench JSON into compare.html and summary.md.

Input: results/<lang>.r<round>.json (one file per language per round, written by
run-all.sh with ROUNDS=N); a plain results/<lang>.json counts as one round.

Every number is reported as the median across rounds with the min–max range, so
run-to-run noise is visible next to the value. Charts compare one mode at a time
(the same mode for every language). The positional index is shown separately, as
an algorithm comparison (scan vs index), not mixed into the concurrency charts.

Stdlib only.
"""

import glob
import json
import math
import os
import re
import statistics
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
CASES_PATH = os.path.join(HERE, "cases.json")
OUT_PATH = os.path.join(HERE, "compare.html")
SUMMARY_PATH = os.path.join(HERE, "summary.md")

# Preferred display order; anything else is appended alphabetically.
ORDER = ["python", "java", "go", "nest", "csharp"]
COLORS = {
    "python": "#3776ab",
    "java": "#e76f00",
    "go": "#00add8",
    "nest": "#e0234e",
    "csharp": "#512bd4",
}
# Concurrency modes per endpoint. "indexed" is an algorithm, reported apart.
FILE_MODES = ["baseline", "split"]
MANY_MODES = ["baseline", "fanout", "nested"]

ROUND_FILE = re.compile(r"^(?P<lang>[a-z0-9_-]+?)(?:\.r(?P<round>\d+))?\.json$")


def load_rounds():
    """{lang: [report, ...]} — one report per round, in round order."""
    rounds = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json"))):
        m = ROUND_FILE.match(os.path.basename(path))
        if not m:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        lang = data.get("language") or m["lang"]
        rounds[lang].append((int(m["round"] or 0), data))
    return {lang: [d for _, d in sorted(items, key=lambda x: x[0])] for lang, items in rounds.items()}


def spread(values):
    """{med, lo, hi, n} over the per-round values (None when there are none)."""
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {"med": statistics.median(values), "lo": min(values), "hi": max(values), "n": len(values)}


def geomean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values)) if values else None


def shape_of(case_name):
    """'file len=7 mixed strict' -> 'mixed strict'."""
    return case_name.split(" ", 2)[-1]


def build(cases, rounds):
    langs = sorted(rounds, key=lambda l: (ORDER.index(l) if l in ORDER else len(ORDER), l))
    first = {l: rounds[l][0] for l in langs}
    languages = [{"id": l, "label": first[l].get("label", l), "color": COLORS.get(l, "#888"),
                  "rounds": len(rounds[l])} for l in langs]
    file_cases = [c["name"] for c in cases if c["kind"] == "file"]
    many_cases = [c["name"] for c in cases if c["kind"] == "many"]

    # per_round[lang][case][mode] = [median_ms of round 1, round 2, ...]
    per_round = {l: defaultdict(lambda: defaultdict(list)) for l in langs}
    counts = {l: {} for l in langs}
    for l in langs:
        for report in rounds[l]:
            for c in report.get("cases", []):
                counts[l][c["name"]] = c.get("count")
                for mode, v in c.get("modes", {}).items():
                    per_round[l][c["name"]][mode].append(v.get("median_ms"))

    by_lang = {l: {cn: {"count": counts[l].get(cn),
                        "modes": {m: spread(vs) for m, vs in modes.items()}}
                   for cn, modes in per_round[l].items()} for l in langs}

    # Headline: per mode, the geometric mean over every case of that endpoint,
    # computed per round, then median and range across rounds.
    def summary(names, mode):
        out = {}
        for l in langs:
            per_case = [per_round[l].get(cn, {}).get(mode) for cn in names]
            if not all(per_case):
                continue
            n = min(len(v) for v in per_case)
            out[l] = spread([geomean([v[r] for v in per_case]) for r in range(n)])
        return out

    summaries = {
        "file": {m: summary(file_cases, m) for m in FILE_MODES},
        "many": {m: summary(many_cases, m) for m in MANY_MODES},
    }

    # Algorithm view: scan vs index (/search/file), as a speedup per query shape.
    shapes = list(dict.fromkeys(shape_of(cn) for cn in file_cases))
    algorithm = {}
    for l in langs:
        if not any("indexed" in per_round[l].get(cn, {}) for cn in file_cases):
            continue
        by_shape = {}
        for shape in shapes:
            ratios = []
            for cn in file_cases:
                if shape_of(cn) != shape:
                    continue
                modes = by_lang[l].get(cn, {}).get("modes", {})
                if modes.get("baseline") and modes.get("indexed"):
                    ratios.append(modes["baseline"]["med"] / modes["indexed"]["med"])
            by_shape[shape] = geomean(ratios)
        algorithm[l] = by_shape

    throughput = {}
    for l in langs:
        tps = [r.get("throughput") for r in rounds[l] if r.get("throughput")]
        if tps:
            throughput[l] = {"ops_per_sec": spread([t["ops_per_sec"] for t in tps]),
                             "median_latency_ms": spread([t["median_latency_ms"] for t in tps]),
                             "concurrency": tps[0].get("concurrency"), "ops": tps[0].get("ops"),
                             "workload": tps[0].get("workload")}

    # Correctness: every language must find the same number of words per case.
    mismatches = []
    for c in cases:
        found = {l: counts[l].get(c["name"]) for l in langs if c["name"] in counts[l]}
        if len(set(found.values())) > 1:
            mismatches.append({"case": c["name"], "counts": found})

    return {
        "generated": str(date.today()),
        "languages": languages,
        "cases": [{"name": c["name"], "kind": c["kind"]} for c in cases],
        "byLang": by_lang,
        "summaries": summaries,
        "shapes": shapes,
        "algorithm": algorithm,
        "throughput": throughput,
        "meta": {l: first[l].get("meta", {}) for l in langs},
        "mismatches": mismatches,
    }


def fmt(s, digits=3):
    if not s:
        return "—"
    if s["n"] > 1:
        return f"{s['med']:.{digits}f} ({s['lo']:.{digits}f}–{s['hi']:.{digits}f})"
    return f"{s['med']:.{digits}f}"


def write_summary(p):
    labels = {l["id"]: l["label"] for l in p["languages"]}
    rounds = sorted({l["rounds"] for l in p["languages"]})
    lines = [
        "# In-process benchmark summary",
        "",
        f"Generated {p['generated']} by `aggregate.py` from {'/'.join(map(str, rounds))} round(s) "
        "per language. Each value is the geometric mean of the per-case medians, in ms "
        "(lower is better). With several rounds it shows the median across rounds and, "
        "in parentheses, the min–max range.",
        "",
    ]
    for kind, title in (("file", "`/search/file`"), ("many", "`/search/many`")):
        modes = FILE_MODES if kind == "file" else MANY_MODES
        lines += [f"## {title}", "", "| Language | " + " | ".join(modes) + " |",
                  "|---|" + "---:|" * len(modes)]
        for l in p["languages"]:
            row = [fmt(p["summaries"][kind][m].get(l["id"])) for m in modes]
            lines.append(f"| {labels[l['id']]} | " + " | ".join(row) + " |")
        lines.append("")
    if p["algorithm"]:
        lines += ["## Scan vs positional index (`/search/file`)", "",
                  "Speedup of the index dispatcher over the single-threaded scan "
                  "(geometric mean per query shape; above 1 means the index is faster).", "",
                  "| Shape | " + " | ".join(labels[l] for l in p["algorithm"]) + " |",
                  "|---|" + "---:|" * len(p["algorithm"])]
        for shape in p["shapes"]:
            cells = [f"{p['algorithm'][l][shape]:.1f}×" if p["algorithm"][l].get(shape) else "—"
                     for l in p["algorithm"]]
            lines.append(f"| {shape} | " + " | ".join(cells) + " |")
        lines.append("")
    if p["throughput"]:
        lines += ["## Throughput (many searches in flight, single-threaded scan each)", "",
                  "| Language | ops/sec |", "|---|---:|"]
        for l in p["languages"]:
            if l["id"] in p["throughput"]:
                lines.append(f"| {labels[l['id']]} | {fmt(p['throughput'][l['id']]['ops_per_sec'], 1)} |")
        lines.append("")
    lines += ["## Correctness", "",
              "All languages found the same number of words for every case."
              if not p["mismatches"] else
              f"**{len(p['mismatches'])} case(s) differ between languages** — see compare.html."]
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    rounds = load_rounds()
    if not rounds:
        raise SystemExit(f"no result files in {RESULTS_DIR} — run run-all.sh first")
    payload = build(cases, rounds)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE.replace("/*DATA*/", json.dumps(payload)))
    write_summary(payload)
    n = ", ".join(f"{l['id']}×{l['rounds']}" for l in payload["languages"])
    print(f"wrote {OUT_PATH} and {SUMMARY_PATH} ({n})")
    if payload["mismatches"]:
        print(f"WARNING: {len(payload['mismatches'])} case(s) have different word counts across languages")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Concurrency benchmark — in-process</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; color: #1c1c1c; padding: 0 1rem; }
  h1 { border-bottom: 2px solid #ddd; padding-bottom: .4rem; }
  h2 { margin-top: 2.5rem; }
  .controls { margin: 1rem 0; display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; }
  .controls label { font-weight: 600; }
  .note { background: #f6f8fa; border-left: 4px solid #c0c7d0; padding: .8rem 1rem; font-size: .9rem; line-height: 1.5; }
  .warn { background: #fff4e5; border-left: 4px solid #e8a33d; padding: .8rem 1rem; }
  .chart-box { margin: 1.5rem 0 2.5rem; }
  .scroll { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: .82rem; margin-bottom: 2rem; }
  th, td { border: 1px solid #ddd; padding: 5px 8px; text-align: right; white-space: nowrap; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #f4f4f4; }
  caption { text-align: left; font-weight: 600; margin-bottom: .4rem; }
  code { background: #eef; padding: 0 .25rem; border-radius: 3px; }
  details { margin: 1rem 0; }
</style>
</head>
<body>
<h1>Concurrency benchmark (in-process)</h1>
<p><em>Generated <span id="gen"></span> · <span id="rounds"></span> · each round: median of <span id="iters">N</span> runs after <span id="warmup">?</span> warmup · split degree <span id="split">?</span> · lower is better</em></p>

<div class="note">
  This calls each language's search functions directly inside its container, with no HTTP,
  under the same 2-CPU limit. Every language runs the <strong>same scan algorithm</strong> in
  the same mode, so a chart compares runtimes, not algorithms:
  <ul>
    <li><code>baseline</code>: single-threaded scan.</li>
    <li><code>split</code> (<code>/search/file</code>): one word list scanned in N contiguous chunks on N threads.</li>
    <li><code>fanout</code> (<code>/search/many</code>): one thread or task per word length.</li>
    <li><code>nested</code> (<code>/search/many</code>): fan-out where each length is also split.</li>
  </ul>
  Each bar is the median across rounds; the whisker spans the fastest and slowest round.
  Python threads share the GIL, so its threaded modes cannot use the second core.
  Most searches take well under a millisecond, so starting threads can cost more than it saves.
</div>
<div id="mismatch"></div>

<h2>Summary per mode</h2>
<p>Geometric mean over all cases of the endpoint, in ms.</p>
<div id="summary" class="scroll"></div>

<h2>Per case</h2>
<div class="controls">
  <span><label for="fileMode"><code>/search/file</code> mode:</label> <select id="fileMode"></select></span>
  <span><label for="manyMode"><code>/search/many</code> mode:</label> <select id="manyMode"></select></span>
  <span><label><input type="checkbox" id="log" checked> log scale</label></span>
</div>
<div class="chart-box"><h3><code>/search/file</code></h3><canvas id="fileChart" height="130"></canvas></div>
<div class="chart-box"><h3><code>/search/many</code></h3><canvas id="manyChart" height="110"></canvas></div>

<h2>Algorithm: scan vs positional index</h2>
<div class="note">
  Separate from the concurrency comparison. Python, Java and C# also implement a
  positional index for <code>/search/file</code>: when a hint pins a letter to a position,
  candidates come from the index instead of scanning every word. Their dispatcher uses the
  index only when such a hint exists, and the scan otherwise. Bars show the speedup of that
  dispatcher over the single-threaded scan (above 1 means faster).
</div>
<div class="chart-box"><canvas id="algoChart" height="100"></canvas></div>

<h2>Throughput under concurrent load</h2>
<div class="note">
  Many single-threaded scans in flight at once, using each language's own way of running
  concurrent work, bounded by 2 CPUs. Higher is better. Expect Python near one core,
  because the GIL serializes its threads.
</div>
<div class="chart-box"><canvas id="tputChart" height="80"></canvas></div>
<div id="tputTable" class="scroll"></div>

<details><summary>All cases, all modes (median [min–max] ms)</summary><div id="tables" class="scroll"></div></details>

<script>
const DATA = /*DATA*/;
const FILE_MODES = ['baseline', 'split'];
const MANY_MODES = ['baseline', 'fanout', 'nested'];
document.getElementById('gen').textContent = DATA.generated;
const roundCounts = [...new Set(DATA.languages.map(l => l.rounds))];
document.getElementById('rounds').textContent = roundCounts.join('/') + ' round(s) per language';
function metaField(key) {
  const vals = [...new Set(Object.values(DATA.meta || {}).map(m => m && m[key]).filter(v => v != null))];
  return vals.length ? vals.join(' / ') : '?';
}
document.getElementById('iters').textContent = metaField('iterations');
document.getElementById('warmup').textContent = metaField('warmup');
document.getElementById('split').textContent = metaField('split_degree');

if (DATA.mismatches.length) {
  document.getElementById('mismatch').innerHTML = '<p class="warn"><strong>Correctness warning:</strong> ' +
    DATA.mismatches.length + ' case(s) return different word counts across languages: ' +
    DATA.mismatches.map(m => m.case).join(', ') + '</p>';
}

const fmt = (s, d = 3) => !s ? '—' : (s.n > 1 ? s.med.toFixed(d) + ' <small>(' + s.lo.toFixed(d) + '–' + s.hi.toFixed(d) + ')</small>' : s.med.toFixed(d));

// Summary tables.
(function () {
  let h = '';
  for (const [kind, modes, title] of [['file', FILE_MODES, '/search/file'], ['many', MANY_MODES, '/search/many']]) {
    h += '<table><caption><code>' + title + '</code></caption><tr><th>Language</th>' +
      modes.map(m => '<th>' + m + '</th>').join('') + '</tr>';
    for (const l of DATA.languages) {
      h += '<tr><td>' + l.label + '</td>' + modes.map(m => '<td>' + fmt(DATA.summaries[kind][m][l.id]) + '</td>').join('') + '</tr>';
    }
    h += '</table>';
  }
  document.getElementById('summary').innerHTML = h;
})();

// Whisker plugin: draws each dataset's `ranges` ([lo, hi] per bar) on top of the bars.
const whiskers = {
  id: 'whiskers',
  afterDatasetsDraw(chart) {
    const horizontal = chart.options.indexAxis === 'y';
    const scale = horizontal ? chart.scales.x : chart.scales.y;
    const ctx = chart.ctx;
    ctx.save();
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    chart.data.datasets.forEach((ds, i) => {
      const meta = chart.getDatasetMeta(i);
      if (!ds.ranges || meta.hidden) return;
      meta.data.forEach((bar, j) => {
        const r = ds.ranges[j];
        if (!r || r[0] == null || r[0] === r[1]) return;
        const a = scale.getPixelForValue(r[0]), b = scale.getPixelForValue(r[1]);
        const w = Math.min(4, (horizontal ? bar.height : bar.width) / 3);
        ctx.beginPath();
        if (horizontal) {
          ctx.moveTo(a, bar.y); ctx.lineTo(b, bar.y);
          ctx.moveTo(a, bar.y - w); ctx.lineTo(a, bar.y + w);
          ctx.moveTo(b, bar.y - w); ctx.lineTo(b, bar.y + w);
        } else {
          ctx.moveTo(bar.x, a); ctx.lineTo(bar.x, b);
          ctx.moveTo(bar.x - w, a); ctx.lineTo(bar.x + w, a);
          ctx.moveTo(bar.x - w, b); ctx.lineTo(bar.x + w, b);
        }
        ctx.stroke();
      });
    });
    ctx.restore();
  },
};

const fileCases = DATA.cases.filter(c => c.kind === 'file').map(c => c.name);
const manyCases = DATA.cases.filter(c => c.kind === 'many').map(c => c.name);
const cell = (lang, cn, mode) => ((DATA.byLang[lang] || {})[cn] || {modes: {}}).modes[mode];

function fillSelect(id, modes) {
  const sel = document.getElementById(id);
  for (const m of modes) { const o = document.createElement('option'); o.value = m; o.textContent = m; sel.appendChild(o); }
  return sel;
}
const fileSel = fillSelect('fileMode', FILE_MODES);
const manySel = fillSelect('manyMode', MANY_MODES);

const charts = {};
function caseChart(id, names, mode, log) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type: 'bar',
    plugins: [whiskers],
    data: {
      labels: names.map(n => n.replace(/^(file|many) /, '')),
      datasets: DATA.languages.map(l => ({
        label: l.label,
        backgroundColor: l.color,
        data: names.map(cn => (cell(l.id, cn, mode) || {}).med ?? null),
        ranges: names.map(cn => { const s = cell(l.id, cn, mode); return s ? [s.lo, s.hi] : null; }),
      })),
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { callbacks: { label: ctx => {
          const s = cell(DATA.languages[ctx.datasetIndex].id, names[ctx.dataIndex], mode);
          return ctx.dataset.label + ': ' + (s ? s.med.toFixed(4) + ' ms' + (s.n > 1 ? ' (' + s.lo.toFixed(4) + '–' + s.hi.toFixed(4) + ')' : '') : 'n/a');
        } } },
      },
      scales: { y: { type: log ? 'logarithmic' : 'linear', title: { display: true, text: 'ms (' + mode + ')' } } },
    },
  });
}
function render() {
  const log = document.getElementById('log').checked;
  caseChart('fileChart', fileCases, fileSel.value, log);
  caseChart('manyChart', manyCases, manySel.value, log);
}
[fileSel, manySel, document.getElementById('log')].forEach(e => e.addEventListener('change', render));
render();

// Algorithm chart: speedup per query shape, one dataset per language with an index.
(function () {
  const algoLangs = DATA.languages.filter(l => DATA.algorithm[l.id]);
  if (!algoLangs.length) { document.getElementById('algoChart').replaceWith('No indexed results.'); return; }
  new Chart(document.getElementById('algoChart'), {
    type: 'bar',
    data: {
      labels: DATA.shapes,
      datasets: algoLangs.map(l => ({ label: l.label, backgroundColor: l.color, data: DATA.shapes.map(s => DATA.algorithm[l.id][s]) })),
    },
    options: {
      plugins: { legend: { position: 'bottom' },
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + (ctx.parsed.y == null ? 'n/a' : ctx.parsed.y.toFixed(2) + '×') } } },
      scales: { y: { type: 'logarithmic', title: { display: true, text: 'speedup of index over scan (×)' } } },
    },
  });
})();

// Throughput chart + table.
(function () {
  const tput = DATA.throughput || {};
  const ls = DATA.languages.filter(l => tput[l.id]);
  if (!ls.length) return;
  new Chart(document.getElementById('tputChart'), {
    type: 'bar',
    plugins: [whiskers],
    data: { labels: ls.map(l => l.label), datasets: [{
      label: 'ops/sec', backgroundColor: ls.map(l => l.color),
      data: ls.map(l => tput[l.id].ops_per_sec.med),
      ranges: ls.map(l => [tput[l.id].ops_per_sec.lo, tput[l.id].ops_per_sec.hi]),
    }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false } },
      scales: { x: { title: { display: true, text: 'ops/sec (higher is better)' } } } },
  });
  const s = tput[ls[0].id];
  let h = '<table><caption>concurrency ' + s.concurrency + ', ' + s.ops + ' ops, workload: <code>' + s.workload +
    '</code></caption><tr><th>Language</th><th>ops/sec</th><th>median latency (ms)</th></tr>';
  for (const l of ls) h += '<tr><td>' + l.label + '</td><td>' + fmt(tput[l.id].ops_per_sec, 1) + '</td><td>' + fmt(tput[l.id].median_latency_ms, 1) + '</td></tr>';
  document.getElementById('tputTable').innerHTML = h + '</table>';
})();

// Detail tables.
(function () {
  const root = document.getElementById('tables');
  for (const c of DATA.cases) {
    const modes = c.kind === 'file' ? [...FILE_MODES, 'indexed'] : MANY_MODES;
    let h = '<caption>' + c.name + '</caption><tr><th>Language</th><th>words</th>' + modes.map(m => '<th>' + m + '</th>').join('') + '</tr>';
    for (const l of DATA.languages) {
      const cc = (DATA.byLang[l.id] || {})[c.name];
      if (!cc) continue;
      h += '<tr><td>' + l.label + '</td><td>' + (cc.count ?? '') + '</td>' + modes.map(m => '<td>' + fmt(cc.modes[m], 4) + '</td>').join('') + '</tr>';
    }
    const t = document.createElement('table'); t.innerHTML = h; root.appendChild(t);
  }
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
