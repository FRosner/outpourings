# `etcd` Storage Evolution Blog Series — Agent Context

This directory contains a 5-part technical blog series tracing how `etcd`'s storage engine evolved from 2013 to 2026 (`v0.1` → `v3.7`).

## Series Framing & Style

* **Audience:** Systems and database enthusiasts interested in the broader lesson of how changing workloads reshape storage engines.
* **Tone & Structure:** Deeply technical, structured, and educative. Each post must be **self-explanatory** while **bridging cleanly into the next part**.
* **Supporting Material:** Include architecture explanations, concrete API/coordination examples, source-code archaeology grounded in the reference repositories below, reproducible mini-experiments/benchmarks, and Python-generated animations.

## Directory Layout & Shared Notes

* **Shared research notes:**
  * `etcd_storage_history.md` — Chronological breakdown of Phases 1–6 (`v0.1`–`v3.7` + alternatives)
  * `coreos_history.md` — CoreOS Container Linux, `locksmith`, `fleet`, and Kubernetes backstory
  * `bbolt_history.md` — LMDB → BoltDB → `bbolt` history and primary quotes
* **Series parts:**
  1. `part1_distributed_etc_goraft/blog_post.md` — Era 1: Distributed `/etc` & `goraft` (`v0.1 – v0.4.x`)
  2. `part2_etcd_raft_v2store/blog_post.md` — Era 2: `etcd/raft` rewrite & hitting the Kubernetes wall (`v2.0 – v2.3`)
  3. `part3_v3_mvcc_boltdb/blog_post.md` — Era 3: `v3` MVCC rewrite & entering BoltDB (`v3.0 – v3.2`)
  4. `part4_bbolt_scaling/blog_post.md` — Era 4: Forking `bbolt`, `ConcurrentReadTx`, and `map` freelist (`v3.3 – v3.5`)
  5. `part5_modern_etcd_and_alternatives/blog_post.md` — Era 5: Retiring `v2store`, modern efficiency (`v3.6 – v3.7`), and alternatives (`etcd#10321`, LSMs, `kine`)

## Local Reference Repositories (Source-Code Archaeology)

All primary and comparison repositories are cloned locally under `/Users/frosner/Documents/`:

| Local Path | Upstream Repo | Purpose & Notes | Relevant Parts |
| :--- | :--- | :--- | :--- |
| `/Users/frosner/Documents/etcd` | `etcd-io/etcd` | Primary `etcd` source across all eras (`v0.1`–`v3.7` via git tags: `store`/`v2store`, `EventHistory`, JSON snapshots, `server/`, `etcd/raft`, `wal`, `snap`, `mvcc`, `treeIndex`, `backend`). Note: `v0.4.x` also vendors `goraft` under `third_party/github.com/goraft/raft`. | All Parts |
| `/Users/frosner/Documents/goraft` | `goraft/raft` | Ben Johnson's original Go Raft library used by `etcd v0.1–v0.4` (coupling of transport, disk I/O, timers, state machine, and locking). | Part 1 |
| `/Users/frosner/Documents/locksmith` | `coreos/locksmith` | CoreOS distributed reboot semaphore using `etcd` `CompareAndSwap` (`prevIndex`) **without** TTL or watches (retried via exponential backoff so a rebooting host keeps the lock while powered off). | Part 1 |
| `/Users/frosner/Documents/fleet` | `coreos/fleet` | CoreOS distributed `systemd` scheduler storing unit state in early `etcd`. | Part 1 |
| `/Users/frosner/Documents/raft` | `etcd-io/raft` | Modern decoupled `etcd/raft` state-machine library (contrasted against `goraft`). | Parts 2+ |
| `/Users/frosner/Documents/bolt` | `boltdb/bolt` | Original archived BoltDB by Ben Johnson (pre-fork code and `array` freelist). | Parts 3–4 |
| `/Users/frosner/Documents/bbolt` | `etcd-io/bbolt` | Active CoreOS / `etcd` fork (`map` freelist, `v1.3` → `v1.4` → `v1.5.1`, `NoStatistics`, DB size limits). | Parts 4–5 |
| `/Users/frosner/Documents/btree` | `google/btree` | In-memory B-tree backing `etcd v3`'s `treeIndex`. | Parts 3–5 |
| `/Users/frosner/Documents/lmdb` | `LMDB/lmdb` | C database that inspired BoltDB (useful for contrasting LMDB's B+tree freelist bucket vs. BoltDB's `array` freelist). | Parts 3–4 |
| `/Users/frosner/Documents/kubernetes` | `kubernetes/kubernetes` | Blobless clone (`--filter=blob:none`) for inspecting `kube-apiserver`'s `etcd2`/`etcd3` storage drivers, `resourceVersion`, and `cacher`. | Parts 2–3 |
| `/Users/frosner/Documents/kine` | `k3s-io/kine` | `etcd v3` gRPC shim backed by SQLite/PostgreSQL/MySQL. | Part 5 |
| `/Users/frosner/Documents/pebble` | `cockroachdb/pebble` | Pure-Go LSM-tree storage engine evaluated in pluggable-backend discussions (`etcd#10321`). | Part 5 |
| `/Users/frosner/Documents/badger` | `dgraph-io/badger` | Pure-Go LSM-tree storage engine evaluated in pluggable-backend discussions (`etcd#10321`). | Part 5 |

*Tip:* Avoid leaving checkouts dirty in the reference repos—prefer `git -C <repo> show <tag>:<path>` or temporary worktrees when inspecting historical tags in `/Users/frosner/Documents/etcd`.

## Animations & Reproducible Experiments

* **Animations:** Place Python animation packages (`pyproject.toml`, `animations/common.py`, `animations/render.py`, and per-diagram modules) and rendered `.webp` assets (embedded directly in `blog_post.md`) inside the corresponding `part*/` folder. Use `matplotlib`, `numpy`, `pillow`, and `imageio`/`imageio-ffmpeg` — see `part1_distributed_etc_goraft/pyproject.toml` and `part1_distributed_etc_goraft/animations/` for the established modular style and CLI runner (derived from `../tcp_buffers/`).
* **Benchmarks / Demos:** Shared cross-part benchmark harnesses live under `benchmarks/` (`benchmarks/common/` for the shared setup & plotting, and `benchmarks/part*/run.sh` for isolated per-part execution and results). Copy final chart PNGs explicitly into the corresponding `part*/` folder so re-running benchmarks never silently mutates published posts.
