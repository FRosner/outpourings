---
title: "The Evolution of etcd Storage (Part 3): The v3 Rewrite & Entering BoltDB (v3.0 – v3.2)"
published: false
description: "TBD — Co-designing flat binary keys, MVCC revisions, Leases, and gRPC watches around an in-memory treeIndex and BoltDB's mmap-ed CoW B+tree."
tags: etcd, bbolt, databases, kubernetes
---

<!--
Placeholder for Part 3 of the etcd Storage Evolution series.
- Reference notes: ../etcd_storage_history.md (Phase 3: v3.0 – v3.2), ../bbolt_history.md
- Relevant local repos: ~/Documents/etcd (v3.0–v3.2 tags), ~/Documents/bolt, ~/Documents/lmdb, ~/Documents/btree, ~/Documents/kubernetes
-->

## TBD

Outline and content to be developed after Part 2. Core topics:
- Co-designing the `v3` API and storage layer around Kubernetes (`LIST`/`WATCH` → `resourceVersion`, flat sorted binary keys, MVCC revisions, atomic `Txn`, shared server-side Leases, gRPC multiplexed watch streams)
- Two-tier storage architecture: in-memory `treeIndex` (`google/btree`) + on-disk `backend` wrapping `boltdb/bolt` (`member/snap/db`)
- Why BoltDB (and its LMDB lineage): pure Go (zero `cgo`), ordered B+tree, off-heap `mmap` + OS page cache, CoW MVCC reads, two-phase meta-page commits without a second WAL
- Bridge to Part 4: how real-world multi-thousand-node Kubernetes clusters exposed bottlenecks in both `etcd`'s backend locking and BoltDB's internals
