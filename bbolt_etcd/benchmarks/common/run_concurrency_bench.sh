#!/usr/bin/env bash
set -euo pipefail

# Shared steady-state concurrency benchmark runner for etcd clusters.
# Invoked by per-part wrapper scripts (e.g. benchmarks/part1_v04/run.sh, benchmarks/part2_v2/run.sh)
# so changes to the shared setup apply uniformly across parts while each part's results stay isolated.

COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERIES_DIR="$(cd "${COMMON_DIR}/../.." && pwd)"

if [[ -d "/Applications/Docker.app/Contents/Resources/bin" ]]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH}"
fi

ETCD_VERSION=""
RESULTS_DIR=""
ETCD_REPO="${ETCD_REPO:-/Users/frosner/Documents/etcd}"
PLOT_ONLY=0
COMPARE_WITH=""
CONCURRENCIES=(1 2 4 8 16 32 64 128 256)
SNAPSHOT_COUNT=2000000

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      ETCD_VERSION="$2"
      shift 2
      ;;
    --results-dir)
      RESULTS_DIR="$2"
      shift 2
      ;;
    --compare-with)
      COMPARE_WITH="$2"
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
      echo "Usage: $0 --version <tag> --results-dir <dir> [--compare-with <baseline.json>] [--etcd-repo /path/to/etcd] [--plot-only]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${ETCD_VERSION}" || -z "${RESULTS_DIR}" ]]; then
  echo "Error: --version and --results-dir are required." >&2
  exit 1
fi

mkdir -p "${RESULTS_DIR}"
RESULTS_DIR="$(cd "${RESULTS_DIR}" && pwd)"
FINAL_JSON="${RESULTS_DIR}/${ETCD_VERSION}.json"
BUILD_SRC_DIR="${COMMON_DIR}/.build_src"
COMPOSE_FILE="${COMMON_DIR}/docker-compose.yml"
COMPOSE_PROJECT="etcd_bench"

PYTHON_BIN="${SERIES_DIR}/part1_distributed_etc_goraft/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

compose_down() {
  RESULTS_DIR="${RESULTS_DIR}" ETCD_BENCH_VERSION="${ETCD_VERSION}" \
    docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" down -v --remove-orphans >/dev/null 2>&1 || true
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

  mkdir -p "${BUILD_SRC_DIR}"
  rm -f "${RESULTS_DIR}"/_tmp_"${ETCD_VERSION}"_*.json

  echo "==> [1/3] Exporting clean source archive for etcd ${ETCD_VERSION} from ${ETCD_REPO}"
  git -C "${ETCD_REPO}" archive --format=tar -o "${BUILD_SRC_DIR}/etcd-src.tar" "${ETCD_VERSION}"

  echo "==> [2/3] Building linux/amd64 container images (etcd ${ETCD_VERSION} + Go bench-client)"
  docker build --platform linux/amd64 \
    -f "${COMMON_DIR}/Dockerfile.etcd" \
    -t "etcd-bench-node:${ETCD_VERSION}" \
    "${COMMON_DIR}"

  docker build --platform linux/amd64 \
    -f "${COMMON_DIR}/Dockerfile.client" \
    -t "etcd-bench-client:latest" \
    "${COMMON_DIR}"

  PHASE_A_FILES=()
  echo "==> [3/3] Steady-State Concurrency Scaling (${ETCD_VERSION}, c in ${CONCURRENCIES[*]}, tmpfs, snapshot-count=${SNAPSHOT_COUNT})"
  echo "    -> Starting 3-node cluster once on fresh tmpfs volumes (constant peer heartbeat phase across sweep)..."
  compose_down
  RESULTS_DIR="${RESULTS_DIR}" ETCD_BENCH_VERSION="${ETCD_VERSION}" SNAPSHOT_COUNT="${SNAPSHOT_COUNT}" \
    docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" up -d etcd-1 etcd-2 etcd-3

  for c in "${CONCURRENCIES[@]}"; do
    echo "    -> Running concurrency c=${c}..."
    OUT_REL="_tmp_${ETCD_VERSION}_phase_a_c${c}.json"
    RESULTS_DIR="${RESULTS_DIR}" ETCD_BENCH_VERSION="${ETCD_VERSION}" SNAPSHOT_COUNT="${SNAPSHOT_COUNT}" \
      docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" run --rm bench-client \
        --mode=concurrency \
        --concurrency="${c}" \
        --warmup=3s \
        --duration=15s \
        --key-space=1000 \
        --value-size=256 \
        --out="/results/${OUT_REL}"

    PHASE_A_FILES+=("${RESULTS_DIR}/${OUT_REL}")
  done
  compose_down

  "${PYTHON_BIN}" "${COMMON_DIR}/merge_results.py" \
    --version "${ETCD_VERSION}" \
    --snapshot-count "${SNAPSHOT_COUNT}" \
    --phase-a "${PHASE_A_FILES[@]}" \
    --out "${FINAL_JSON}"
fi

VER_SLUG="${ETCD_VERSION//./_}"
THROUGHPUT_PNG="${RESULTS_DIR}/${VER_SLUG}_write_throughput.png"
LATENCY_PNG="${RESULTS_DIR}/${VER_SLUG}_write_latency.png"

echo "==> Rendering standalone benchmark figures from ${FINAL_JSON}"
"${PYTHON_BIN}" "${COMMON_DIR}/plot_benchmarks.py" \
  --results "${FINAL_JSON}" \
  --out-throughput "${THROUGHPUT_PNG}" \
  --out-latency "${LATENCY_PNG}"

if [[ -n "${COMPARE_WITH}" && -f "${COMPARE_WITH}" ]]; then
  BASE_VER="$("${PYTHON_BIN}" -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "${COMPARE_WITH}")"
  BASE_SLUG="${BASE_VER//./_}"
  CMP_THROUGHPUT_PNG="${RESULTS_DIR}/${BASE_SLUG}_vs_${VER_SLUG}_write_throughput.png"
  CMP_LATENCY_PNG="${RESULTS_DIR}/${BASE_SLUG}_vs_${VER_SLUG}_write_latency.png"
  echo "==> Rendering comparison overlay figures (${BASE_VER} vs. ${ETCD_VERSION})"
  "${PYTHON_BIN}" "${COMMON_DIR}/plot_benchmarks.py" \
    --results "${COMPARE_WITH}" "${FINAL_JSON}" \
    --out-throughput "${CMP_THROUGHPUT_PNG}" \
    --out-latency "${CMP_LATENCY_PNG}"
fi

echo "==> Benchmark complete!"
echo "    Raw results : ${FINAL_JSON}"
echo "    Throughput  : ${THROUGHPUT_PNG}"
echo "    Latency     : ${LATENCY_PNG}"
if [[ -n "${COMPARE_WITH}" && -f "${COMPARE_WITH}" ]]; then
  echo "    Comparison  : ${CMP_THROUGHPUT_PNG}"
  echo "    Comparison  : ${CMP_LATENCY_PNG}"
fi
