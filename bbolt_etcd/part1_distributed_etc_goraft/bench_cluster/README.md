# Reproducible `etcd` Write-Path Benchmark Suite (`bench_cluster/`)

This folder contains the single-host Docker Compose benchmark harness used in **Part 1** (`etcd v0.4.9`) and **Part 2** (`etcd v2.3.8`) of the `etcd` storage evolution series.

## Architecture & Determinism Rules

- **4-container `linux/amd64` topology** on an isolated Docker bridge network:
  - `etcd-1`, `etcd-2`, `etcd-3`: `1.0` CPU, `512 MiB` RAM each, mounting fresh **Docker named volumes** (`etcd1-data`, `etcd2-data`, `etcd3-data`) at `/var/lib/etcd` so `write()` and `fsync()` hit native Linux `ext4` inside the Docker VM rather than macOS `VirtioFS`.
  - `bench-client`: `2.0` CPUs, `1 GiB` RAM Go load generator that discovers the active Raft leader via `/v2/stats/leader` and sends `PUT /v2/keys/bench/key-<i % 1000>` (`256 B` deterministic payloads) directly to the leader's `:4001` endpoint over persistent HTTP `keep-alive` connections (`MaxIdleConnsPerHost: 512`).
- **Zero dependency drift:** Exports source from the local `etcd` git clone via `git archive <version>` and builds inside a pinned Go container using the tag's vendored `./build` script.

## Usage

Run both experiments end-to-end (`Phase A`: steady-state concurrency sweep `c ∈ {1, 4, 16, 64, 256}`; `Phase B`: 20,000-write snapshot & log-compaction trace) and render both PNG charts:

```bash
./bench_cluster/run_benchmark.sh
```

By default, `--version v0.4.9` writes raw measurements to `bench_cluster/results/v0.4.9.json` and renders:
- `../v04_concurrency_scaling.png`
- `../v04_compaction_stall.png`

To re-render charts from existing JSON results without re-running containers:

```bash
./bench_cluster/run_benchmark.sh --plot-only
```

To run the exact same harness against `etcd v2.3.8` (used in Part 2):

```bash
./bench_cluster/run_benchmark.sh --version v2.3.8
```
