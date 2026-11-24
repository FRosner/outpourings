#!/usr/bin/env bash
set -euo pipefail

# Single-command reproducible etcd write-path benchmark harness.
# Defaults to --version v0.4.9 (Part 1) and supports --version v2.3.8 (Part 2).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PART1_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -d "/Applications/Docker.app/Contents/Resources/bin" ]]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH}"
fi

ETCD_VERSION="v0.4.9"
ETCD_REPO="${ETCD_REPO:-/Users/frosner/Documents/etcd}"
PLOT_ONLY=0
CONCURRENCIES=(1 4 16 64 256)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      ETCD_VERSION="$2"
      shift 2
      ;;
    --etcd-repo)
      ETCD_REPO="$2"
      shift 2
      ;;
    --plot-only)
      PLOT_ONLY=1
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--version v0.4.9|v2.3.8] [--etcd-repo /path/to/etcd] [--plot-only]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

RESULTS_DIR="${SCRIPT_DIR}/results"
FINAL_JSON="${RESULTS_DIR}/${ETCD_VERSION}.json"
BUILD_SRC_DIR="${SCRIPT_DIR}/.build_src"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
COMPOSE_PROJECT="etcd_bench"

PYTHON_BIN="${PART1_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

compose_down() {
  ETCD_BENCH_VERSION="${ETCD_VERSION}" docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" down -v --remove-orphans >/dev/null 2>&1 || true
}

cleanup() {
  compose_down
  rm -rf "${BUILD_SRC_DIR}"
  rm -f "${RESULTS_DIR}"/_tmp_"${ETCD_VERSION}"_*.json
}

if [[ "${PLOT_ONLY}" -eq 0 ]]; then
  trap cleanup EXIT

  if [[ ! -d "${ETCD_REPO}/.git" ]]; then
    echo "Error: local etcd git repository not found at ${ETCD_REPO}" >&2
    exit 1
  fi

  mkdir -p "${RESULTS_DIR}" "${BUILD_SRC_DIR}"
  rm -f "${RESULTS_DIR}"/_tmp_"${ETCD_VERSION}"_*.json

  echo "==> [1/4] Exporting clean source archive for etcd ${ETCD_VERSION} from ${ETCD_REPO}"
  git -C "${ETCD_REPO}" archive --format=tar -o "${BUILD_SRC_DIR}/etcd-src.tar" "${ETCD_VERSION}"

  echo "==> [2/4] Building linux/amd64 container images (etcd ${ETCD_VERSION} + Go bench-client)"
  docker build --platform linux/amd64 \
    -f "${SCRIPT_DIR}/Dockerfile.etcd" \
    -t "etcd-bench-node:${ETCD_VERSION}" \
    "${SCRIPT_DIR}"

  docker build --platform linux/amd64 \
    -f "${SCRIPT_DIR}/Dockerfile.client" \
    -t "etcd-bench-client:latest" \
    "${SCRIPT_DIR}"

  echo "==> [3/4] Phase A — Steady-State Concurrency Scaling (c in ${CONCURRENCIES[*]}, snapshot-count=100000)"
  PHASE_A_FILES=()
  for c in "${CONCURRENCIES[@]}"; do
    echo "    -> Starting fresh 3-node cluster with empty ext4 volumes for c=${c}..."
    compose_down
    ETCD_BENCH_VERSION="${ETCD_VERSION}" SNAPSHOT_COUNT=100000 \
      docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d etcd-1 etcd-2 etcd-3

    OUT_REL="_tmp_${ETCD_VERSION}_phase_a_c${c}.json"
    ETCD_BENCH_VERSION="${ETCD_VERSION}" SNAPSHOT_COUNT=100000 \
      docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" run --rm bench-client \
        --mode=concurrency \
        --concurrency="${c}" \
        --warmup=3s \
        --duration=15s \
        --key-space=1000 \
        --value-size=256 \
        --out="/results/${OUT_REL}"

    PHASE_A_FILES+=("${RESULTS_DIR}/${OUT_REL}")
    compose_down
  done

  echo "==> [4/4] Phase B — Snapshot & Log-Rewrite Compaction Stall (snapshot-count=10000, 20,000 writes)"
  compose_down
  ETCD_BENCH_VERSION="${ETCD_VERSION}" SNAPSHOT_COUNT=10000 \
    docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d etcd-1 etcd-2 etcd-3

  PHASE_B_REL="_tmp_${ETCD_VERSION}_phase_b.json"
  ETCD_BENCH_VERSION="${ETCD_VERSION}" SNAPSHOT_COUNT=10000 \
    docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" run --rm bench-client \
      --mode=compaction \
      --concurrency=64 \
      --total-writes=20000 \
      --rate-limit=1400 \
      --sample-interval=100ms \
      --key-space=1000 \
      --value-size=256 \
      --out="/results/${PHASE_B_REL}"

  compose_down

  "${PYTHON_BIN}" "${SCRIPT_DIR}/merge_results.py" \
    --version "${ETCD_VERSION}" \
    --phase-a "${PHASE_A_FILES[@]}" \
    --phase-b "${RESULTS_DIR}/${PHASE_B_REL}" \
    --out "${FINAL_JSON}"
fi

if [[ "${ETCD_VERSION}" == v0.4* ]]; then
  SCALING_PNG="${PART1_DIR}/v04_concurrency_scaling.png"
  COMPACTION_PNG="${PART1_DIR}/v04_compaction_stall.png"
else
  VER_SLUG="${ETCD_VERSION//./_}"
  SCALING_PNG="${RESULTS_DIR}/${VER_SLUG}_concurrency_scaling.png"
  COMPACTION_PNG="${RESULTS_DIR}/${VER_SLUG}_compaction_stall.png"
fi

echo "==> Rendering benchmark figures from ${FINAL_JSON}"
"${PYTHON_BIN}" "${SCRIPT_DIR}/plot_benchmarks.py" \
  --results "${FINAL_JSON}" \
  --out-scaling "${SCALING_PNG}" \
  --out-compaction "${COMPACTION_PNG}"

echo "==> Benchmark suite complete!"
echo "    Raw results : ${FINAL_JSON}"
echo "    Chart 1     : ${SCALING_PNG}"
echo "    Chart 2     : ${COMPACTION_PNG}"
