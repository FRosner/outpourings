# History of `etcd` Storage Engines: Usage, Featureset & Architecture (2013 → 2026)

A chronological report on why `etcd` was created, how its real-world adoption and feature set evolved from `v0.1` to `v3.7`, and how those workloads drove every major change in its storage layer.

---

## Why `etcd` Was Created (2013)

In 2013, **CoreOS** was building **CoreOS Container Linux**, a minimal Linux distribution designed to run containerized infrastructure across clusters of machines. Operating a fleet of container hosts required a strongly consistent way to share configuration, coordinate rolling OS updates, and discover services—without forcing operators to run heavy JVM-based systems like Apache ZooKeeper.

The name **`etcd`** comes straight from that mental model: Unix's **`/etc`** directory (where a single machine stores system-wide configuration) plus **`d`** (for **distributed** and the Unix daemon naming convention). In short, `etcd` was built to be a **distributed `/etc`**.

That original mental model—small configuration trees, simple key-value lookups, and coordination locks—directly shaped `etcd`'s earliest APIs and storage design. As adoption shifted from CoreOS host utilities to **Kubernetes** managing entire container platforms, the mismatch between `etcd`'s original `/etc`-style storage and Kubernetes's scale forced a decade of storage evolution.

---

## Summary Matrix

| Era / Version | Release Date | Primary Adoption & Workloads | Key Featureset | Consensus & Storage Implementation | How Usage Drove Storage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **v0.1 – v0.4.x** | Mid-2013 – 2014 | CoreOS Container Linux (`fleet`, `locksmith`), `SkyDNS`, `flannel` | HTTP+JSON hierarchical dirs, CAS, per-key TTLs, long-poll watches | `goraft` + in-memory tree (`store`) + Raft log + JSON snapshots | Built for small `/etc`-like config trees that easily fit in RAM. |
| **v2.0 – v2.3** | Jan 28, 2015 | Early production clusters, Cloud Foundry, **Kubernetes v1.0** (Jul 2015) | Same v2 HTTP+JSON tree API, hardened clustering | `etcd/raft` + segmented `wal` + `snap` + in-memory `v2store` | Decoupled Raft fixed `goraft` stability, but Kubernetes workloads blew past `v2store`'s RAM/GC/snapshot limits. |
| **v3.0 – v3.2** | Jun 30, 2016 | **Kubernetes v1.6** (default backend), OpenShift, Rook/Ceph | gRPC/Protobuf, flat binary keys, MVCC revisions, `Txn`, shared Leases, Watch streams | `etcd/raft` + `wal`/`snap` + `mvcc` (`treeIndex` in RAM + **`boltdb/bolt`** CoW B+tree via `mmap`) | Co-designed around Kubernetes `LIST`/`WATCH` (`resourceVersion`), optimistic concurrency, and off-heap disk storage. |
| **v3.3 – v3.5** | Feb 2018 – Jun 2021 | CNCF Graduation (Nov 2020); multi-thousand-node K8s + CRD explosion | `ConcurrentReadTx` (3.4), Pre-Vote & Learners (3.4), `map` freelist default (3.5) | `mvcc` + **`coreos/bbolt`** / **`go.etcd.io/bbolt`** v1.3 | Large K8s reads stalled writes (`ConcurrentReadTx` fix); CRD churn/compaction exposed `boltdb` bugs and `array` freelist `O(N)` stalls. |
| **v3.6 – v3.7** | May 2025 – Jul 2026 | Mature, high-density K8s control planes | Sole `v3store` membership & safe rolling downgrades (3.6); `--keys-only` optimization & DB size cap (3.7) | `mvcc` + **`bbolt`** v1.4 (3.6) → v1.5.1 (3.7); `v2store` completely removed | Eliminated legacy `v2store` split-brain/overhead and cut memory & unnecessary bbolt value reads for large control-plane queries. |

---

## Phase 1: The Distributed `/etc` & `goraft` Era (`v0.1` – `v0.4.x`, 2013–2014)

### Adoption & Usage
* Used primarily inside CoreOS's own ecosystem and early container tooling:
  * **`locksmith`:** Coordinated sequential reboots across CoreOS Container Linux hosts using a distributed semaphore/lock so OS updates didn't take down an entire cluster at once.
  * **`fleet`:** Treated a cluster of machines like a distributed `systemd`, tracking unit placement and state in `etcd`.
  * **`SkyDNS` & `flannel`:** Service discovery DNS records and container overlay subnet allocations.
* Datasets were small (megabytes, not gigabytes), with relatively low write churn and few concurrent watchers.

### Featureset
* **Hierarchical directory/key API over HTTP+JSON:** Keys behaved like filesystem paths with explicit directories and leaf files.
* **Coordination primitives:** Atomic compare-and-swap (`prevValue` / `prevIndex`), per-key **TTLs** (for ephemeral service registrations/heartbeats), and HTTP long-polling **watches** on keys or directories.

### Storage Implementation & Relationship to Usage
* **Consensus:** Ben Johnson's [`github.com/goraft/raft`](https://github.com/goraft/raft) (originally created for his *Sky* analytics database)—one of the earliest Go Raft libraries.
* **Storage:** An in-memory hierarchical tree (`store`), backed by sequential Raft command logs on disk and periodic **JSON-serialized snapshots** of the entire tree.
* **Why it fit—and why it broke:** Keeping the whole directory tree in memory as Go structs and dumping it as JSON matched the small-config `/etc` use case. However, `goraft` tightly coupled network transport, disk I/O, and state-machine application inside one library, causing lock contention and subtle correctness/partition issues as clusters grew beyond early prototypes.

---

## Phase 2: The `etcd/raft` Rewrite & Hitting the Kubernetes Wall (`v2.0`, Jan 2015)

### Adoption & Usage
* **Production early adopters & Kubernetes v1.0 (July 2015):** `etcd 2.0` was CoreOS's first production-grade stable release and was adopted by **Kubernetes 1.0** as its sole cluster state store (alongside Cloud Foundry, Vulcand, and container networking tools).
* **The workload shift:** Kubernetes did *not* use `etcd` like a quiet config directory. It stored thousands—and soon hundreds of thousands—of serialized API objects (Pods, Nodes, Services, Endpoints, Events), sent continuous node heartbeat/status updates, and had dozens of control-plane controllers running `LIST` + `WATCH` loops across prefixes.

### Featureset
* Preserved the v2 HTTP+JSON hierarchical API, per-key TTLs, and hanging-GET watches while hardening cluster membership changes and TLS/auth.

### Storage Implementation & Relationship to Usage
* **What changed (`goraft` → `etcd/raft` + `wal` + `snap`):** CoreOS replaced `goraft` with a brand-new, pure state-machine Raft implementation (**`etcd/raft`**) that decoupled network I/O, timers, and disk persistence from consensus logic. Persistence was split into segmented, CRC-checksummed write-ahead logs (**`wal`**, `$seq-$index.wal`) and periodic snapshot files (**`snap`**) containing JSON-serialized dumps of the in-memory **`v2store`** tree.
* **How Kubernetes workloads broke `v2store`:**
  1. **Go Heap & GC Pauses:** Keeping every Pod, Event, and ConfigMap in RAM as Go pointer trees inflated heap usage and triggered massive Go Garbage Collector "stop-the-world" pauses and OOMs.
  2. **`O(N)` JSON Snapshots:** Periodically serializing the entire in-memory tree to JSON spiked CPU and latency whenever snapshots ran under write load.
  3. **Per-Key TTL Churn:** Kubernetes node/endpoint heartbeats refreshing individual key TTLs generated constant Raft proposals and writes.
  4. **Fragile Watches:** HTTP hanging-GET watches lacked deep historical revision retention, dropping events or stalling under high write bursts and forcing expensive full re-syncs.

---

## Phase 3: The `v3` Storage & API Rewrite for Kubernetes Scale (`v3.0` – `v3.2`, 2016–2017)

### Adoption & Usage
* Announced **June 30, 2016** ([Announcing etcd 3.0](https://coreos.com/blog/etcd3-a-new-version-of-etcd-from-coreos.html)), `etcd v3` was explicitly engineered to break the v2 scalability walls for **Kubernetes** (which made `etcd v3` its **default storage backend in Kubernetes 1.6**), OpenShift, and cloud-native platforms like Rook/Ceph.

### Featureset — Co-Designed with Storage
Every flagship `v3` feature was designed hand-in-hand with the new storage architecture:
* **Flat Binary Keyspace + Range/Prefix Queries:** Dropped Unix-style directories in favor of lexically sorted raw byte keys (keys like `/registry/pods/default/nginx` look hierarchical by convention, but are flat sorted keys). This enabled fast prefix/range scans for Kubernetes `LIST` calls.
* **MVCC & Global Revisions → Kubernetes `resourceVersion`:** Instead of overwriting keys in place, every mutation creates a new version stamped with a monotonically increasing cluster-wide **revision**. Kubernetes maps `.metadata.resourceVersion` directly to this etcd revision, enabling consistent `List-then-Watch` semantics from any uncompacted revision (or returning `410 Gone` / *"required revision has been compacted"* when a slow client falls behind the compaction window).
* **gRPC Multiplexed Watch Streams:** Replaced HTTP/JSON hanging-GETs with persistent bidirectional gRPC/Protobuf streams capable of watching key prefixes reliably from an exact revision.
* **Multi-Key Atomic `Txn`:** Compare-and-then-else mini-transactions enabled Kubernetes optimistic concurrency (`resourceVersion` checks), distributed locks, and leader elections.
* **Server-Side Leases:** Replaced per-key TTL updates with shared **Leases**—thousands of keys can attach to a single lease refreshed by one lightweight keepalive, slashing storage write amplification.

### Storage Implementation & Relationship to Usage
* **`mvcc` + `backend` + `boltdb/bolt`:** `etcd v3` introduced a completely separate storage path (isolated from `v2store`) split into two tiers:
  1. **`treeIndex` (in RAM):** A compact in-memory B-tree (`google/btree`) mapping user keys to revision metadata (generation + revision pointers), keeping Go heap objects small and predictable.
  2. **`backend` wrapping BoltDB (on disk, `member/snap/db`):** Actual key-value revision payloads, leases, cluster metadata, and Raft's `consistent_index` live on disk inside a single **`mmap`-ed Copy-on-Write B+tree** file.
* **Why BoltDB was chosen:**
  * **Pure Go (zero `cgo`):** Unlike RocksDB, LevelDB, SQLite, or LMDB, BoltDB kept `etcd` 100% pure Go—preserving easy cross-compilation and full `pprof`/race-detector visibility across Raft and storage.
  * **Ordered B+tree:** Sorted keys in contiguous leaf pages mapped directly to `etcd v3` prefix/range scans.
  * **Off-Heap `mmap` & MVCC Reads:** Delegating page caching to the OS page cache eliminated Go GC heap pressure for large datasets, while CoW pages let read transactions view consistent snapshots alongside a single writer.
  * **Simple Crash Recovery & Snapshots:** Two-phase meta-page commits avoided needing a second DB-level WAL alongside Raft's `wal`, and Raft snapshots could stream/copy `member/snap/db` directly without walking and JSON-encoding every key in RAM.

*(For the backstory of how BoltDB itself started as a learning port of LMDB at Shopify and why CoreOS later forked it, see [bbolt_history.md](file:///Users/frosner/Documents/outpourings/bbolt_etcd/bbolt_history.md).)*

---

## Phase 4: Production Hardening, `bbolt` Fork & Large-Cluster Bottlenecks (`v3.3` – `v3.5`, 2018–2021)

### Adoption & Usage
* `etcd` joined the CNCF in December 2018 and achieved **CNCF Graduated status on November 24, 2020**, becoming the ubiquitous control-plane database across Kubernetes distributions.
* Clusters scaled to thousands of nodes and heavy **CRD (Custom Resource Definition)** usage (Cilium, Calico, service meshes, GitOps/Argo controllers), driving higher write churn, larger `LIST` payloads, frequent MVCC compactions, and high-frequency lease/event turnover.

### Featureset & Storage Changes Driven by Real Workloads
* **`etcd v3.3.0` (Feb 2018) — Forking `boltdb/bolt` → `coreos/bbolt`:**
  * *Why:* Upstream `boltdb/bolt` was unmaintained while large clusters exposed DB growth and page-allocation bugs. CoreOS forked it into `coreos/bbolt` (later [`etcd-io/bbolt`](https://github.com/etcd-io/bbolt) / `go.etcd.io/bbolt`) to fix database space growth issues and take ownership of stability (`CHANGELOG-3.3.md`).
* **`etcd v3.4.0` (Aug 30, 2019) — Fully Concurrent Reads (`ConcurrentReadTx`), Learners & Pre-Vote:**
  * *The bottleneck:* Prior to v3.4, `etcd`'s `backend` batched writes in an in-memory buffer (`BatchTx`) before flushing to `bbolt`, and read transactions (`ReadTx`) shared locks/structures with that buffer. Heavy Kubernetes `LIST` queries blocked concurrent writes and triggered `"read-only range request took too long to execute"` stalls.
  * *The fix:* v3.4 introduced **`ConcurrentReadTx()`**, copying the transient uncommitted buffer at transaction start so expensive reads run concurrently without blocking `BatchTx` writes (yielding major throughput gains and p99 write-latency drops).
  * *Cluster safety features:* Added **Raft Pre-Vote** (preventing isolated nodes from disrupting quorum) and **Learner (non-voting) nodes** (allowing new nodes to catch up on large `bbolt` snapshots before joining quorum), and deprecated `v2store` (`--enable-v2=false` by default).
* **`etcd v3.5.0` (Jun 15, 2021) — `map` Freelist Default & Buffer Tuning:**
  * *The bottleneck:* Under heavy Kubernetes CRD churn, lease expirations, and compaction cycles on multi-GB databases, `bbolt`'s original `array` freelist (inherited from Ben Johnson's "toy project" simplification) degraded due to `O(N)` scanning/merging on commits.
  * *The fix:* v3.5 switched the default `--backend-bbolt-freelist-type` from `array` to **`map`** (in-memory hashmap freelist), drastically speeding up large-DB commits, and refined `ConcurrentReadTx` buffer copying to cut allocation overhead. This also surfaced operational nuances around `totalDBSize` vs. `totalDBSizeInUse` and manual `defrag` (explained in [How to debug large db size issue?](https://etcd.io/blog/2023/how-to-debug-large-db-size-issue/)).

---

## Phase 5: Retiring `v2store` & Modern Control-Plane Efficiency (`v3.6` – `v3.7`, 2025–2026)

### Adoption & Usage
* Modern Kubernetes control planes focus on zero-downtime upgrades/downgrades, strict memory/quota predictability, and reducing API-server/etcd read amplification on large clusters.

### Featureset & Storage Changes
* **`etcd v3.6.0` (May 15, 2025) — Single Source of Truth & `bbolt v1.4`:**
  * *What & why:* Removed `--enable-v2` and migrated cluster membership truth out of `v2store` into **`v3store`** (eliminating decades-old dual-store complexity and adding `etcdutl check v2store` for safe upgrades). Upgraded to **`bbolt v1.4`**, improved schema compatibility for **rolling downgrades** back to v3.5, and reduced default memory consumption by ~50%.
  * See [Announcing etcd v3.6.0](https://etcd.io/blog/2025/05/15/announcing-etcd-v3.6.0/).
* **`etcd v3.7.0` (Jul 8, 2026) — Pure `v3store`, `bbolt v1.5.1` & `--keys-only` Optimization:**
  * *What & why:* Completely stripped out the final remnants of `v2store` (`client/v2`, `--experimental-enable-v2v3`, legacy v2 snapshot loading). Upgraded to **`bbolt v1.5.1`**, adding explicit DB file size limit enforcement (refusing writes above the threshold until compacted) and `NoStatistics` to reduce lock contention. Added a **`--keys-only` range query optimization** so queries that only need keys can be served directly from the in-memory `treeIndex` without reading value payloads from `bbolt`.
  * See [Announcing etcd v3.7.0](https://etcd.io/blog/2026/07/08/announcing-etcd-v3.7.0/).

---

## Phase 6: Explored Alternatives & External Shims

Because `bbolt`'s single-writer model, copy-on-write write amplification, `mmap` ceilings (typically 2–8 GB backend quotas in Kubernetes), and manual compaction/defrag cycles define `etcd`'s hard operational boundaries, the community has repeatedly explored alternatives:

1. **Meta-Issue: Pluggable Backend ([`etcd#10321`](https://github.com/etcd-io/etcd/issues/10321)):**
   * Tracked decoupling `etcd`'s Raft/MVCC layer from `bbolt` so operators or cloud providers could swap in alternative engines.
   * **Why `bbolt` stayed:** `etcd`'s `mvcc` layer, watch history, `BatchTx`/`ConcurrentReadTx`, and bucket layout are tightly coupled to `bbolt`'s ACID transactions and B+tree prefix scans; abstracting them cleanly without risking serializable snapshot isolation or crash-recovery guarantees remains extremely difficult.
2. **LSM-Tree Candidates Evaluated:**
   * **BadgerDB (pure Go, Dgraph):** Strong write throughput, but higher read amplification on range scans and Go GC/compaction spikes.
   * **Pebble (pure Go, Cockroach Labs):** Built in Go to avoid `cgo` while matching RocksDB's LSM strengths, but moving `etcd`'s bucket/MVCC model onto an LSM engine requires a major redesign.
   * **RocksDB (C++):** High-performance LSM engine, but requires `cgo`, which `etcd` maintainers avoid to keep cross-compilation simple and Go profiling intact.
3. **API-Compatible Shims (`k3s-io/kine`):**
   * For workloads that want Kubernetes without `etcd`'s Raft quorum or `bbolt`'s constraints (single-node edge clusters or teams preferring managed SQL), **[`k3s-io/kine`](https://github.com/k3s-io/kine)** (*"Kine is not etcd"*) translates the subset of the `etcd v3` gRPC API used by `kube-apiserver` onto **SQLite**, **PostgreSQL**, or **MySQL/MariaDB**.

---

## Reference Links

* **CoreOS — Announcing etcd 3.0 (June 30, 2016):** https://coreos.com/blog/etcd3-a-new-version-of-etcd-from-coreos.html
* **etcd v3.3 Changelog (`boltdb/bolt` → `coreos/bbolt`):** https://github.com/etcd-io/etcd/blob/main/CHANGELOG/CHANGELOG-3.3.md
* **Announcing etcd 3.5 (June 15, 2021):** https://etcd.io/blog/2021/announcing-etcd-3.5/
* **How to debug large db size issue? (etcd blog, 2023):** https://etcd.io/blog/2023/how-to-debug-large-db-size-issue/
* **Announcing etcd v3.6.0 (May 15, 2025):** https://etcd.io/blog/2025/05/15/announcing-etcd-v3.6.0/
* **Announcing etcd v3.7.0 (July 8, 2026):** https://etcd.io/blog/2026/07/08/announcing-etcd-v3.7.0/
* **Pluggable Backend Meta-Issue:** https://github.com/etcd-io/etcd/issues/10321
* **Kine (SQLite/Postgres/MySQL shim for etcd v3 API):** https://github.com/k3s-io/kine
* **bbolt history notes:** [bbolt_history.md](file:///Users/frosner/Documents/outpourings/bbolt_etcd/bbolt_history.md)
