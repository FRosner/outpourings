---
title: "The Evolution of etcd Storage (Part 1): When a Distributed /etc Fit in RAM (v0.1 – v0.4)"
published: false
description: "TBD — How CoreOS's small-config workload shaped etcd's earliest storage engine: an in-memory directory tree, goraft consensus, JSON snapshots, and the cracks that led to etcd v2."
tags: etcd, distributed-systems, databases, storage
---

<!--
Series & Authoring Notes (remove before publishing):
- Audience: Systems / database enthusiasts interested in the broader lesson of how changing workloads reshape storage engines.
- Tone: Deeply technical, structured, and educative (self-contained post that bridges naturally into Part 2).
- Shared research notes:
  - ../etcd_storage_history.md (Phase 1: v0.1 – v0.4.x)
  - ../coreos_history.md (Motivating slice: Container Linux A/B updates, locksmith, fleet)
- Local source repositories for code archaeology:
  - ~/Documents/etcd (inspect v0.4.x git tags for `store/`, `server/`, `EventHistory`, JSON snapshots)
  - ~/Documents/goraft (`goraft/raft` — coupling of transport, disk I/O, timers, state machine, locking)
  - ~/Documents/locksmith (`coreos/locksmith` — concrete reboot semaphore example using CAS + TTL)
  - ~/Documents/fleet (`coreos/fleet` — optional secondary CoreOS example)
- Animations:
  - Use Python (`matplotlib`, `numpy`, `pillow`, `imageio`, `imageio-ffmpeg`) to render `.webp` animations embedded directly in this post.
  - See ../../tcp_buffers/pyproject.toml and ../../tcp_buffers/animate_tcp_buffers.py for the established project style and setup.
-->

## Motivation & Series Roadmap

TBD — Hook for systems and database enthusiasts: storage engines are not designed in a vacuum; they are mirrors of the workloads they serve. Today `etcd` is best known as Kubernetes's disk-backed `bbolt` control-plane store, yet it began in 2013 as something radically simpler—an in-memory hierarchical directory tree serialized to JSON.

Introduce the 5-part series roadmap (with Part 1 fully self-contained):

1. **Part 1 (this post):** The Distributed `/etc` & `goraft` Era (`v0.1 – v0.4.x`, 2013–2014)
2. **Part 2:** The `etcd/raft` Rewrite & Hitting the Kubernetes Wall (`v2.0 – v2.3`, 2015)
3. **Part 3:** The `v3` Rewrite & Entering BoltDB (`v3.0 – v3.2`, 2016–2017)
4. **Part 4:** Forking `bbolt` & Scaling to Large Clusters (`v3.3 – v3.5`, 2018–2021)
5. **Part 5:** Retiring `v2store`, Modern Efficiency & Life Beyond `bbolt` (`v3.6 – v3.7` & Alternatives, 2025–2026)

## The 2013 Workload: Why CoreOS Needed a Distributed `/etc`

TBD — Motivating slice of CoreOS history (from `../coreos_history.md`):
- CoreOS Container Linux ran minimal container hosts with immutable dual-partition (A/B) automatic OS updates.
- Once servers automatically reboot themselves, you immediately need distributed coordination (`locksmith` sequential reboot semaphore, `fleet` unit placement, `flannel` subnet allocation, `SkyDNS` service discovery) without hauling a JVM and Apache ZooKeeper onto minimal Linux hosts.
- The mental model: Unix `/etc` + `d` (distributed/daemon) = small configuration trees (MBs, not GBs), low write churn, few concurrent watchers.
- **Storage design lesson:** When your entire dataset easily fits in RAM and looks like a filesystem, an in-memory tree + append-only log + periodic snapshots is a pragmatic, rational choice.

## The `v0.x` Data Model & Coordination Primitives

TBD — Explain the hierarchical directory/key API over HTTP+JSON and the three primitives that turned `/etc` into a coordination service:
- **Atomic Compare-and-Swap (`prevValue` / `prevIndex`)**
- **Per-key TTLs** (ephemeral registrations and heartbeats)
- **Long-polling HTTP watches** (`?wait=true&waitIndex=...`)

### Concrete Walkthrough: A `locksmith`-Style Distributed Reboot Lock

TBD — Grounded in `~/Documents/locksmith`, walk through concrete HTTP+JSON (`curl`) interactions showing how a cluster host acquires a reboot semaphore with CAS + TTL, renews/releases it, and how waiting hosts watch for release. Highlight why this UX felt great for small config coordination while implicitly assuming low write churn.

## Under the Hood: `etcd v0.4` & `goraft` (Source-Code Archaeology)

TBD — Trace the end-to-end write/read/watch lifecycle: Client HTTP → `goraft` Leader → Raft log append & quorum replication → apply to in-memory `store` → wake watchers → periodic snapshot.

### The In-Memory `store` Tree

TBD — Inspect actual Go structs in `~/Documents/etcd` at a `v0.4.x` tag:
- Hierarchical `node` / directory maps, leaf values, global `currentIndex`, TTL expiration tracking (`ttlKeyHeap` / expiration handling), and locking around reads/writes.

### Watch History (`EventHistory` Ring Buffer)

TBD — Inspect how `EventHistory` maintains a fixed-size in-memory sliding window of recent events so long-polling watchers can catch up from a given `waitIndex`—and what happens when write bursts overflow that window.

TBD — **Animation 1 (Python / `matplotlib` → `.webp`):** *`EventHistory` Ring Buffer & Long-Poll Watches* — visualize writes advancing `currentIndex` and populating the fixed-size ring buffer, a watcher catching up via `waitIndex`, and a slow watcher getting evicted under a write burst.

### Durability & Log Compaction: Raft Command Log + Full-Tree JSON Snapshots

TBD — Explain why an append-only Raft command log cannot grow unboundedly, and inspect `store.Save()` / `SaveNoCopy()` in `etcd v0.4` to show how snapshotting walked the entire Go tree, serialized it to JSON on disk, and truncated the Raft log.

TBD — **Animation 2 (Python / `matplotlib` → `.webp`):** *The Write, Raft Log & Full-Tree JSON Snapshot Lifecycle* — visualize mutations appending to the Raft log and updating the in-memory tree, followed by a snapshot cycle traversing all `N` nodes to serialize JSON and compact the log.

## Mini-Experiment: Measuring the Cost of an In-Memory JSON-Snapshotted Tree

TBD — Reproducible Go benchmark (either exercising historical `etcd v0.4` `store` code directly or a faithful standalone Go harness mirroring its exact structs) scaling from e.g. 1k → 10k → 100k keys to measure:
- **Memory overhead:** Go heap footprint of pointer-heavy directory/node structs vs. raw key/value bytes.
- **Snapshot cost:** Latency, CPU, and allocation spikes of `O(N)` JSON serialization as tree size grows.

Connect the measurements back to fundamental storage trade-offs: blazing-fast point reads and simple crash recovery at 2013 config scale, with steep scaling cliffs waiting once datasets grow.

## Why It Fit 2013—and Where the First Cracks Appeared

TBD — Balanced retrospective grounded in `~/Documents/goraft` and `~/Documents/etcd` (`v0.4.x`):
- **What worked brilliantly:** Single static Go binary, zero external dependencies, intuitive filesystem mental model, fast RAM reads.
- **What broke (`goraft` coupling):** Inspect how `goraft` tightly coupled network transport, disk persistence, timers, and state-machine application behind coarse locking—producing lock contention, brittle network-partition behavior, and hard-to-test failure modes as clusters matured.
- **Latent storage limits:** Full-tree JSON snapshots, Go heap pointer trees, and fixed watch windows were fine at CoreOS config scale, but already ticking time bombs for larger workloads.

## Looking Ahead to Part 2

TBD — Smooth handoff to **Part 2 (`v2.0 – v2.3`)**:
To make `etcd` production-grade, CoreOS replaced `goraft` with a clean-sheet, decoupled state-machine Raft implementation (`etcd/raft`) backed by segmented `wal` and `snap` files. That solved consensus stability—just in time for **Kubernetes v1.0** to adopt `etcd` and push the still-in-memory tree past its breaking point.
