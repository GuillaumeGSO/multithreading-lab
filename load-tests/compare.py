import json
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"
OUTPUT = SCRIPT_DIR / "compare-report.html"

ENVS = ["python-base", "python-improved", "java", "go", "cpp"]
ENDPOINTS = ["/health", "/search/file", "/search/many"]


def load_results() -> dict[str, dict]:
    results = {}
    for env in ENVS:
        path = RESULTS_DIR / f"{env}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                results[env] = json.load(f)
    return results


def get_endpoint_stats(data: dict, endpoint: str) -> dict | None:
    key = f"plugins.metrics-by-endpoint.response_time.{endpoint}"
    return data.get("aggregate", {}).get("summaries", {}).get(key)


def get_overall_stats(data: dict) -> dict:
    counters = data.get("aggregate", {}).get("counters", {})
    rates = data.get("aggregate", {}).get("rates", {})
    return {
        "requests": counters.get("http.requests", 0),
        "failed": counters.get("vusers.failed", 0),
        "req_rate": rates.get("http.request_rate", 0),
    }


def fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0f} ms"


def cell(stats: dict | None, metric: str) -> str:
    if stats is None:
        return "<td>—</td>"
    return f"<td>{fmt(stats.get(metric))}</td>"


def generate_html(results: dict[str, dict]) -> str:
    langs = [e for e in ENVS if e in results]

    header_cells = "".join(f"<th>{e}</th>" for e in langs)

    endpoint_rows = ""
    for ep in ENDPOINTS:
        for metric, label in [("p50", "p50"), ("p95", "p95"), ("p99", "p99")]:
            cells = "".join(
                cell(get_endpoint_stats(results[e], ep), metric) for e in langs
            )
            endpoint_rows += f"<tr><td><code>{ep}</code></td><td>{label}</td>{cells}</tr>\n"

    overall_rows = ""
    for key, label in [("requests", "Total requests"), ("failed", "Failures"), ("req_rate", "Req/sec")]:
        cells = "".join(
            f"<td>{get_overall_stats(results[e]).get(key, '—')}</td>" for e in langs
        )
        overall_rows += f"<tr><td colspan='2'>{label}</td>{cells}</tr>\n"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Comparative Load Test Report</title>
  <style>
    body {{ font-family: sans-serif; max-width: 960px; margin: 2rem auto; color: #222; }}
    h1 {{ border-bottom: 2px solid #ddd; padding-bottom: 0.4rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #f4f4f4; }}
    td:first-child {{ white-space: nowrap; }}
  </style>
</head>
<body>
  <h1>Comparative Load Test Report</h1>
  <p><em>{date.today()}</em> — implementations tested: {", ".join(langs)}</p>

  <h2>Response time by endpoint</h2>
  <table>
    <thead>
      <tr><th>Endpoint</th><th>Metric</th>{header_cells}</tr>
    </thead>
    <tbody>
      {endpoint_rows}
    </tbody>
  </table>

  <h2>Overall</h2>
  <table>
    <thead>
      <tr><th colspan="2">Metric</th>{header_cells}</tr>
    </thead>
    <tbody>
      {overall_rows}
    </tbody>
  </table>
</body>
</html>"""


if __name__ == "__main__":
    results = load_results()
    if not results:
        print(f"No result files found in {RESULTS_DIR}")
        raise SystemExit(1)
    html = generate_html(results)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Report written to {OUTPUT}")
