#!/usr/bin/env bash
set -euo pipefail

# Part 1 benchmark runner: runs ONLY etcd v0.4.9 into benchmarks/part1_v04/results/.
# Never regenerates or overwrites other parts' results or published blog post PNGs.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/../common/run_concurrency_bench.sh" \
  --version "v0.4.9" \
  --results-dir "${SCRIPT_DIR}/results" \
  "$@"
