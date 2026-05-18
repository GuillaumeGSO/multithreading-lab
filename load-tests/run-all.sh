#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
ARTILLERY_YML="$SCRIPT_DIR/artillery.yml"

declare -A ENVS=(
  [python-base]=8000
  [python-improved]=8001
  [python-indexed]=8005
  [java]=8002
  [go]=8003
  [cpp]=8004
)

declare -A CONTAINERS=(
  [python-base]=multithreading-lab-python-base-1
  [python-improved]=multithreading-lab-python-improved-1
  [python-indexed]=multithreading-lab-python-indexed-1
  [java]=multithreading-lab-java-1
  [go]=multithreading-lab-go-1
  [cpp]=multithreading-lab-cpp-1
)

CPU_THRESHOLD=10
CPU_POLL_INTERVAL=3

wait_for_cpu_cool() {
  local container="$1"
  echo -n "Waiting for $container CPU to drop below ${CPU_THRESHOLD}%"
  while true; do
    cpu=$(docker stats --no-stream --format "{{.CPUPerc}}" "$container" 2>/dev/null | tr -d '%')
    if [ -z "$cpu" ]; then
      echo " (container gone)"
      break
    fi
    cpu_int=${cpu%.*}
    if [ "${cpu_int:-999}" -lt "$CPU_THRESHOLD" ]; then
      echo " → ${cpu}% (cool)"
      break
    fi
    echo -n " ${cpu}%"
    sleep "$CPU_POLL_INTERVAL"
  done
}

mkdir -p "$RESULTS_DIR"

ran=()

for env in python-base python-improved python-indexed java go cpp; do
  port=${ENVS[$env]}
  url="http://localhost:$port"

  printf "%-20s" "$env"

  if curl -sf "$url/health" > /dev/null 2>&1; then
    echo "→ running..."
    npx --yes artillery run \
      --environment "$env" \
      --output "$RESULTS_DIR/$env.json" \
      "$ARTILLERY_YML"
    ran+=("$env")
    wait_for_cpu_cool "${CONTAINERS[$env]}"
  else
    echo "→ skipped (not reachable on :$port)"
  fi
done

echo ""

if [ ${#ran[@]} -eq 0 ]; then
  echo "No containers were reachable — nothing to compare."
  exit 0
fi

echo "Generating comparative report..."
python3 "$SCRIPT_DIR/compare.py"
echo "Done → $SCRIPT_DIR/compare-report.html"
