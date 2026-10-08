#!/usr/bin/env bash
# Load-test every implementation under each SEARCH_MODE profile with the same
# artillery.yml, then build compare-report.html.
#
#   bash run-all.sh                      # all services, profiles baseline + parallel
#   bash run-all.sh go java              # only the named services
#   PROFILES=parallel bash run-all.sh    # only one profile
#   ROUNDS=3 bash run-all.sh             # repeat everything (default 1)
#
# For each profile the service is recreated with that SEARCH_MODE, so every
# language runs the same mode at the same time. Results land in
# results/<profile>/<service>.r<round>.json. Services are restored to the
# default mode at the end.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
ARTILLERY_YML="$SCRIPT_DIR/artillery.yml"
COMPOSE="docker compose -f $SCRIPT_DIR/../docker-compose.yml"

: "${PROFILES:=baseline parallel}"
: "${ROUNDS:=1}"
ALL=(python java go nest csharp)
TARGETS=("$@")
[ "${#TARGETS[@]}" -eq 0 ] && TARGETS=("${ALL[@]}")

if command -v artillery > /dev/null 2>&1; then
  ARTILLERY=(artillery)
elif [ -x "$SCRIPT_DIR/node_modules/.bin/artillery" ]; then
  ARTILLERY=("$SCRIPT_DIR/node_modules/.bin/artillery")
else
  echo "artillery not found — run 'npm install' in load-tests/ or 'npm install -g artillery'" >&2
  exit 1
fi

get_port() {
  case "$1" in
    python) echo 8007 ;;
    java)   echo 8002 ;;
    go)     echo 8003 ;;
    nest)   echo 8006 ;;
    csharp) echo 8005 ;;
    *) echo "unknown service: $1" >&2; exit 1 ;;
  esac
}

CPU_THRESHOLD=10
CPU_POLL_INTERVAL=3

wait_for_cpu_cool() {
  local container="$1"
  echo -n "  waiting for $container CPU to drop below ${CPU_THRESHOLD}%"
  while true; do
    cpu=$(docker stats --no-stream --format "{{.CPUPerc}}" "$container" 2>/dev/null | tr -d '%')
    if [ -z "$cpu" ]; then echo " (container gone)"; break; fi
    if [ "${cpu%.*}" -lt "$CPU_THRESHOLD" ] 2>/dev/null; then echo " → ${cpu}%"; break; fi
    echo -n " ${cpu}%"
    sleep "$CPU_POLL_INTERVAL"
  done
}

# start_service <service> <mode>: recreate the container with SEARCH_MODE=<mode>
# and wait until /health answers (an invalid mode makes the service exit).
start_service() {
  local svc="$1" mode="$2" port
  port=$(get_port "$svc")
  SEARCH_MODE="$mode" $COMPOSE up -d --force-recreate --no-deps "$svc" > /dev/null 2>&1
  for _ in $(seq 1 90); do
    curl -sf "http://localhost:$port/health" > /dev/null 2>&1 && return 0
    sleep 2
  done
  echo "  $svc did not become healthy with SEARCH_MODE=$mode" >&2
  return 1
}

echo "Building images..."
$COMPOSE build "${TARGETS[@]}"

for profile in $PROFILES; do
  rm -f "$RESULTS_DIR/$profile"/*.json
done

for round in $(seq 1 "$ROUNDS"); do
  for profile in $PROFILES; do
    mkdir -p "$RESULTS_DIR/$profile"
    for svc in "${TARGETS[@]}"; do
      echo "=== round $round/$ROUNDS · SEARCH_MODE=$profile · $svc"
      if ! start_service "$svc" "$profile"; then continue; fi
      "${ARTILLERY[@]}" run --environment "$svc" \
        --output "$RESULTS_DIR/$profile/$svc.r$round.json" "$ARTILLERY_YML" > /dev/null
      wait_for_cpu_cool "$($COMPOSE ps -q "$svc")"
    done
  done
done

echo "Restoring services to the default mode..."
$COMPOSE up -d --force-recreate --no-deps "${TARGETS[@]}" > /dev/null 2>&1

echo "Generating comparative report..."
python3 "$SCRIPT_DIR/compare.py"
echo "Done → $SCRIPT_DIR/compare-report.html"
