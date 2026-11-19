---
title: "The Evolution of etcd Storage (Part 4): Forking bbolt & Scaling to Large Clusters (v3.3 – v3.5)"
published: false
description: "TBD — Why CoreOS forked BoltDB into bbolt, fixing read/write stalls with ConcurrentReadTx, Raft Learners & Pre-Vote, and replacing the array freelist with map."
tags: etcd, bbolt, databases, performance
---

<!--
Placeholder for Part 4 of the etcd Storage Evolution series.
- Reference notes: ../etcd_storage_history.md (Phase 4: v3.3 – v3.5), ../bbolt_history.md
- Relevant local repos: ~/Documents/etcd (v3.3–v3.5 tags), ~/Documents/bolt, ~/Documents/bbolt, ~/Documents/lmdb
-->

## TBD

Outline and content to be developed after Part 3. Core topics:
- CNCF adoption & multi-thousand-node Kubernetes + CRD explosion
- `v3.3`: Why CoreOS forked `boltdb/bolt` → `coreos/bbolt` (`etcd-io/bbolt`)
- `v3.4`: Eliminating `LIST` vs. write stalls via `ConcurrentReadTx`, plus Raft Pre-Vote and Learner nodes
- `v3.5`: Ben Johnson's "toy-project" `array` freelist (`O(N)` stalls vs. LMDB's B+tree bucket) and switching the default to `map` freelist, plus `totalDBSize` vs. `totalDBSizeInUse` and manual `defrag`
- Bridge to Part 5: retiring the lingering `v2store` shadow and pushing modern `v3store` + `bbolt` efficiency further
