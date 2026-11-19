---
title: "The Evolution of etcd Storage (Part 5): Retiring v2store, Modern Efficiency & Life Beyond bbolt (v3.6 – v3.7)"
published: false
description: "TBD — Completing the v2store removal, bbolt v1.4/v1.5 and --keys-only optimizations, and why pluggable backends, LSM trees, and shims like kine keep coming up."
tags: etcd, bbolt, databases, kubernetes
---

<!--
Placeholder for Part 5 of the etcd Storage Evolution series (can be split into Part 5 + Part 6 later if it grows large).
- Reference notes: ../etcd_storage_history.md (Phase 5: v3.6 – v3.7 & Phase 6: Explored Alternatives & External Shims)
- Relevant local repos: ~/Documents/etcd (v3.6–v3.7 tags), ~/Documents/bbolt, ~/Documents/kine, ~/Documents/pebble, ~/Documents/badger
-->

## TBD

Outline and content to be developed after Part 4. Core topics:
- `v3.6`: Migrating cluster membership out of `v2store` into `v3store`, safe rolling downgrades, `bbolt v1.4`, ~50% memory reduction
- `v3.7`: Complete removal of `v2store`, `bbolt v1.5.1` (explicit DB size limit enforcement, `NoStatistics`), and `--keys-only` queries served straight from `treeIndex`
- Hard operational boundaries of `bbolt` (single-writer model, CoW write amplification, `mmap` ceilings, compaction/defrag)
- Explored alternatives: Pluggable backend meta-issue (`etcd#10321`), LSM-tree candidates (BadgerDB, Pebble, RocksDB), and API-compatible shims (`k3s-io/kine` over SQLite/Postgres/MySQL)
- Series wrap-up: core lessons on how workloads continuously reshape storage engines
