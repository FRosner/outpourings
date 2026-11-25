#!/usr/bin/env sh
set -eu

NODE_NAME="${NODE_NAME:?NODE_NAME must be set}"
ETCD_BENCH_VERSION="${ETCD_BENCH_VERSION:-v0.4.9}"
SNAPSHOT_COUNT="${SNAPSHOT_COUNT:-10000}"
DATA_DIR="/var/lib/etcd"

case "${ETCD_BENCH_VERSION}" in
  v0.4*)
    HEARTBEAT_INTERVAL="${HEARTBEAT_INTERVAL:-50}"
    ELECTION_TIMEOUT="${ELECTION_TIMEOUT:-200}"

    if [ "${NODE_NAME}" = "etcd-1" ]; then
      exec /usr/local/bin/etcd \
        -name="${NODE_NAME}" \
        -data-dir="${DATA_DIR}" \
        -addr="${NODE_NAME}:4001" \
        -bind-addr="0.0.0.0:4001" \
        -peer-addr="${NODE_NAME}:7001" \
        -peer-bind-addr="0.0.0.0:7001" \
        -peer-heartbeat-interval="${HEARTBEAT_INTERVAL}" \
        -peer-election-timeout="${ELECTION_TIMEOUT}" \
        -snapshot=true \
        -snapshot-count="${SNAPSHOT_COUNT}"
    else
      # Wait for seed node etcd-1 to accept HTTP connections before joining.
      tries=0
      while ! curl -sf "http://etcd-1:4001/version" >/dev/null 2>&1; do
        tries=$((tries + 1))
        if [ "${tries}" -ge 150 ]; then
          echo "Timed out waiting for seed node etcd-1:4001" >&2
          exit 1
        fi
        sleep 0.1
      done
      # Slight stagger for etcd-3 so join commands serialize cleanly on etcd-1.
      if [ "${NODE_NAME}" = "etcd-3" ]; then
        sleep 0.3
      fi
      exec /usr/local/bin/etcd \
        -name="${NODE_NAME}" \
        -data-dir="${DATA_DIR}" \
        -addr="${NODE_NAME}:4001" \
        -bind-addr="0.0.0.0:4001" \
        -peer-addr="${NODE_NAME}:7001" \
        -peer-bind-addr="0.0.0.0:7001" \
        -peers="etcd-1:7001" \
        -max-retry-attempts=30 \
        -retry-interval=0.2 \
        -peer-heartbeat-interval="${HEARTBEAT_INTERVAL}" \
        -peer-election-timeout="${ELECTION_TIMEOUT}" \
        -snapshot=true \
        -snapshot-count="${SNAPSHOT_COUNT}"
    fi
    ;;

  v2.*)
    HEARTBEAT_INTERVAL="${HEARTBEAT_INTERVAL:-100}"
    ELECTION_TIMEOUT="${ELECTION_TIMEOUT:-1000}"
    exec /usr/local/bin/etcd \
      -name "${NODE_NAME}" \
      -data-dir "${DATA_DIR}" \
      -listen-client-urls "http://0.0.0.0:4001" \
      -advertise-client-urls "http://${NODE_NAME}:4001" \
      -listen-peer-urls "http://0.0.0.0:7001" \
      -initial-advertise-peer-urls "http://${NODE_NAME}:7001" \
      -initial-cluster "etcd-1=http://etcd-1:7001,etcd-2=http://etcd-2:7001,etcd-3=http://etcd-3:7001" \
      -initial-cluster-token "etcd-bench-cluster" \
      -initial-cluster-state "new" \
      -heartbeat-interval "${HEARTBEAT_INTERVAL}" \
      -election-timeout "${ELECTION_TIMEOUT}" \
      -snapshot-count "${SNAPSHOT_COUNT}"
    ;;

  *)
    echo "Unsupported ETCD_BENCH_VERSION: ${ETCD_BENCH_VERSION}" >&2
    exit 1
    ;;
esac
