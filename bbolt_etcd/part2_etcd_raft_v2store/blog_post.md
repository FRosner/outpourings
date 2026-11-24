---
title: "The Evolution of etcd Storage (Part 2): The etcd/raft Rewrite & Hitting the Kubernetes Wall (v2.0 – v2.3)"
published: false
description: "TBD — Decoupling consensus with etcd/raft, segmented WALs and snapshots, and why Kubernetes v1.0 workloads broke the in-memory v2store."
tags: etcd, distributed-systems, databases, kubernetes
---

<!--
Placeholder for Part 2 of the etcd Storage Evolution series.
- Reference notes: ../etcd_storage_history.md (Phase 2: v2.0 – v2.3, Jan 2015)
- Relevant local repos: ~/Documents/etcd (v2.0–v2.3 tags), ~/Documents/raft, ~/Documents/kubernetes
-->

## TBD

Outline and content to be developed after Part 1. Core topics:
- Replacing `goraft` with decoupled `etcd/raft` (`Ready()` batching) + segmented, CRC-chained `wal` (`$seq-$index.wal`, 64 MB preallocation + `fdatasync` in v2.2) + `snap` + streaming `rafthttp`
- **Benchmark follow-ups from Part 1 (two separate charts via `../part1_distributed_etc_goraft/bench_cluster/`):** Re-run the exact 3-node Docker `/v2/keys` benchmark against `etcd v2` (`v2.3.8`) and place each comparison chart alongside the `v2` mechanism that solved it: (1) steady-state concurrency scaling (`v0.4.9` vs. `v2` throughput & `p50`/`p99` latency across `c = 1..256`, showing event-driven `rafthttp` + `Ready()` WAL batching eliminating the 50 ms polling floor), and (2) crossing the `10,000`-commit snapshot boundary (`v0.4.9` vs. `v2`, showing segmented `$seq-$index.wal` rotation vs. monolithic `log.new` rewrite)
- Retaining the in-memory `v2store` tree (`Root *node`, `worldLock`, `Root.Clone()`, `json.Marshal`, 1,000-slot `EventHistory`) and v2 HTTP+JSON API
- Kubernetes v1.0 (July 2015) workload shift: Pods, Nodes, Endpoints, Events, continuous heartbeats, `LIST` + `WATCH` controllers
- Drawbacks leading to `v3` (split into Architectural vs. Performance subsections):
  - Architectural: v2 hierarchical directory semantics vs. flat range queries, single-key CAS vs. multi-key `Txn`, fragile HTTP hanging-GET watches + 1,000-event ring buffer without deep revision history, per-key TTL coupling
  - Performance (**with reproducible benchmark leading into Part 3**): `1,000 → 10,000 → 100,000` key `v2store` scaling benchmark (`HeapAlloc`/`HeapObjects` & GC pause cost, `worldLock` `Root.Clone()` pause, `O(N)` JSON snapshot latency/size, and per-key TTL write amplification)—designed so Part 3 (`mvcc` + `BoltDB`) reuses the same setup to show the improvement
- Bridge to Part 3: why `etcd v3` needed a brand-new disk-backed MVCC storage engine (without spoiling BoltDB internals)
