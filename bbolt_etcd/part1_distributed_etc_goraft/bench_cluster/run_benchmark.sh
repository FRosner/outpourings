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
  ETCD_BENCH_VERSION="${ETCD_VERSION}" docker compose -p "${COMPOSE_PROJECT}" \
    -f "${COMPOSE_FILE}" down -v --remove-orphans >/dev/null 2>&1 || true
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

  # Pin each container to dedicated CPU cores to avoid Linux CFS 100ms quota throttling freezes.
  NCPU="$(docker info --format '{{.NCPU}}' 2>/dev/null || echo 4)"
  if [[ "${NCPU}" -ge 5 ]]; then
    export CPUSET_ETCD1="0"
    export CPUSET_ETCD2="1"
    export CPUSET_ETCD3="2"
    export CPUSET_CLIENT="3,4"
  elif [[ "${NCPU}" -ge 4 ]]; then
    export CPUSET_ETCD1="0"
    export CPUSET_ETCD2="1"
    export CPUSET_ETCD3="2"
    export CPUSET_CLIENT="3"
  else
    export CPUSET_ETCD1="0"
    export CPUSET_ETCD2="0"
    export CPUSET_ETCD3="0"
    export CPUSET_CLIENT="0"
  fi
  echo "==> Docker VM CPUs=${NCPU} -> pinning etcd={${CPUSET_ETCD1},${CPUSET_ETCD2},${CPUSET_ETCD3}}, bench-client={${CPUSET_CLIENT}}"

  mkdir -p "${RESULTS_DIR}" "${BUILD_SRC_DIR}"
  rm -f "${RESULTS_DIR}"/_tmp_"${ETCD_VERSION}"_*.json

  echo "==> [1/3] Exporting clean source archive for etcd ${ETCD_VERSION} from ${ETCD_REPO}"
  git -C "${ETCD_REPO}" archive --format=tar -o "${BUILD_SRC_DIR}/etcd-src.tar" "${ETCD_VERSION}"

  echo "==> [2/3] Building linux/amd64 container images (etcd ${ETCD_VERSION} + Go bench-client)"
  docker build --platform linux/amd64 \
    -f "${SCRIPT_DIR}/Dockerfile.etcd" \
    -t "etcd-bench-node:${ETCD_VERSION}" \
    "${SCRIPT_DIR}"

  docker build --platform linux/amd64 \
    -f "${SCRIPT_DIR}/Dockerfile.client" \
    -t "etcd-bench-client:latest" \
    "${SCRIPT_DIR}"

  PHASE_A_FILES=()
  echo "==> [3/3] Steady-State Concurrency Scaling (c in ${CONCURRENCIES[*]}, snapshot-count=100000)"
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

  "${PYTHON_BIN}" "${SCRIPT_DIR}/merge_results.py" \
    --version "${ETCD_VERSION}" \
    --phase-a "${PHASE_A_FILES[@]}" \
    --out "${FINAL_JSON}"
fi

VER_SLUG="${ETCD_VERSION//./_}"
THROUGHPUT_PNG="${RESULTS_DIR}/${VER_SLUG}_write_throughput.png"
LATENCY_PNG="${RESULTS_DIR}/${VER_SLUG}_write_latency.png"

echo "==> Rendering benchmark figures from ${FINAL_JSON}"
"${PYTHON_BIN}" "${SCRIPT_DIR}/plot_benchmarks.py" \
  --results "${FINAL_JSON}" \
  --out-throughput "${THROUGHPUT_PNG}" \
  --out-latency "${LATENCY_PNG}"

echo "==> Benchmark suite complete!"
echo "    Raw results : ${FINAL_JSON}"
echo "    Chart 1     : ${THROUGHPUT_PNG}"
echo "    Chart 2     : ${LATENCY_PNG}"
