#!/usr/bin/env bash
# Run the in-process benchmark inside every container (same 2-CPU compose limit),
# capture each language's JSON report into results/, then build compare.html.
#
# Each runner prints ONLY its JSON report to stdout (logs go to stderr), so we
# redirect stdout to the result file. Override pacing/degree from the host env:
#   BENCH_WARMUP=20 BENCH_ITERS=100 SPLIT_DEGREE=2 bash run-all.sh
#   bash run-all.sh go java       # only the named services
#   ROUNDS=5 bash run-all.sh      # repeat the whole sweep (default 3)
#
# Each round benches every service once, in turn, so slow drift on the host
# spreads across languages instead of landing on one. Round k of a service is
# saved as results/<service>.r<k>.json; aggregate.py reports the median across
# rounds with the min–max range.
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

# Lighter defaults for the full sweep (≈half the work of each language's own
# 20/100/200 defaults). Override on the host to restore a heavy run, e.g.
#   BENCH_ITERS=100 THROUGHPUT_OPS=200 bash run-all.sh
: "${BENCH_WARMUP:=10}"
: "${BENCH_ITERS:=50}"
: "${THROUGHPUT_OPS:=100}"
: "${ROUNDS:=3}"

# Forward pacing knobs into the containers when set on the host.
ENVPASS=()
for v in BENCH_WARMUP BENCH_ITERS THROUGHPUT_OPS SPLIT_DEGREE; do
  [ -n "${!v:-}" ] && ENVPASS+=(-e "$v=${!v}")
done

# bench <service> <out-name> [docker-compose-run args... -- ] <command...>
# Runs `docker compose run --rm -T <env> <args> <service> <command>` and saves stdout.
bench() {
  local svc="$1" out="$2.r${ROUND:-1}"; shift 2
  echo "... running $svc" >&2
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
    python)
      bench python python \
        -e BENCH_LANGUAGE=python -e "BENCH_LABEL=Python" \
        --entrypoint .venv/bin/python python bench.py ;;
    go)
      bench go go --entrypoint /app/bench go ;;
    java)
      bench java java --entrypoint java java \
        -XX:+UseCompactObjectHeaders -Xmx380m \
        -Dloader.main=com.lab.search.BenchmarkRunner -cp /app/app.jar \
        org.springframework.boot.loader.launch.PropertiesLauncher ;;
    nest)
      bench nest nest --entrypoint node nest dist/bench.js ;;
    csharp)
      bench csharp csharp --entrypoint dotnet csharp /app/Bench.dll ;;
    *) echo "unknown service: $SELECTED" >&2 ;;
  esac
}

ALL=(python go java nest csharp)
TARGETS=("$@")
[ "${#TARGETS[@]}" -eq 0 ] && TARGETS=("${ALL[@]}")

# exFAT drive: macOS scatters AppleDouble `._*` files whose xattrs Docker's
# build-context sender can't read ("failed to xattr ._*: operation not permitted"),
# and .dockerignore doesn't spare them from the xattr walk. Scrub before building.
find .. -name '._*' -delete 2>/dev/null || true

echo "Building images..." >&2
$COMPOSE build "${TARGETS[@]}"

# Fresh results for the services being benched (others are kept).
for svc in "${TARGETS[@]}"; do
  rm -f "results/${svc}.json" "results/${svc}".r*.json "results/${svc}".r*.log
done

for round in $(seq 1 "$ROUNDS"); do
  echo "=== round $round/$ROUNDS" >&2
  for svc in "${TARGETS[@]}"; do
    ROUND="$round" run_service "$svc"
  done
done

echo "Aggregating -> compare.html" >&2
python3 aggregate.py

echo "Done. Open benchmarks/compare.html" >&2
