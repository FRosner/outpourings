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

In 2013, **CoreOS** set out to rethink how server infrastructure was operated. Rather than patching long-lived Linux hosts in place with `apt` or `yum`, **CoreOS Container Linux** shipped a minimal, container-only OS modeled after ChromeOS: just the Linux kernel, `systemd`, a container runtime, and immutable dual-partition (A/B) automatic OS updates. Updates downloaded silently to the passive partition and activated on reboot.

That minimalist design immediately created a coordination problem. Once servers reboot themselves automatically and move containers across a cluster, you need a strongly consistent place to coordinate rolling reboots, schedule services, and share configuration—without hauling a heavy JVM and Apache ZooKeeper onto stripped-down Linux hosts. CoreOS built **`etcd`** (Unix `/etc` + `d` for *distributed* and *daemon*) as a single static Go binary to fill that role.

To make concrete what a "distributed `/etc`" actually meant in practice—and why its workload shaped `etcd`'s earliest storage engine—let's look at how `etcd` sat at the center of a typical CoreOS cluster.

### Inside a CoreOS Cluster: Bootstrapping Around `etcd`

Picture a small CoreOS cluster running a 3-replica `web` service behind an `nginx` reverse proxy on three worker machines, backed by a dedicated `etcd` cluster (three machines so a single crash or reboot doesn't take the store down—we'll unpack how those nodes stay in sync later in this post).

The defining design rule of the early CoreOS stack is **hub-and-spoke coordination**: daemons on worker machines never talk directly to each other. Schedulers do not open RPC connections to worker agents, and update daemons do not gossip. Every component only reads from and writes to `etcd`'s shared directory tree:

![How a CoreOS Cluster Bootstraps Around etcd](./coreos_cluster_bootstrap.webp)

Walking through the bootstrap sequence shows how every layer of the cluster maps onto a small branch of that tree:

1. **Start with an empty `/`:** `etcd` boots first as a shared, hierarchical keyspace—literally a cluster-wide `/etc`.
2. **Workers join via `fleetd`:** Each CoreOS worker starts `fleetd`, registers a liveness heartbeat under `/_coreos.com/fleet/machines/`, and agrees on a single active scheduler (`/_coreos.com/fleet/lease/engine-leader`, held here by Worker 2).
3. **An admin deploys services and config:** Using `fleetctl` and `etcdctl` directly against `etcd` (in 2013–2014 `fleetctl` wrote unit definitions straight into `etcd` with no intermediate API server), an admin submits `web@1..3` and `nginx` along with shared application config like `/config/web/rate_limit`. The active `fleetd` scheduler assigns those units to workers, which launch the containers locally.
4. **Running containers register for discovery:** Once up, each `web` replica publishes its live `IP:port` under `/services/web/`. On Worker 3, `nginx` (driven by a lightweight template helper like `confd`) follows `/services/web/` so traffic routes only to healthy backends.
5. **OS updates take turns via `locksmithd`:** Every worker also runs `locksmithd`, sharing a reboot semaphore under `/coreos.com/updateengine/rebootlock/semaphore` so automatic A/B OS updates reboot one machine at a time instead of taking the whole cluster offline at once. *(The `etcd` nodes themselves run `locksmithd` in their own one-at-a-time group for the same reason.)*

Notice the scale of what `etcd` actually holds once the entire cluster is up and running. The animation compresses each unit to a single line (13 keys total); even in a real CoreOS cluster where `fleet` splits each unit across a few internal subkeys (`object`, `target`, `state`), the whole cluster's working set is only dozens of tiny keys, well under 1 MB in total, with a light trickle of periodic heartbeat writes.

## The `v0.x` Data Model & Coordination Primitives

TBD — Explain the hierarchical directory/key API over HTTP+JSON and the three primitives that turned `/etc` into a coordination service:
- **Atomic Compare-and-Swap (`prevValue` / `prevIndex`)**
- **Per-key TTLs** (ephemeral registrations and heartbeats)
- **Long-polling HTTP watches** (`?wait=true&waitIndex=...`)

### Concrete Walkthrough: Minimal `etcd v0.4` Config & Tracing the 3 AM Reboot Over `curl`

*(Raw draft notes — grounded in `~/Documents/etcd` at `v0.4.9` and `~/Documents/locksmith/lock/etcd.go` + `semaphore.go`)*

> **Code archaeology nuance (`locksmith`):** Real `locksmith` (`lock/etcd.go`) uses **CAS (`prevIndex`) *without* a TTL or watch**—deliberately, because a rebooting host must keep holding the semaphore while powered down and unlocks on boot-up (waiting hosts retry with exponential backoff). Pairing `locksmith`'s CAS semaphore with `/services/web/*` service discovery (TTLs + recursive watches) shows all three primitives faithfully.

#### Minimal 3-Node `etcd v0.4` Configuration (`/etc/etcd/etcd.conf`)

In `v0.4`, each control-plane node ran a single static `etcd` binary configured via CLI flags or `/etc/etcd/etcd.conf` (TOML):
- Port `4001`: Client HTTP+JSON API
- Port `7001`: Peer-to-peer `goraft` HTTP traffic
- `data_dir`: Where `goraft` stores `conf`, its append-only `log`, and JSON `snapshot/` files
- `snapshot_count`: Raft commits between full-tree JSON snapshots (default `10000`)

**`etcd-1` (`10.0.0.1` — bootstraps cluster):**
```toml
name = "etcd-1"
addr = "10.0.0.1:4001"
bind_addr = "0.0.0.0:4001"
data_dir = "/var/lib/etcd"
snapshot = true
snapshot_count = 10000

[peer]
addr = "10.0.0.1:7001"
bind_addr = "0.0.0.0:7001"
```

**`etcd-2` (`10.0.0.2` — joins `etcd-1`; `etcd-3` is identical with `10.0.0.3`):**
```toml
name = "etcd-2"
addr = "10.0.0.2:4001"
bind_addr = "0.0.0.0:4001"
data_dir = "/var/lib/etcd"
peers = ["10.0.0.1:7001"]
snapshot = true
snapshot_count = 10000

[peer]
addr = "10.0.0.2:7001"
bind_addr = "0.0.0.0:7001"
```

On disk, `/var/lib/etcd/` only contained:
```text
/var/lib/etcd/
├── conf          # Raft peer metadata
├── log           # Append-only Raft command log
└── snapshot/     # Periodic full-tree JSON dumps
```

#### Concrete HTTP+JSON (`curl`) Interactions From the 3 AM Reboot

1. **Ephemeral service registration (Tree + `ttlKeyHeap`):**
   ```bash
   curl -X PUT http://10.0.0.1:4001/v2/keys/services/web/web@1 \
     -d value="10.0.1.1:8080" \
     -d ttl=30
   ```
   *Under the hood:* `goraft` commits a `Set` command → `store` auto-creates `/services` and `/services/web`, inserts leaf `web@1`, pushes it onto `ttlKeyHeap`, and appends an `Event` to `EventHistory`.

2. **`nginx`/`confd` opens a recursive long-poll watch (`WatcherHub` + `EventHistory`):**
   ```bash
   curl "http://10.0.0.1:4001/v2/keys/services/web?wait=true&recursive=true&waitIndex=42"
   # HTTP connection stays parked in WatcherHub.watchers["/services/web"]
   ```

3. **Worker 1 acquires the `locksmith` reboot semaphore (Atomic CAS via `prevIndex`):**
   After reading `/v2/keys/coreos.com/updateengine/rebootlock/semaphore` (`modifiedIndex: 5`):
   ```bash
   curl -X PUT http://10.0.0.1:4001/v2/keys/coreos.com/updateengine/rebootlock/semaphore \
     -d prevIndex=5 \
     -d value='{"semaphore":0,"max":1,"holders":["worker-1"]}'
   ```
   If Worker 2 races with `prevIndex=5`, Raft serializes both: Worker 1 succeeds (`modifiedIndex: 42`) and Worker 2 gets `101: Compare failed ([5 != 42])`.

4. **Worker 1 reboots → TTL expires → Watcher fires:**
   30s after Worker 1 stops heartbeating, the Raft leader's 500ms `SyncCommand(now)` commits → `store.DeleteExpiredKeys(now)` pops `web@1` off `ttlKeyHeap`, increments `CurrentIndex` to `43`, records an `expire` event in `EventHistory`, and walks `/services/web/web@1` → `/services/web` → `/` to wake `confd`'s hanging `GET`:
   ```json
   {
     "action": "expire",
     "node": { "key": "/services/web/web@1", "modifiedIndex": 43 },
     "prevNode": { "key": "/services/web/web@1", "value": "10.0.1.1:8080" }
   }
   ```
   While `confd` reloads `nginx`, `fleetd` reschedules `web@1` onto Worker 3 (`10.0.1.3:8081`, `index: 44`). When `confd` reconnects with `?wait=true&recursive=true&waitIndex=44`, `EventHistory.scan()` serves `index: 44` immediately from the 1,000-slot ring buffer.

5. **Worker 1 finishes booting → releases the lock via CAS (`prevIndex=42`):**
   ```bash
   curl -X PUT http://10.0.0.1:4001/v2/keys/coreos.com/updateengine/rebootlock/semaphore \
     -d prevIndex=42 \
     -d value='{"semaphore":1,"max":1,"holders":[]}'
   ```

## Under the Hood: `etcd v0.4` & `goraft` (Source-Code Archaeology)

TBD — Trace the end-to-end write/read/watch lifecycle using the exact operations above: Client HTTP (`:4001`) → `goraft` Leader → Raft `log` append & quorum replication (`:7001`) → apply to in-memory `store` (behind `worldLock`) → wake watchers / record in `EventHistory` → periodic JSON snapshot (`monitorSnapshot` every 3s, default `SnapshotCount = 10000`).

*(Verified `v0.4.9` details to highlight below: `store.worldLock sync.RWMutex`, leader `monitorSync()` proposing `SyncCommand(now)` every 500ms through Raft for deterministic TTL expiration via `DeleteExpiredKeys(cutoff)`, `EventHistory` fixed 1,000-slot ring buffer returning `EcodeEventIndexCleared` / `401` on overflow, and `store.Save()` taking `worldLock` to deep-clone `Root` + `EventHistory` + `Stats` before `json.Marshal`.)*

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
