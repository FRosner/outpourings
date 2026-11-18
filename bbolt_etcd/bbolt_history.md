# Historical Context: bbolt & etcd Storage

Research notes and primary references tracing how **LMDB** inspired **BoltDB**, how **BoltDB** became **bbolt**, and why **etcd** adopted it for its v3 storage engine.

---

## 1. Timeline Overview

* **Late 2013 (~Dec 20, 2013):** Ben Johnson (`benbjohnson`) creates **Bolt** ([`boltdb/bolt`](https://github.com/boltdb/bolt)) as a pure-Go port/exploration of Howard Chu's **LMDB** (Lightning Memory-Mapped Database) to understand its copy-on-write B+tree internals.
* **~2014 (Shopify Merchant Analytics):** At Shopify, Ben Johnson's team initially uses [`szferi/gomdb`](https://github.com/szferi/gomdb) (a cgo wrapper around LMDB) for Merchant Analytics, runs into months of unresolved issues and poor Go `pprof` visibility across the C boundary, and swaps it out for Bolt.
* **July 7, 2014:** Nate Finch publishes [Intro to BoltDB: Painless Performant Persistence](https://npf.io/2014/07/intro-to-boltdb-painless-performant-persistence/), helping popularize BoltDB in the Go ecosystem (later linked in Bolt/bbolt READMEs).
* **June 30, 2016 (`etcd` 3.0):** CoreOS announces **etcd 3.0** ([Announcing etcd 3.0](https://coreos.com/blog/etcd3-a-new-version-of-etcd-from-coreos.html)), replacing etcd v2's in-memory hierarchical tree + JSON snapshots with a flat binary keyspace, gRPC API, MVCC revision model, and **BoltDB** (`member/snap/db`) as the persistent backend.
* **2017:** Ben Johnson steps back from active maintenance as he considers Bolt's narrow scope complete; CoreOS forks `boltdb/bolt` into `coreos/bbolt` to actively patch bugs, improve freelist/page handling, and optimize for etcd's production workloads.
* **February 2018 (`etcd` v3.3.0):** `etcd` switches its dependency from `boltdb/bolt` to `coreos/bbolt` (recorded in [`CHANGELOG-3.3.md`](https://github.com/etcd-io/etcd/blob/main/CHANGELOG/CHANGELOG-3.3.md): *"Use coreos/bbolt to replace boltdb/bolt"*).
* **March 9, 2019:** `boltdb/bolt` is officially archived on GitHub in read-only mode, with the README explicitly pointing users to CoreOS's `bbolt` fork.
* **2018–2020 (`coreos/bbolt` → `etcd-io/bbolt`):** As `etcd` governance moves under the CNCF / `etcd-io` umbrella, the repository transfers to [`etcd-io/bbolt`](https://github.com/etcd-io/bbolt) with Go module path `go.etcd.io/bbolt` (triggering notable `go.mod` path-mismatch issues during the Go modules transition, e.g. [`etcd#11749`](https://github.com/etcd-io/etcd/issues/11749), [`etcd#12028`](https://github.com/etcd-io/etcd/issues/12028)).

---

## 2. Primary Sources & Notable Quotes

### Ben Johnson on Bolt's Origins, Shopify, and the Freelist
From Ben Johnson's comment on the Hacker News thread for the Roblox outage postmortem ([HN item 30015913](https://news.ycombinator.com/item?id=30015913), Jan 2022):

> *"BoltDB author here. Yes, it is a bad design. The project was never intended to go to production but rather it was a port of LMDB so I could understand the internals. I simplified the freelist handling since it was a toy project. At Shopify, we had some serious issues at the time (~2014) with either LMDB or the Go driver that we couldn't resolve after several months so we swapped out for Bolt. And alas, my poor design stuck around. LMDB uses a regular bucket for the freelist whereas Bolt simply saved the list as an array."*

Key architectural consequence highlighted here:
* Because Bolt began as a learning port, it stored reclaimed page IDs (the **freelist**) as a serialized array rather than inside a B+tree bucket like LMDB. Under heavy churn / fragmentation (later addressed in `bbolt` via hashmap-backed freelists and tuning like `NoFreelistSync`), that toy-project shortcut became a major scalability bottleneck.

### Archiving `boltdb/bolt`
From the [`boltdb/bolt` README](https://github.com/boltdb/bolt) (archived March 9, 2019):

> *"The original goal of Bolt was to provide a simple pure Go key/value store and to not bloat the code with extraneous features. To that end, the project has been a success. However, this limited scope also means that the project is complete. Maintaining an open source database requires an immense amount of time and energy... Unfortunately I no longer have the time or energy to continue this work. Bolt is in a stable state and has years of successful production use. As such, I feel that leaving it in its current state is the most prudent course of action. If you are interested in using a more featureful version of Bolt, I suggest that you look at the CoreOS fork called bbolt."*

### `etcd-io/bbolt` Fork Statement
From the [`etcd-io/bbolt` README](https://github.com/etcd-io/bbolt):

> *"bbolt is a fork of Ben Johnson's Bolt key/value store. The purpose of this fork is to provide the Go community with an active maintenance and development target for Bolt; the goal is improved reliability and stability. bbolt includes bug fixes, performance enhancements, and features not found in Bolt while preserving backwards compatibility with the Bolt API. Bolt is a pure Go key/value store inspired by Howard Chu's LMDB project."*

---

## 3. Why `etcd` Chose BoltDB in v3 (vs. `etcd` v2 Storage)

### What `etcd` v2 Did (and Where It Hit a Wall)
* **In-memory hierarchical tree:** `etcd` v2 stored its entire directory/key tree in RAM and periodically serialized the whole tree into JSON snapshots alongside a WAL.
* **Kubernetes scaling bottlenecks:** As Kubernetes clusters grew to thousands of nodes and hundreds of thousands of objects/events:
  * Keeping the entire state as Go heap objects caused heavy memory consumption, GC "stop-the-world" pressure, and OOM risks.
  * Snapshot serialization and tree operations scaled poorly (`O(N)` with tree size).
  * Per-key TTL heartbeats and HTTP/JSON hanging-GET watches struggled under high write rates, leading to dropped watch events and control-plane instability.

### Why `etcd` v3 Replaced It with BoltDB
* **On-disk B+tree + `mmap`:** Data lives on disk in fixed-size B+tree pages (`member/snap/db`) and is `mmap`-ed so the OS page cache handles caching without Go GC heap pressure; only a compact in-memory key-to-revision index stays on the Go heap.
* **Pure Go (no cgo):** Avoided C dependencies (unlike RocksDB, LevelDB, SQLite, or LMDB), preserving simple cross-compilation and full `pprof`/race-detector observability across Raft and storage.
* **Serializable ACID transactions & CoW MVCC:** Single-writer / lock-free multi-reader transactions fit etcd's revision-based MVCC model, range/prefix scans over sorted keys, and cheap consistent snapshots.
* **No second WAL needed:** Copy-on-write page updates + two-phase meta-page commits provide deterministic crash recovery alongside etcd's own Raft WAL.

---

## 4. Reference Links

* **Original Bolt repo (archived):** https://github.com/boltdb/bolt
* **Active bbolt repo (`go.etcd.io/bbolt`):** https://github.com/etcd-io/bbolt
* **Ben Johnson HN comment (LMDB, Shopify, freelist):** https://news.ycombinator.com/item?id=30015913
* **Nate Finch — Intro to BoltDB (2014):** https://npf.io/2014/07/intro-to-boltdb-painless-performant-persistence/
* **CoreOS — Announcing etcd 3.0 (2016):** https://coreos.com/blog/etcd3-a-new-version-of-etcd-from-coreos.html
* **etcd v3.3 changelog (`boltdb/bolt` → `coreos/bbolt`):** https://github.com/etcd-io/etcd/blob/main/CHANGELOG/CHANGELOG-3.3.md
* **Go module path transition issues in etcd:**
  * https://github.com/etcd-io/etcd/issues/11749
  * https://github.com/etcd-io/etcd/issues/12028
  * https://github.com/etcd-io/etcd/issues/12149
  * https://github.com/etcd-io/etcd/issues/12650
* **Operational deep dive (bbolt db size / freelist in etcd):** https://etcd.io/blog/2023/how-to-debug-large-db-size-issue/
