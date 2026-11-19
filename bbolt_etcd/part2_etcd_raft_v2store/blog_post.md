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
- Replacing `goraft` with decoupled `etcd/raft` + segmented `wal` (`$seq-$index.wal`) + `snap`
- Retaining the in-memory `v2store` tree and v2 HTTP+JSON API
- Kubernetes v1.0 (July 2015) workload shift: Pods, Nodes, Endpoints, Events, continuous heartbeats, `LIST` + `WATCH` controllers
- The 4 failure modes of `v2store` under Kubernetes: Go heap/GC pauses, `O(N)` JSON snapshots, per-key TTL churn, fragile hanging-GET watches
- Bridge to Part 3: why fixing Raft wasn't enough and why `etcd v3` needed a brand-new disk-backed storage engine
