# History of CoreOS & Its Relationship to Kubernetes

Research notes on why **CoreOS** was founded in 2013, how **Container Linux** led to **`etcd`**, and how CoreOS's cluster tooling both enabled and pivoted toward **Kubernetes**.

---

## 1. Origins: "Google's Infrastructure for Everyone Else" (2013)

* **Founding:** CoreOS was founded in **2013** (Y Combinator S13) by **Alex Polvi**, **Brandon Philips**, and **Michael Marineau**.
* **The Problem They Saw:** Traditional server Linux distributions (Ubuntu, CentOS, RHEL) assumed long-lived, manually configured "pet" servers patched live via `apt` or `yum`, causing configuration drift, dependency conflicts, and fragile upgrades. Meanwhile, hyperscalers like Google ran fleets of uniform, disposable servers ("cattle") orchestrated as a single cluster where workloads ran in containers.
* **CoreOS Container Linux (originally CoreOS Linux):**
  * Built from a **ChromiumOS / ChromeOS** (Gentoo-based SDK) lineage, bringing consumer-grade automatic updates to servers.
  * **Minimalist, container-only host:** Shipped only the Linux kernel, `systemd`, and a container runtime (initially Docker, later also `rkt`)—with **no traditional package manager** (`apt`/`yum`).
  * **Dual-partition A/B immutable updates:** Root A / Root B partitions allowed `update_engine` to download and apply OS updates silently in the background to the passive partition, flip the boot flag on reboot, and automatically roll back if the new image failed to boot.

---

## 2. How Container Linux Created `etcd` (and the Early CoreOS Stack, 2013–2014)

Once servers are minimal, immutable, and **automatically rebooting themselves** for OS updates, you immediately need distributed coordination:

* **[`etcd`](https://github.com/etcd-io/etcd) (2013):** Created as a lightweight, strongly consistent **"distributed `/etc`"** (Unix `/etc` + `d` for distributed/daemon) backed by Raft consensus, avoiding heavy JVM dependencies like Apache ZooKeeper.
* **[`locksmith`](https://github.com/coreos/locksmith) (2013–2014):** Used `etcd` as a distributed semaphore/lock so nodes in a cluster rebooted sequentially during automatic OS updates instead of taking down the whole cluster at once.
* **[`fleet`](https://github.com/coreos/fleet) (2014):** A "distributed `init` system" tying `systemd` and `etcd` together so operators could schedule units/containers across a cluster of CoreOS machines.
* **[`flannel`](https://github.com/flannel-io/flannel) (2014):** A lightweight Layer 3 container overlay network allocating per-host subnets and storing network state in `etcd`.
* **Quay (acquired 2014):** CoreOS acquired Quay.io (founded by Jake Moshenko and Joey Schorr) and launched *Quay Enterprise* (now open-sourced as [`quay/quay`](https://github.com/quay/quay)), followed by **[`Clair`](https://github.com/quay/clair)** (2015) for layer-by-layer container CVE scanning.

---

## 3. CoreOS & Kubernetes: From Symbiosis to Full Pivot (2014–2017)

### Mid-2014: Kubernetes Chooses `etcd`
* When Google open-sourced **Kubernetes** in mid-2014 (inspired by Borg and Omega), it needed a strongly consistent, easy-to-embed cluster state store and chose CoreOS's **`etcd`** as its control-plane database.
* Early Kubernetes clusters routinely ran on **CoreOS Container Linux**, using **`flannel`** for pod networking and **`etcd`** for state.

### Dec 2014 – 2015: `rkt`, Standards Wars & Tectonic
* **[`rkt`](https://github.com/rkt/rkt) ("Rocket", late 2014):** Concerned that Docker was becoming a monolithic, root-privileged daemon, CoreOS launched `rkt` and the `appc` spec with pod-native, rootless-friendly, cryptographically verified execution. While `containerd`/`runc` eventually won the runtime market (and `rkt` development ended by 2020), the "container wars" catalyzed the **Open Container Initiative (OCI)** (2015) and Kubernetes's Container Runtime Interface (CRI).
* **Tectonic (April 2015):** Recognizing that Kubernetes was far more capable than `fleet` for full container orchestration, CoreOS raised $12M led by Google Ventures ([TechCrunch, Apr 6, 2015](https://techcrunch.com/2015/04/06/coreos-raises-12m-funding-round-led-by-google-ventures-to-bring-kubernetes-to-the-enterprise/)) and launched **Tectonic**—an enterprise distribution built on pure upstream Kubernetes, Container Linux, `etcd`, and **[`Dex`](https://github.com/dexidp/dex)** (OIDC identity broker).

### 2016–2018: Deprecating `fleet` & Inventing Kubernetes Operators
* **Deprecating `fleet` (Dec 2016 – Feb 2018):** CoreOS shipped `fleet v1.0.0` in December 2016 as its final feature release, formally deprecated it, ended Container Linux support for it after **February 1, 2018**, and explicitly pointed users to **Kubernetes** in the [`coreos/fleet` README](https://github.com/coreos/fleet).
* **Co-designing `etcd v3` for Kubernetes (June 2016):** CoreOS rewrote `etcd`'s storage engine around BoltDB (`bbolt`), MVCC revisions, gRPC watch streams, and leases specifically to solve Kubernetes's scaling bottlenecks with `etcd v2` (see [etcd_storage_history.md](file:///Users/frosner/Documents/outpourings/bbolt_etcd/etcd_storage_history.md)).
* **Introducing Kubernetes Operators (November 2016):** CoreOS CTO Brandon Philips introduced the **Operator pattern** ([coreos.com/blog/introducing-operators.html](https://coreos.com/blog/introducing-operators.html), archived on Red Hat's blog: [Introducing Operators: Putting Operational Knowledge into Software](https://www.redhat.com/en/blog/introducing-operators-putting-operational-knowledge-into-software))—encoding human operational knowledge (backups, failovers, upgrades) into Kubernetes controllers via custom resources, starting with the **etcd Operator** and **[Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator)**.

---

## 4. Red Hat Acquisition & Long-Term Legacy (2018–2020+)

* **Red Hat Acquires CoreOS (January 30, 2018):** Red Hat acquired CoreOS for **$250 million** ([Red Hat Press Release](https://www.redhat.com/en/about/press-releases/red-hat-acquire-core-os-expanding-its-kubernetes-and-containers-leadership), [TechCrunch](https://techcrunch.com/2018/01/30/red-hat-acquires-coreos-for-250-million-in-kubernetes-expansion/), [Forbes](https://www.forbes.com/sites/janakirammsv/2018/01/30/red-hat-acquires-coreos-for-250-million/)).
  * **Tectonic** and the **Operator Framework** were folded into **Red Hat OpenShift** (unveiled at KubeCon Europe / Red Hat Summit, May 2018).
  * **Container Linux**'s immutable OS architecture became **Red Hat Enterprise Linux CoreOS (RHCOS)** for OpenShift 4.
* **Container Linux EOL (May 26, 2020):** CoreOS Container Linux reached End-of-Life on **May 26, 2020**, succeeded by:
  * **Fedora CoreOS** (official Red Hat/Fedora successor)
  * **Flatcar Container Linux** (community/independent fork continuing the Container Linux lineage)
* **Cloud-Native Foundations:** `etcd` (CNCF Graduated Nov 2020), `flannel`, `Quay`, `Clair`, `Dex`, `Prometheus Operator`, and the **Operator** pattern all originated from CoreOS's 2013–2017 push to make clustered container infrastructure automated by default.

---

## 5. Primary & Reference Links

* **Tectonic / Google Ventures round (Apr 6, 2015):** https://techcrunch.com/2015/04/06/coreos-raises-12m-funding-round-led-by-google-ventures-to-bring-kubernetes-to-the-enterprise/
* **Introducing Operators (Brandon Philips, Nov 2016):**
  * Original URL: https://coreos.com/blog/introducing-operators.html
  * Red Hat mirror: https://www.redhat.com/en/blog/introducing-operators-putting-operational-knowledge-into-software
* **Red Hat acquires CoreOS ($250M, Jan 30, 2018):**
  * Press release: https://www.redhat.com/en/about/press-releases/red-hat-acquire-core-os-expanding-its-kubernetes-and-containers-leadership
  * TechCrunch: https://techcrunch.com/2018/01/30/red-hat-acquires-coreos-for-250-million-in-kubernetes-expansion/
  * Forbes: https://www.forbes.com/sites/janakirammsv/2018/01/30/red-hat-acquires-coreos-for-250-million/
* **CoreOS Open-Source Repositories:**
  * `fleet` (deprecated in favor of Kubernetes): https://github.com/coreos/fleet
  * `locksmith`: https://github.com/coreos/locksmith
  * `flannel`: https://github.com/flannel-io/flannel
  * `rkt`: https://github.com/rkt/rkt
  * `quay`: https://github.com/quay/quay
  * `clair`: https://github.com/quay/clair
  * `dex`: https://github.com/dexidp/dex
  * `prometheus-operator`: https://github.com/prometheus-operator/prometheus-operator
* **Related research notes:**
  * [bbolt_history.md](file:///Users/frosner/Documents/outpourings/bbolt_etcd/bbolt_history.md)
  * [etcd_storage_history.md](file:///Users/frosner/Documents/outpourings/bbolt_etcd/etcd_storage_history.md)
