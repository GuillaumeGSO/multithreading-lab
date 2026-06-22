"""In-process benchmark runner for the Python implementation.

Copied into the python image as ``bench.py``. Reads the canonical cases from
CASES_PATH, times each case per concurrency mode with warmup + median-of-N, records
process memory, and prints a single JSON object to stdout (logs go to stderr).

Modes:
  file cases  -> baseline (single thread), split (intra-file, SPLIT_DEGREE chunks)
  many cases  -> baseline (sequential), fanout (per-length), nested (per-length + split)
"""

import json
import os
import resource
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from seek_words import Hint, search_in_file, search_in_many_files
from parallel import search_in_file_parallel, search_in_many_parallel, split_degree


def _peak_rss_mb() -> float:
    """Peak resident set of this process, in MB. ru_maxrss is KB on Linux (the
    bench container) and bytes on macOS."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


def _current_rss_mb():
    """Current resident set in MB (Linux /proc); None where unavailable."""
    try:
        with open("/proc/self/statm") as f:
            resident_pages = int(f.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
    except (FileNotFoundError, OSError, IndexError, ValueError):
        return None

WARMUP = int(os.environ.get("BENCH_WARMUP", "20"))
ITERS = int(os.environ.get("BENCH_ITERS", "100"))
LABEL = os.environ.get("BENCH_LABEL", "Python")
LANGUAGE = os.environ.get("BENCH_LANGUAGE", "python")

# Concurrent-load workload: identical across all languages. A heavy length-11
# scan (full alphabet, so every word does the full content check) filtered by a
# rare positional hint (tiny result set, so worker-thread serialization does not
# skew the worker-pool languages). Each op is one single-threaded baseline scan;
# the concurrency comes from running many ops at once via each language's
# request-handling primitive — that is the model under test.
CONCURRENCY = int(os.environ.get("CONCURRENCY", "16"))
THROUGHPUT_OPS = int(os.environ.get("THROUGHPUT_OPS", "200"))
TP_LANG = "fr"
TP_NB_CAR = 11
TP_LETTERS = list("abcdefghijklmnopqrstuvwxyz")
TP_HINTS = [Hint(1, "x", False)]
TP_STRICT = False


def log(*args):
    print(*args, file=sys.stderr)


def to_hints(raw):
    return [Hint(h["pos"], h.get("car"), h.get("inverted", False)) for h in raw]


def time_mode(fn):
    """Warmup then time ITERS runs; return (count, median_ms, min_ms)."""
    count = 0
    for _ in range(WARMUP):
        count = len(fn())
    samples = []
    for _ in range(ITERS):
        start = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - start) * 1000.0)
        count = len(result)
    return count, statistics.median(samples), min(samples)


def build_modes(case):
    """Return {mode_name: callable} for a case."""
    lang = case.get("lang", "fr")
    hints = to_hints(case.get("lst_hint", []))
    if case["kind"] == "file":
        nb_car = case["nb_car"]
        lst_car = case.get("lst_car", [])
        strict = case.get("strict", False)
        return {
            "baseline": lambda: list(search_in_file(
                lang=lang, nb_car=nb_car, lst_car=lst_car, lst_hint=hints, strict=strict)),
            "split": lambda: search_in_file_parallel(
                lang=lang, nb_car=nb_car, lst_car=lst_car, lst_hint=hints, strict=strict),
        }
    cars = case.get("cars", "")
    return {
        "baseline": lambda: list(search_in_many_files(lang=lang, cars=cars, lst_hint=hints)),
        "fanout": lambda: search_in_many_parallel(lang=lang, cars=cars, lst_hint=hints, threads=1),
        "nested": lambda: search_in_many_parallel(lang=lang, cars=cars, lst_hint=hints),
    }


def run_throughput():
    """Run THROUGHPUT_OPS baseline scans with CONCURRENCY in flight; report
    aggregate ops/sec and median per-op latency under load."""
    def op(_):
        start = time.perf_counter()
        r = list(search_in_file(lang=TP_LANG, nb_car=TP_NB_CAR, lst_car=TP_LETTERS,
                                lst_hint=TP_HINTS, strict=TP_STRICT))
        return (time.perf_counter() - start) * 1000.0, len(r)

    op(None)  # warmup (populate word cache)
    latencies = []
    count = 0
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for lat, c in ex.map(op, range(THROUGHPUT_OPS)):
            latencies.append(lat)
            count = c
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    latencies.sort()
    return {
        "workload": f"file nb_car={TP_NB_CAR} pool=26 hint=1:x (baseline scan per op)",
        "concurrency": CONCURRENCY,
        "ops": THROUGHPUT_OPS,
        "elapsed_ms": elapsed_ms,
        "ops_per_sec": THROUGHPUT_OPS / (elapsed_ms / 1000.0),
        "median_latency_ms": latencies[len(latencies) // 2],
        "count": count,
    }


def main():
    cases_path = os.environ.get("CASES_PATH", "/app/cases.json")
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    # Baseline before any word file is loaded / index is built, so the delta below
    # attributes the growth to the search indexes (shared across all modes).
    rss_baseline = _current_rss_mb()

    out_cases = []
    for case in cases:
        modes = {}
        count = 0
        for name, fn in build_modes(case).items():
            count, median_ms, min_ms = time_mode(fn)
            modes[name] = {"median_ms": median_ms, "min_ms": min_ms}
            log(f"[{LABEL}] {case['name']} / {name}: {count} words, "
                f"median {median_ms:.4f} ms")
        out_cases.append({
            "name": case["name"],
            "kind": case["kind"],
            "count": count,
            "modes": modes,
        })

    throughput = run_throughput()
    log(f"[{LABEL}] throughput: {throughput['ops_per_sec']:.1f} ops/s "
        f"@ concurrency {CONCURRENCY} ({throughput['count']} words/op)")

    # Memory is process-level: indexes are built once per (lang, length) and cached,
    # then shared across every mode — so there is no meaningful per-mode figure. We
    # report the peak RSS and the growth from baseline (≈ what the indexes cost).
    peak = _peak_rss_mb()
    end_rss = _current_rss_mb()
    memory = {
        "peak_rss_mb": round(peak, 1),
        "baseline_rss_mb": round(rss_baseline, 1) if rss_baseline is not None else None,
        "end_rss_mb": round(end_rss, 1) if end_rss is not None else None,
        "index_growth_mb": round(peak - rss_baseline, 1) if rss_baseline is not None else None,
    }
    log(f"[{LABEL}] memory: peak {memory['peak_rss_mb']} MB"
        + (f", index growth {memory['index_growth_mb']} MB" if memory['index_growth_mb'] is not None else ""))

    report = {
        "language": LANGUAGE,
        "label": LABEL,
        "meta": {"warmup": WARMUP, "iterations": ITERS, "split_degree": split_degree()},
        "cases": out_cases,
        "throughput": throughput,
        "memory": memory,
    }
    print(json.dumps(report))


if __name__ == "__main__":
    main()
