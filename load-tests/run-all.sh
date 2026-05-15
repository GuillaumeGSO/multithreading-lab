#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
ARTILLERY_YML="$SCRIPT_DIR/artillery.yml"

declare -A ENVS=(
  [python-base]=8000
  [python-improved]=8001
  [java]=8002
  [go]=8003
  [cpp]=8004
)

mkdir -p "$RESULTS_DIR"

ran=()

for env in python-base python-improved java go cpp; do
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
