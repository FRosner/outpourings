# Shared `etcd` Write-Path Benchmark Suite (`benchmarks/`)

Reusable Docker Compose benchmark harness shared across parts of the `etcd` storage evolution series.

## Structure

- `common/` — Shared Dockerfiles, Docker Compose topology, Go load generator (`client/`), result merger, plotting script (`plot_benchmarks.py`), and core runner (`run_concurrency_bench.sh`). Editing anything in `common/` updates the setup consistently for every part that uses it.
- `part1_v04/` — Isolated Part 1 runner (`./benchmarks/part1_v04/run.sh`) targeting `etcd v0.4.9`, writing exclusively to `part1_v04/results/`.
- `part2_v2/` — Isolated Part 2 runner (`./benchmarks/part2_v2/run.sh`) targeting `etcd v2.3.8`, writing exclusively to `part2_v2/results/` (plus read-only comparison overlays against `part1_v04/results/v0.4.9.json` when present).

Re-running any part's `run.sh` never regenerates another part's results and never overwrites PNGs embedded inside `part*/blog_post.md` — copy generated PNGs into the corresponding `part*/` folder explicitly when updating a post.

## Architecture & Determinism Rules

- **4-container `linux/amd64` topology** on an isolated Docker bridge network:
  - `etcd-1`, `etcd-2`, `etcd-3`: pinned to `1` dedicated CPU core each (`cpuset` + `GOMAXPROCS=1`) and `1 GiB` RAM, mounting fresh **`tmpfs` volumes** (`768 MiB` each) at `/var/lib/etcd` so the single-host benchmark cleanly isolates Raft consensus, replication batching, locking, and log-syscall overhead from macOS Docker Desktop's shared virtual-disk `fsync` queue. The 3-node cluster stays up across the concurrency sweep so peer heartbeat phase stays constant across all `c` values.
  - `bench-client`: pinned to `2` dedicated CPU cores (`cpuset` + `GOMAXPROCS=2`) and `1 GiB` RAM, discovering the active Raft leader via `/v2/stats/leader` and sending `PUT /v2/keys/bench/key-<i % 1000>` (`256 B` deterministic payloads) directly to the leader's `:4001` endpoint over persistent HTTP `keep-alive` connections (`MaxIdleConnsPerHost: 512`) across `c ∈ {1, 2, 4, 8, 16, 32, 64, 128, 256}`.
- **Zero dependency drift:** Exports source from the local `etcd` git clone via `git archive <version>` and builds inside a pinned Go container using the tag's vendored `./build` script.

## Usage

Run Part 1 (`etcd v0.4.9`) or Part 2 (`etcd v2.3.8`) independently:

```bash
./benchmarks/part1_v04/run.sh
./benchmarks/part2_v2/run.sh
```

Re-render charts from existing JSON results without running containers:

```bash
./benchmarks/part1_v04/run.sh --plot-only
./benchmarks/part2_v2/run.sh --plot-only
```
