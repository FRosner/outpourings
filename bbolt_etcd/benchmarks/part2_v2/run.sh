#!/usr/bin/env bash
set -euo pipefail

# Part 2 benchmark runner: runs ONLY etcd v2.3.8 into benchmarks/part2_v2/results/.
# If Part 1's v0.4.9.json exists, also renders read-only comparison overlays inside part2_v2/results/
# without re-running or modifying Part 1.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PART1_JSON="${SCRIPT_DIR}/../part1_v04/results/v0.4.9.json"

COMPARE_ARGS=()
if [[ -f "${PART1_JSON}" ]]; then
  COMPARE_ARGS=(--compare-with "${PART1_JSON}")
fi

exec "${SCRIPT_DIR}/../common/run_concurrency_bench.sh" \
  --version "v2.3.8" \
  --results-dir "${SCRIPT_DIR}/results" \
  "${COMPARE_ARGS[@]}" \
  "$@"
