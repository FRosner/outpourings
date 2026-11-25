# Reproducible `etcd` Write-Path Benchmark Suite (`bench_cluster/`)

This folder contains the single-host Docker Compose benchmark harness used in **Part 1** (`etcd v0.4.9`) and **Part 2** (`etcd v2.3.8`) of the `etcd` storage evolution series.

## Architecture & Determinism Rules

- **4-container `linux/amd64` topology** on an isolated Docker bridge network:
  - `etcd-1`, `etcd-2`, `etcd-3`: pinned to `1` dedicated CPU core each (`cpuset` + `GOMAXPROCS=1`) and `512 MiB` RAM, mounting fresh **Docker named volumes** (`etcd1-data`, `etcd2-data`, `etcd3-data`) at `/var/lib/etcd` so `write()` and `fsync()` hit native Linux `ext4` inside the Docker VM rather than macOS `VirtioFS`.
  - `bench-client`: pinned to `2` dedicated CPU cores (`cpuset` + `GOMAXPROCS=2`) and `1 GiB` RAM, discovering the active Raft leader via `/v2/stats/leader` and sending `PUT /v2/keys/bench/key-<i % 1000>` (`256 B` deterministic payloads) directly to the leader's `:4001` endpoint over persistent HTTP `keep-alive` connections (`MaxIdleConnsPerHost: 512`).
- **Zero dependency drift:** Exports source from the local `etcd` git clone via `git archive <version>` and builds inside a pinned Go container using the tag's vendored `./build` script.

## Usage

Run the steady-state concurrency sweep (`c ∈ {1, 4, 16, 64, 256}`) and render separate throughput and latency PNG charts:

```bash
./bench_cluster/run_benchmark.sh
```

By default, `--version v0.4.9` writes raw measurements and charts inside `bench_cluster/results/` so re-running the harness never overwrites the published blog post figures:
- `bench_cluster/results/v0.4.9.json`
- `bench_cluster/results/v0_4_9_write_throughput.png`
- `bench_cluster/results/v0_4_9_write_latency.png`

To update the figures embedded in `../blog_post.md`, copy the generated PNGs explicitly to `../v04_write_throughput.png` and `../v04_write_latency.png`.

To re-render charts from existing JSON results without re-running containers:

```bash
./bench_cluster/run_benchmark.sh --plot-only
```

To run the exact same harness against `etcd v2.3.8` (used in Part 2):

```bash
./bench_cluster/run_benchmark.sh --version v2.3.8
```
