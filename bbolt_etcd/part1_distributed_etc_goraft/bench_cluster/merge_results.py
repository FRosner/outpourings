#!/usr/bin/env python3
"""Combine per-concurrency benchmark outputs into a single structured results/<version>.json file."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge steady-state concurrency benchmark outputs.")
    parser.add_argument("--version", required=True, help="etcd version tag, e.g. v0.4.9")
    parser.add_argument("--phase-a", nargs="+", required=True, help="Paths to concurrency JSON files")
    parser.add_argument("--out", required=True, help="Destination combined JSON path")
    args = parser.parse_args()

    phase_a_runs = []
    for p in args.phase_a:
        with open(p, "r", encoding="utf-8") as fh:
            phase_a_runs.append(json.load(fh))
    phase_a_runs.sort(key=lambda r: r["concurrency"])

    combined = {
        "version": args.version,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {
            "topology": "3x etcd nodes + 1x bench-client on isolated Docker bridge network",
            "container_platform": "linux/amd64",
            "etcd_resources": {
                "cpuset": "1 dedicated core per node (GOMAXPROCS=1)",
                "mem_limit": "512m",
                "storage": "Docker named volume (Linux ext4)",
            },
            "client_resources": {"cpuset": "2 dedicated cores (GOMAXPROCS=2)", "mem_limit": "1g"},
            "host_arch": platform.machine(),
            "workload": {
                "endpoint": "PUT /v2/keys/bench/key-<i % 1000> (direct to Raft leader, HTTP keep-alive)",
                "key_space": 1000,
                "value_bytes": 256,
            },
        },
        "experiment1_concurrency_scaling": {
            "snapshot_count": 100000,
            "warmup_seconds": phase_a_runs[0]["warmup_s"] if phase_a_runs else 3.0,
            "measurement_seconds": phase_a_runs[0]["duration_s"] if phase_a_runs else 15.0,
            "runs": phase_a_runs,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, indent=2)
    print(f"[merge] Wrote combined results to {out_path}")


if __name__ == "__main__":
    main()
