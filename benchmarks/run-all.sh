#!/usr/bin/env bash
# Run the in-process benchmark inside every container (same 2-CPU compose limit),
# capture each language's JSON report into results/, then build compare.html.
#
# Each runner prints ONLY its JSON report to stdout (logs go to stderr), so we
# redirect stdout to the result file. Override pacing/degree from the host env:
#   BENCH_WARMUP=20 BENCH_ITERS=100 SPLIT_DEGREE=2 bash run-all.sh
#   bash run-all.sh go cpp        # only the named services
set -uo pipefail

cd "$(dirname "$0")"
COMPOSE="docker compose -f ../docker-compose.yml"
mkdir -p results

# Benchmarks run one container at a time. `docker compose run --rm` only removes
# its container on a clean exit; a Ctrl-C can detach it, leaving a zombie that
# keeps eating the 2-CPU budget and overlaps the next service. Force-remove any
# leftover one-shot bench containers on exit/interrupt so the run stays serial.
cleanup() {
  local ids
  ids=$(docker ps -aq --filter "name=-run-" 2>/dev/null)
  [ -n "$ids" ] && docker rm -f $ids >/dev/null 2>&1
  return 0
}
trap cleanup EXIT INT TERM

# Forward pacing knobs into the containers when set on the host.
ENVPASS=()
for v in BENCH_WARMUP BENCH_ITERS SPLIT_DEGREE; do
  [ -n "${!v:-}" ] && ENVPASS+=(-e "$v=${!v}")
done

# bench <service> <out-name> [docker-compose-run args... -- ] <command...>
# Runs `docker compose run --rm -T <env> <args> <service> <command>` and saves stdout.
bench() {
  local svc="$1" out="$2"; shift 2
  echo ">>> $svc" >&2
  if $COMPOSE run --rm -T ${ENVPASS[@]+"${ENVPASS[@]}"} "$@" >"results/${out}.json" 2>>"results/${out}.log"; then
    echo "    wrote results/${out}.json" >&2
  else
    echo "    FAILED ($svc) — see results/${out}.log" >&2
    rm -f "results/${out}.json"
  fi
}

want() { [ "$#" -eq 0 ] && return 0; for s in "$@"; do [ "$s" = "$SELECTED" ] && return 0; done; return 1; }

run_service() {
  SELECTED="$1"
  case "$SELECTED" in
    python-base)
      bench python-base python-base \
        -e BENCH_LANGUAGE=python-base -e "BENCH_LABEL=Python (base)" \
        --entrypoint .venv/bin/python python-base bench.py ;;
    python-improved)
      bench python-improved python-improved \
        -e BENCH_LANGUAGE=python-improved -e "BENCH_LABEL=Python (improved)" \
        --entrypoint .venv/bin/python python-improved bench.py ;;
    python-indexed)
      bench python-indexed python-indexed \
        -e BENCH_LANGUAGE=python-indexed -e "BENCH_LABEL=Python (indexed)" \
        --entrypoint .venv/bin/python python-indexed bench.py ;;
    go)
      bench go go --entrypoint /app/bench go ;;
    cpp)
      bench cpp cpp --entrypoint /app/bench cpp ;;
    java)
      bench java java --entrypoint java java \
        -XX:+UseCompactObjectHeaders \
        -Dloader.main=com.lab.search.BenchmarkRunner -cp /app/app.jar \
        org.springframework.boot.loader.launch.PropertiesLauncher ;;
    nest)
      bench nest nest --entrypoint node nest dist/bench.js ;;
    *) echo "unknown service: $SELECTED" >&2 ;;
  esac
}

ALL=(python-base python-improved python-indexed go cpp java nest)
TARGETS=("$@")
[ "${#TARGETS[@]}" -eq 0 ] && TARGETS=("${ALL[@]}")

echo "Building images..." >&2
$COMPOSE build "${TARGETS[@]}"

for svc in "${TARGETS[@]}"; do
  run_service "$svc"
done

echo "Aggregating -> compare.html" >&2
python3 aggregate.py

echo "Done. Open benchmarks/compare.html" >&2
