---
title: "The Evolution of etcd Storage (Part 1): When a Distributed /etc Fit in RAM (v0.1 – v0.4)"
published: false
description: "TBD — How CoreOS's small-config workload shaped etcd's earliest storage engine: an in-memory directory tree, goraft consensus, JSON snapshots, and the cracks that led to etcd v2."
tags: etcd, distributedsystems, databases, storage
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

## Inside a CoreOS Cluster: Bootstrapping Around `etcd`

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

## Storing `/etc` in RAM: Inside `etcd v0.4`'s `store`

When an entire cluster's working set fits in a few hundred kilobytes, you do not build an on-disk B+tree or an LSM-tree. Early `etcd` (`v0.1 – v0.4`) had no embedded database engine at all—its primary storage engine was an **in-memory Go directory tree** (`store`), exposed over a simple HTTP+JSON API on port `4001`.

Looking directly at [`store/store.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/store.go#L66-L74) in `etcd v0.4.9`, the entire storage engine is summarized in a single seven-field struct:

```go
// store/store.go (etcd v0.4.9)
type store struct {
	Root           *node
	WatcherHub     *watcherHub
	CurrentIndex   uint64
	Stats          *Stats
	CurrentVersion int
	ttlKeyHeap     *ttlKeyHeap  // need to recovery manually
	worldLock      sync.RWMutex // stop the world lock
}
```

Every coordination pattern from our CoreOS bootstrap walkthrough maps cleanly onto one of those fields:

| CoreOS Cluster Need | HTTP+JSON Primitive | Backing In-Memory Structure |
| :--- | :--- | :--- |
| Hierarchical `/etc` paths (`fleet`, `/config/*`) | Directory / leaf CRUD | `Root *node` tree (`Children map[string]*node`) |
| Mutual exclusion (`locksmithd` semaphore, `fleetd` leader lease) | Atomic CAS (`prevIndex` / `prevValue`) | Monotonic `CurrentIndex` + `worldLock` |
| Ephemeral liveness (`fleetd` heartbeats, `web@1..3` registration) | Per-key TTLs (`ttl=30`) | `ttlKeyHeap` min-heap |
| Reactive config (`nginx`/`confd` following `/services/web/`) | Long-polling watches (`?wait=true`) | `WatcherHub` + 1,000-slot `EventHistory` ring buffer |

Let's unpack each of those four pieces in code.

### The Directory Tree, `worldLock`, and Atomic CAS

At the root of the store sits a Unix-like tree of `node` structs ([`store/node.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/node.go#L25-L40)):

```go
// store/node.go (etcd v0.4.9)
type node struct {
	Path string

	CreatedIndex  uint64
	ModifiedIndex uint64

	Parent *node `json:"-"` // should not encode this field! avoid circular dependency.

	ExpireTime time.Time
	ACL        string
	Value      string           // for key-value pair
	Children   map[string]*node // for directory

	store *store
}
```

A node is either a **leaf** (holding a `Value` string with `Children == nil`) or a **directory** (holding a `Children map[string]*node` keyed by path segment). In memory, our CoreOS cluster's keyspace looks like a nested web of Go structs and hash maps:

```text
store.Root (dir "/")
├── "_coreos.com" ──► "fleet" ──► "machines" ──► ...
├── "config"      ──► "web"   ──► "rate_limit" ("1000")
├── "coreos.com"  ──► "updateengine" ──► "rebootlock" ──► "semaphore" (idx: 5)
└── "services"    ──► "web"   ──► "web@1" ("10.0.1.1:8080", ExpireTime: +30s) ◄──┐
                                                                                 │
store.ttlKeyHeap.array[0] ───────────────────────────────────────────────────────┘
```

Reading `/services/web/web@1` acquires `worldLock.RLock()`, splits the path, and walks `Root.Children["services"].Children["web"].Children["web@1"]`. Every mutation acquires the exclusive `worldLock.Lock()`—literally commented `// stop the world lock` in the source—bumps the store's global monotonic `CurrentIndex`, and stamps the affected node's `ModifiedIndex`.

That single global lock and monotonic index make **Compare-and-Swap (CAS)** trivial. Take `locksmithd` coordinating a 3 AM OS reboot on Worker 1. First, `locksmithd` reads `/coreos.com/updateengine/rebootlock/semaphore` and observes `modifiedIndex: 5`. To claim the reboot slot, it submits a conditional `PUT` with `prevIndex=5`:

```bash
curl -X PUT http://10.0.0.1:4001/v2/keys/coreos.com/updateengine/rebootlock/semaphore \
  -d prevIndex=5 \
  -d value='{"semaphore":0,"max":1,"holders":["worker-1"]}'
```

*Note that `locksmith` deliberately [acquires](https://github.com/coreos/locksmith/blob/v0.2.3/lock/etcd.go#L82-L95) this semaphore with `prevIndex` without a TTL or watch. A rebooting host must keep holding the slot while powered off and only releases it via another CAS after booting back up; other hosts retry with exponential backoff.*

Inside `store.CompareAndSwap` ([`store/store.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/store.go#L199-L250)), the check-and-update executes atomically under `worldLock`:

```go
// store/store.go (etcd v0.4.9, trimmed)
func (s *store) CompareAndSwap(nodePath, prevValue string, prevIndex uint64,
	value string, expireTime time.Time) (*Event, error) {

	s.worldLock.Lock()
	defer s.worldLock.Unlock()

	n, err := s.internalGet(nodePath)
	if err != nil {
		return nil, err
	}
	if ok, which := n.Compare(prevValue, prevIndex); !ok {
		cause := getCompareFailCause(n, which, prevValue, prevIndex)
		return nil, etcdErr.NewError(etcdErr.EcodeTestFailed, cause, s.CurrentIndex)
	}

	s.CurrentIndex++
	// ... record Event with PrevNode ...
	n.Write(value, s.CurrentIndex)
	n.UpdateTTL(expireTime)
	s.WatcherHub.notify(e)
	return e, nil
}
```

If Worker 1 and Worker 2 both race with `prevIndex=5`, whichever request arrives first advances the node to `modifiedIndex: 42`. The second request fails `n.Compare` and receives `101: Compare failed ([5 != 42])`.

### Ephemeral Keys and `ttlKeyHeap`

Unlike the reboot semaphore, service registrations and machine heartbeats *must* vanish automatically if a worker crashes. When `web@1` comes up on Worker 1, it registers an ephemeral key with a 30-second TTL:

```bash
curl -X PUT http://10.0.0.1:4001/v2/keys/services/web/web@1 \
  -d value="10.0.1.1:8080" \
  -d ttl=30
```

When `store` inserts `/services/web/web@1` (auto-creating `/services` and `/services/web` along the way), it sees a non-zero `ExpireTime` and registers the `*node` pointer in `ttlKeyHeap` ([`store/ttl_key_heap.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/ttl_key_heap.go#L8-L74)). Rather than keeping a bare slice or scanning every key in the tree to find expired ones, `ttlKeyHeap` implements Go's standard library `container/heap.Interface` (`Len`, `Less`, `Swap`, `Push`, `Pop`):

```go
// store/ttl_key_heap.go (etcd v0.4.9, trimmed)
type ttlKeyHeap struct {
	array  []*node
	keyMap map[*node]int
}

func (h ttlKeyHeap) Len() int {
	return len(h.array)
}

func (h ttlKeyHeap) Less(i, j int) bool {
	return h.array[i].ExpireTime.Before(h.array[j].ExpireTime)
}

func (h ttlKeyHeap) Swap(i, j int) {
	h.array[i], h.array[j] = h.array[j], h.array[i]

	// Keep each node's current slice index up to date
	h.keyMap[h.array[i]] = i
	h.keyMap[h.array[j]] = j
}

func (h *ttlKeyHeap) Push(x interface{}) {
	n, _ := x.(*node)
	h.keyMap[n] = len(h.array)
	h.array = append(h.array, n)
}

func (h *ttlKeyHeap) Pop() interface{} {
	old := h.array
	n := len(old)
	x := old[n-1]
	h.array = old[0 : n-1]
	delete(h.keyMap, x)
	return x
}

func (h *ttlKeyHeap) update(n *node) {
	if index, ok := h.keyMap[n]; ok {
		heap.Remove(h, index)
		heap.Push(h, n)
	}
}
```

Two details explain how this data structure works:

1. **Ordering `array` by `ExpireTime` so `array[0]` always expires first:** Go's `container/heap` treats the flat slice `array` as an implicit binary tree where the children of index `i` sit at `2*i + 1` and `2*i + 2`. Whenever `etcd` inserts or removes a node via `heap.Push` / `heap.Pop`, `container/heap` calls `Less(i, j)`—comparing `ExpireTime` on the `*node` pointers—and swaps elements up or down a single root-to-leaf path (`O(log N)`) to preserve the min-heap invariant: every parent expires earlier than both of its children. As a result, the soonest-to-expire key always sits at the root (`array[0]`), so checking whether anything is due to expire is an `O(1)` peek.
2. **Tracking positions with `keyMap` for heartbeat refreshes and early deletes:** A plain binary heap only knows where the *earliest* element sits (`array[0]`). When `web@1` refreshes its 30-second heartbeat (`UpdateTTL`) or gets deleted manually, `store` finds the `*node` via the directory tree—not the heap—so it has no idea which slot `i` in `array` that node currently occupies. Because `Push`, `Pop`, and `Swap` keep `keyMap[node] = i` synchronized on every move, `update(n)` and `remove(n)` find the node's slice index in `O(1)` and rebalance via `heap.Remove` / `heap.Push` in `O(log N)` instead of linearly scanning the entire slice.

Expiring overdue keys is then a tight loop in [`store.DeleteExpiredKeys(cutoff time.Time)`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/store.go#L565-L592):

```go
// store/store.go (etcd v0.4.9, trimmed)
func (s *store) DeleteExpiredKeys(cutoff time.Time) {
	s.worldLock.Lock()
	defer s.worldLock.Unlock()

	for {
		node := s.ttlKeyHeap.top()
		if node == nil || node.ExpireTime.After(cutoff) {
			break
		}

		s.CurrentIndex++
		e := newEvent(Expire, node.Path, s.CurrentIndex, node.CreatedIndex)
		e.PrevNode = node.Repr(false, false)

		s.ttlKeyHeap.pop()
		node.Remove(true, true, func(path string) {
			s.WatcherHub.notifyWatchers(e, path, true)
		})
		s.WatcherHub.notify(e)
	}
}
```

Putting that behavior into motion across our three `web` replicas (`ttl=30s`), you can see why a min-heap makes ephemeral heartbeats so effortless—healthy renewals keep pushing keys down below the root, while a crashed container inevitably rises to the top and expires as soon as time catches up:

![How ttlKeyHeap Tracks Ephemeral Heartbeats & Expirations](./ttl_key_heap.webp)

Notice something subtle about `DeleteExpiredKeys`'s signature: it does **not** call `time.Now()` itself—it takes an explicit `cutoff time.Time` parameter. If three `etcd` nodes expired keys using their own local wall clocks, clock skew would cause them to expire keys at different points relative to incoming writes, diverging their trees and `CurrentIndex` values. We'll see in the next section how `etcd` solves this through Raft.

### Long-Polling Watches: `WatcherHub` and the `EventHistory` Ring Buffer

On Worker 3, `nginx` (driven by a template helper like `confd`) needs to learn immediately when `/services/web/web@1` disappears during Worker 1's reboot—without polling `etcd` in a tight loop. In `v0.4`, watches were implemented as **HTTP long-polling** ("hanging GET") requests:

```bash
curl "http://10.0.0.1:4001/v2/keys/services/web?wait=true&recursive=true&waitIndex=42"
```

Inside `store`, watches are managed by `watcherHub` ([`store/watcher_hub.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/watcher_hub.go#L19-L24)):

```go
// store/watcher_hub.go (etcd v0.4.9)
type watcherHub struct {
	mutex        sync.Mutex
	watchers     map[string]*list.List
	count        int64
	EventHistory *EventHistory
}
```

When no matching change has happened yet, [`watcherHub.watch()`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/watcher_hub.go#L41) allocates a buffered `EventChan` and parks the watcher in `watchers["/services/web"]`, leaving the HTTP request open. Thirty seconds after Worker 1 powers down for its OS update, `DeleteExpiredKeys` pops `web@1` at `CurrentIndex = 43` and calls [`WatcherHub.notify(e)`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/watcher_hub.go#L95). `notify` splits `e.Node.Key` (`/services/web/web@1`) on `"/"` and walks every ancestor prefix—`/`, `/services`, `/services/web`, `/services/web/web@1`—waking `confd`'s hanging GET with a JSON response:

```json
{
  "action": "expire",
  "node": { "key": "/services/web/web@1", "modifiedIndex": 43 },
  "prevNode": { "key": "/services/web/web@1", "value": "10.0.1.1:8080" }
}
```

Because each HTTP long-poll delivers only a **single** event and closes the connection, there is an inherent gap while `confd` reloads `nginx` and opens its next `?wait=true` request. During that exact window, `fleetd` reschedules `web@1` onto Worker 3 (`10.0.1.3:8081`, `CurrentIndex = 44`). If `etcd` only notified live watchers, `confd` would miss index `44`.

To bridge that gap, `watcherHub` maintains `EventHistory` ([`store/event_history.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/event_history.go#L12-L17) + [`store/event_queue.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/event_queue.go#L3-L9))—an in-memory **fixed-size ring buffer** initialized to **1,000 events** (`newWatchHub(1000)` in [`store/store.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/store.go#L80-L88)):

```go
// store/event_history.go & store/event_queue.go (etcd v0.4.9)
type EventHistory struct {
	Queue      eventQueue
	StartIndex uint64
	LastIndex  uint64
	rwl        sync.RWMutex
}

type eventQueue struct {
	Events   []*Event
	Size     int
	Front    int
	Back     int
	Capacity int // hardcoded to 1000 in newStore()
}
```

When `confd` reconnects with `?wait=true&recursive=true&waitIndex=44`, [`EventHistory.scan()`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/event_history.go#L44-L89) checks the ring buffer before parking the request:

1. **Future index (`waitIndex > LastIndex`):** Nothing to replay yet; park the watcher in `watchers["/services/web"]`.
2. **In-window index (`StartIndex <= waitIndex <= LastIndex`):** Jump directly to `(Queue.Front + int(waitIndex - StartIndex)) % 1000` and scan forward for the first matching event—immediately returning index `44` so `confd` catches up without missing a beat.
3. **Cleared index (`waitIndex < StartIndex`):** Over 1,000 mutations have occurred since the watcher last checked in, overwriting its slot in the ring buffer. `scan()` aborts with error `401` (`EcodeEventIndexCleared`: *"The event in requested index is outdated and cleared"*), forcing the client to do a full recursive `GET` to re-sync.

You can watch all three cases play out on a scaled-down 10-slot ring buffer—a live watch waking on `#1`, a quick reconnect replaying `#2` from history, and a burst of writes wrapping around to clear `#3`:

![Long-Polling Watches and the EventHistory Ring Buffer](./event_history_ring_buffer.webp)

Looking at the source comment right above `newWatchHub` in [`store/watcher_hub.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/watcher_hub.go#L26-L35) reveals the exact 2013 workload assumption baked into that number:

```go
// Typically, we only need to keep a small size of history[smaller than 20K].
// Ideally, it should smaller than 20K/s[max throughput] * 2 * 50ms[RTT] = 2000
```

For a quiet CoreOS cluster with dozens of keys and light heartbeat traffic, 1,000 events could cover minutes of history. Under a busy cluster, it would evaporate in milliseconds.

---

Pause and notice what we have built so far: a fast, clean, self-contained in-memory directory tree—sitting entirely inside volatile Go heap memory on a single machine. That immediately raises two questions we cannot put off any longer:

1. **Durability:** If `etcd-1` crashes or takes its turn rebooting under `locksmithd`, how does the tree survive?
2. **Consistency:** With three `etcd` nodes running concurrently, how do they agree on who won `locksmithd`'s CAS, keep `CurrentIndex` identical, and expire TTLs at the exact same moment?

## Making RAM Durable and Replicated: `goraft`, the Command Log, and JSON Snapshots

In `etcd v0.1 – v0.4`, durability and replication were not two separate layers—**Raft was the on-disk storage layer.** Specifically, early `etcd` embedded Ben Johnson's [`github.com/goraft/raft`](https://github.com/goraft/raft), one of the very first Go implementations of the [Raft consensus algorithm](https://raft.github.io/).

We won't detour into Raft's leader-election proofs or term safety here (for an interactive walkthrough of those mechanics, see [The Secret Lives of Data](https://thesecretlivesofdata.com/raft/)). For understanding `etcd`'s storage evolution, only one mental model matters: the **Replicated State Machine (RSM)**.

Every `etcd` node runs the exact same deterministic in-memory `store` we just inspected. Rather than replicating raw memory pages or key-value snapshots on every write, Raft replicates an **ordered, append-only log of commands** across the three nodes:

![How etcd's Replicated State Machine Handles a PUT Request](./replicated_state_machine.webp)

Walking through the five steps in the animation shows how `locksmithd`'s CAS request actually flows through `goraft`'s code path:

1. **Client PUT:** Worker 1 sends `PUT /v2/keys/coreos.com/updateengine/rebootlock/semaphore?prevIndex=5` to port `4001`. (If it hits a follower, `etcd` redirects or proxies the write to the leader.) The leader wraps the request in a [`CompareAndSwapCommand`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/v2/compare_and_swap_command.go#L16-L41) (`etcd:compareAndSwap`) and passes it to `raftServer.Do(cmd)`.
2. **Append Log:** Inside `goraft`'s [`leaderLoop`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L812), [`processCommand`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L902) creates a `LogEntry` (`#42`) and encodes the JSON command into the leader's local `/var/lib/etcd/log` file.
3. **Replicate:** Peer heartbeat goroutines replicate `#42` over port `7001` via `AppendEntries`; each follower appends the entry to its own `/var/lib/etcd/log` and replies with an acknowledgment.
4. **Commit & Reply:** Once a majority (2 of 3 nodes) has persisted `#42`, the leader advances `commitIndex`. [`Log.setCommitIndex()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/log.go#L331-L385) decodes the command and invokes `ApplyFunc` → `CompareAndSwapCommand.Apply()` → `store.CompareAndSwap(...)`. Only after the leader updates its in-memory `store` and wakes `WatcherHub` does it return HTTP `200 OK` (with `modifiedIndex: 42`) to Worker 1.
5. **Followers Apply:** Once followers receive the updated `commitIndex`, each runs the exact same `Log.setCommitIndex()` → `store.CompareAndSwap(...)` path against its own RAM tree. If Worker 2 concurrently sent `prevIndex=5`, its command lands at a later log index, applies after Worker 1's, and deterministically fails with `101: Compare failed` on every replica.

Because every node starts from the same empty `/` and applies the same committed log of commands in the same order, every replica arrives at the exact same in-memory tree, the exact same `CurrentIndex`, and the exact same CAS winners—and if a node reboots, it recovers its RAM state from disk.

### Deterministic TTL Expiration via `SyncCommand`

That same command-log mechanism also answers our cliffhanger from the previous section: **how do three independent nodes expire TTLs deterministically without trusting local wall clocks?**

In [`server/peer_server.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/server/peer_server.go#L792-L805), the Raft leader runs a 500 ms background ticker (`monitorSync`) that proposes a `SyncCommand` carrying the *leader's* timestamp right into the Raft log:

```go
// server/peer_server.go (etcd v0.4.9)
func (s *PeerServer) monitorSync() {
	ticker := time.NewTicker(time.Millisecond * 500)
	defer ticker.Stop()
	for {
		select {
		case <-s.closeChan:
			return
		case now := <-ticker.C:
			if s.raftServer.State() == raft.Leader {
				s.raftServer.Do(s.store.CommandFactory().CreateSyncCommand(now))
			}
		}
	}
}
```

When each replica commits and applies that `etcd:sync` log entry ([`store/v2/sync_command.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/v2/sync_command.go#L14-L28)), it passes the leader's serialized `c.Time` straight into `s.DeleteExpiredKeys(c.Time)`. Every node pops the exact same expired nodes from its `ttlKeyHeap` at the exact same point in the log, bumping `CurrentIndex` identically.

Notice the subtle storage side effect: **even a completely idle `etcd v0.4` cluster writes two `etcd:sync` commands per second into the Raft log**—roughly 172,800 log entries per day.

### Log Compaction and Full-Tree JSON Snapshots

An append-only command log cannot grow forever. Without compaction, `/var/lib/etcd/log` would eventually fill the disk—and restarting a node would mean replaying millions of historical mutations from index 1 just to reconstruct a 50 KB tree.

Raft solves unbounded log growth with **snapshotting**: periodically capture the entire state machine's current state to disk at some committed log index `L`, then discard all log entries up to `L`. That gives `/var/lib/etcd/` in `etcd v0.4` its remarkably sparse on-disk layout—no database files, no page caches, no indexes, just three things:

```text
/var/lib/etcd/
├── conf                  # Raft peer configuration metadata
├── log                   # Single append-only Raft command log
└── snapshot/
    └── <term>_<index>.ss # Periodic CRC32-prefixed JSON dump of the entire store
```

In `etcd v0.4.9`, `PeerServer.monitorSnapshot()` ([`server/peer_server.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/server/peer_server.go#L772-L790)) wakes up every 3 seconds and checks whether `CommitIndex - lastSnapshotIndex` exceeds `snapshot_count` (default **`10000`** entries—which, thanks to the 500 ms `SyncCommand`, happens at least every ~83 minutes even with zero user writes). When it crosses that threshold, it calls [`raftServer.TakeSnapshot()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L1188-L1241):

1. **Stop-the-world clone + JSON serialization ([`store.Save()`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/store.go#L620-L639)):**
   `goraft` asks the state machine (`store`) to serialize itself:

   ```go
   // store/store.go (etcd v0.4.9)
   func (s *store) Save() ([]byte, error) {
   	s.worldLock.Lock()

   	clonedStore := newStore()
   	clonedStore.CurrentIndex = s.CurrentIndex
   	clonedStore.Root = s.Root.Clone()
   	clonedStore.WatcherHub = s.WatcherHub.clone()
   	clonedStore.Stats = s.Stats.clone()
   	clonedStore.CurrentVersion = s.CurrentVersion

   	s.worldLock.Unlock()

   	b, err := json.Marshal(clonedStore)
   	if err != nil {
   		return nil, err
   	}
   	return b, nil
   }
   ```

   Look closely at what happens here. To avoid holding `worldLock` during slow JSON encoding, `store.Save()` first takes the **exclusive `worldLock.Lock()`**—blocking every read and write—and performs a **full recursive deep copy** of all `N` nodes in [`Root.Clone()`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/node.go#L355-L367), plus `EventHistory` and `Stats`. Only after allocating a second copy of the entire keyspace in RAM does it release `worldLock` and run `json.Marshal(clonedStore)` over the clone.

2. **Double-encoded snapshot file ([`goraft/raft/snapshot.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/snapshot.go#L55-L86)):**
   `goraft`'s `Snapshot.save()` wraps those `state` JSON bytes inside an outer `Snapshot{LastIndex, LastTerm, Peers, State}` struct, runs `json.Marshal(ss)` a *second* time (which base64-encodes `State []byte` inside the outer JSON envelope!), writes an 8-character CRC32 checksum followed by the payload to `snapshot/<term>_<index>.ss`, calls `file.Sync()`, and deletes the previous snapshot file:

   ```text
   # /var/lib/etcd/snapshot/1_10001.ss
   a3f9c210                                           ◄── 8-char IEEE CRC32 checksum
   {
     "lastIndex": 10001, "lastTerm": 1,
     "peers": [{"name": "etcd-1", "connectionString": "http://10.0.0.1:7001"}, ...],
     "state": "eyJSb290Ijp7IlBhdGgiOiIvIiwiQ2hpbGRyZW4iOnsi..."  ◄── base64(json(store))
   }
   ```

3. **Log rewrite and truncation ([`goraft/raft/log.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/log.go#L568-L624)):**
   With the snapshot safely synced, `goraft` keeps a 200-entry safety tail ([`NumberOfLogEntriesAfterSnapshot = 200`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L34)) so slightly lagging followers can still catch up via `AppendEntries` instead of transferring a full snapshot. It calls `s.log.compact()`, which locks `Log.mutex`, writes those surviving tail entries into `log.new`, calls `file.Sync()`, and atomically `os.Rename`s `log.new` over `log`.

4. **Crash recovery ([`store.Recovery()`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/store.go#L645-L658)):**
   When a node restarts, it reads the latest `<term>_<index>.ss` file, `json.Unmarshal`s the tree back into RAM, walks every node via [`Root.recoverAndclean()`](https://github.com/etcd-io/etcd/blob/v0.4.9/store/node.go#L376-L389) to reconstruct the fields that JSON could not encode (`Parent` pointers marked `json:"-"` and the unexported `ttlKeyHeap`), and replays whatever entries remain in `/var/lib/etcd/log`.

Every step of that pipeline is dead simple to reason about—and scales strictly as **`O(N)` in the total size of the tree**, in RAM, CPU, and disk I/O.

## Why It Fit 2013—and Where the Cracks Appeared

Judged against the 2013 CoreOS Container Linux workload, `etcd v0.1 – v0.4` was a pragmatic piece of engineering. It shipped as a single static Go binary with zero external dependencies, gave operators a familiar filesystem mental model they could inspect with `curl`, served reads in microseconds straight from RAM, and recovered state from plain files in `/var/lib/etcd/`. When a cluster only coordinated a few dozen keys across `fleet`, `locksmith`, and `confd`, that simplicity got CoreOS into users' hands fast.

Yet as clusters moved from early prototypes into production deployments in 2014, **`goraft`—the consensus and persistence engine sitting underneath `store`—started showing serious cracks**, splitting cleanly into **architectural issues** and **performance issues**.

### 1. Architectural Issues: Monolithic Coupling and Persistence Hazards

Inside [`third_party/github.com/goraft/raft/`](https://github.com/etcd-io/etcd/tree/v0.4.9/third_party/github.com/goraft/raft), `goraft`'s [`server`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L111-L150) struct bundled every layer of a distributed system into one stateful object:

- **Network transport:** Direct HTTP client/server calls ([`http_transporter.go`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/http_transporter.go)) and per-peer background goroutines,
- **Timers and goroutine lifecycles:** Wall-clock `time.Tick` / `time.After` channels driving [`leaderLoop`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L817), [`followerLoop`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L669), and [`candidateLoop`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L731),
- **Disk I/O:** Direct `os.File` seeks, writes, renames, and `fsync` calls embedded inside [`Log`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/log.go) and [`Snapshot.save()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/snapshot.go#L55-L86), and
- **Synchronous state-machine execution:** [`Log.setCommitIndex()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/log.go#L331-L385) decoded each entry and invoked `l.ApplyFunc(entry, command)` synchronously *while holding `Log.mutex.Lock()`*.

Consensus protocols live or die by how they behave in rare, adversarial corners: asymmetric network partitions, dropped or reordered RPCs, abrupt leader step-downs, and partial disk writes. Because `goraft` tangled live sockets, wall-clock timers, coarse mutexes, and `os.File` handles directly into the protocol state machine, **deterministic unit testing was virtually impossible**. Every edge case had to be reproduced through timing-dependent multi-goroutine tests, making subtle split-brain and cluster-membership bugs painful to isolate and fix.

On disk, the persistence format carried its own correctness hazards:

- **Unchecksummed log entries:** While `.ss` snapshot files prepended a CRC32 checksum, `/var/lib/etcd/log` had no per-entry integrity check at all. [`LogEntry.Encode()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/log_entry.go#L72-L83) wrote an 8-character ASCII hex length followed by raw protobuf bytes (`fmt.Fprintf(w, "%8x\n", len(b))` + `w.Write(b)`). Silent bitrot or a corrupted sector inside the log went undetected during replay so long as the bytes happened to unmarshal as valid protobuf.
- **Racy snapshot boundaries:** Even [`server.TakeSnapshot()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L1188-L1218) carried a candid `TODO` right in `etcd v0.4.9`'s production code:

  ```go
  // third_party/github.com/goraft/raft/server.go (etcd v0.4.9)
  func (s *server) TakeSnapshot() error {
  	// ...
  	// TODO: acquire the lock and no more committed is allowed
  	// This will be done after finishing refactoring heartbeat
  	s.debugln("take.snapshot")

  	lastIndex, lastTerm := s.log.commitInfo()
  	// ...
  	state, err := s.stateMachine.Save()
  ```

  Because `TakeSnapshot()` read `lastIndex` *before* calling `s.stateMachine.Save()` without blocking concurrent commits, new mutations could apply to `store` in the gap—producing a snapshot file whose serialized `State` had already advanced beyond its recorded `LastIndex`.

### 2. Performance Issues: Timer-Polled Replication, Unbatched Log I/O, and Compaction Stalls

Even on a completely healthy network, `goraft`'s write and compaction path left a surprising amount of performance on the table.

Start with **steady-state writes**—before log compaction ever runs. Two bottlenecks shaped throughput and latency across client concurrency levels:

1. **50 ms timer-polled, stop-and-wait replication:** Look closely at [`server.processCommand()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/server.go#L907-L926) on the leader: after appending a client's command to `/var/lib/etcd/log`, it returns immediately **without signaling any peer replication goroutines**. Instead, each follower's [`Peer.heartbeat()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/peer.go#L138-L182) loop sleeps on a `50 ms` `time.Tick` (`DefaultHeartbeatInterval = 50 * time.Millisecond`) before calling `p.flush()`, and [`sendAppendEntriesRequest()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/peer.go#L189-L250) blocks synchronously until that HTTP request completes. Even with near-zero local network latency, a single request waits ~25 ms on average for the next tick—and back-to-back sequential `PUT`s phase-lock right onto the `50 ms` interval, throttling a single writer to ~20 writes/sec.
2. **Unbatched per-entry syscalls on the log:** Under concurrent client load, [`Log.appendEntry()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/log.go#L502-L533) serializes appends one entry at a time under `Log.mutex.Lock()`. Every single command triggers a `file.Seek(0, os.SEEK_CUR)` syscall plus **two unbuffered `write()` syscalls** (`fmt.Fprintf` for the hex length header and `file.Write` for the JSON-wrapped-in-Protobuf entry), while leader commits call `s.log.sync()` and execute state-machine mutations synchronously under the same coarse lock.

Benchmarking steady-state `/v2/keys` writes across increasing client concurrency (`c = 1` through `256`) on a 3-node `etcd v0.4.9` cluster (reproducible via [`../benchmarks/part1_v04/run.sh`](../benchmarks/part1_v04/run.sh) using 1 dedicated `cpuset`-pinned core per node, `tmpfs` volumes to isolate Raft replication and locking from single-host disk contention, and direct-to-leader HTTP `keep-alive` `PUT`s over `1,000` keys × `256 B` values) exposes both limits directly:

![etcd v0.4.9 Steady-State Write Throughput](./v04_write_throughput.png)

At `c = 1`, back-to-back sequential writes phase-lock straight onto `goraft`'s `50 ms` `Peer.heartbeat()` interval (`p50 = 49.7 ms`, `p99 = 52.8 ms`), capping throughput at **`22.1 writes/s`**. Raising concurrency allows multiple client appends to accumulate in `/var/lib/etcd/log` during the same heartbeat sleep and ride the next `AppendEntries` flush together, lifting throughput steadily through **`87.1 writes/s` (`c = 4`)**, **`317 writes/s` (`c = 16`)**, **`636 writes/s` (`c = 32`)**, **`1,283 writes/s` (`c = 64`)**, and **`2,530 writes/s` (`c = 128`)**. By **`c = 256`**, however, the curve bends below the dashed ideal linear line at **`4,755 writes/s`** (`215×` the `c = 1` rate for `256×` concurrency) as concurrent writers saturate the leader's single core behind `Log.mutex` and unbatched per-entry `Seek`/`Write` syscalls.

![etcd v0.4.9 Steady-State Write Latency](./v04_write_latency.png)

Per-request latency makes both mechanisms unmistakable. Across the entire sweep from `c = 1` to `c = 256`, median latency sits dead-flat on the **`50 ms` heartbeat line** (`49.4–51.0 ms`). Meanwhile, `p99` tail latency climbs steadily as batches grow—from **`53 ms` (`c = 1`)** through **`58 ms` (`c = 32`)**, **`63 ms` (`c = 64`)**, and **`79 ms` (`c = 128`)** up to **`117 ms` (`c = 256`)**, spilling past two full heartbeat cycles as writers queue behind serialized log appends and commits.

Those steady-state numbers hold only while `/var/lib/etcd/log` appends uninterrupted. Every `10,000` commits (`snapshot_count`), `goraft` also introduces a **third bottleneck** into the write path:

3. **Stop-the-world snapshot & log-rewrite stalls:** When `PeerServer.monitorSnapshot()` crosses the `10,000`-entry threshold and calls `TakeSnapshot()`, `store.Save()` acquires the exclusive `worldLock` to deep-clone the tree, marshals it to JSON twice (base64-encoding the inner JSON into an outer `.ss` file), and `fsync`s the snapshot. Immediately afterward, [`Log.compact()`](https://github.com/etcd-io/etcd/blob/v0.4.9/third_party/github.com/goraft/raft/log.go#L568-L624) acquires the exclusive `Log.mutex.Lock()`, opens `log.new`, re-encodes surviving tail entries to disk, calls `file.Sync()`, and atomically `os.Rename`s `log.new` over `/var/lib/etcd/log`—stalling in-flight appends and commits until the rewrite finishes.

## Looking Ahead to Part 2

By late 2014, the CoreOS team recognized that `goraft`'s architectural tangles and write-path bottlenecks could not be solved with incremental patches. Turning `etcd` into a rock-solid, production-grade coordination service meant rebuilding its consensus engine, on-disk write-ahead storage, and peer replication from the ground up—making state transitions deterministic and unit-testable, protecting every persisted record against corruption, and removing the timer-polling and syscall stalls on the write path.

That clean-sheet effort shipped in January 2015 as **`etcd v2.0`**. In **Part 2**, we'll open up `etcd v2`'s redesigned consensus and storage architecture, put it through the exact same 3-node benchmark to see how much changed, and follow what happened when rapid production adoption pushed `etcd` onto a much bigger stage.
