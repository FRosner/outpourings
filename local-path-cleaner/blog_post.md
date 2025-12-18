---
title: Addressing the Shortcomings of Local Path Provisioner in Kubernetes
published: false
description: 
tags: kubernetes, cloud, devops, infrastructure
cover_image: 
---

## Temporary Storage in Kubernetes

In Kubernetes, containers are ephemeral and stateless by default, allowing for easy scaling and management. Some workloads might require storage for temporary files, however. In vanilla Kubernetes, you are presented with the following options:

- Mount an `emptyDir` volume, which will be created on the node where the pod is scheduled. It can either be backed by the node's default disk or the node's memory (`tmpfs`). Some cloud providers also offer `emptyDir` backed by local SSDs based on the node type. However, you cannot customize the mount point on the node for `emptyDir` volumes, which means less flexibility.
- Mount a `hostPath` volume which allows you to specify a custom mount point on the node. This is not recommended for most application due to security risks as it allows mounting arbitrary paths on the node. Also, each pod is "responsible" for mounting the right path to avoid conflicts between pods. There is no separation.
- Mount a `local` volume, which is backed by a statically provisioned local PV. When configured correctly, this approach avoids scheduling issues if your pod is supposed to get the same local data back when it is rescheduled. However, you have to manually create the PVs and manage them, which makes `local` volumes impractical for most production use cases.

While most workloads might be fine with `emptyDir` for storing temporary data, some applications have specific I/O requirements, such as configuring the filesystem in a certain way or choosing a certain RAID configuration for optimal performance. Think of databases or caches.

We need a way to dynamically provision local storage, securely, conflict-free, mounted to the specific path on the node that is mounted to a fast local disk. Ideally, we want to avoid scheduling problems and enforce capacity limits. Additionally, `emptyDir` will be wiped if the pod gets deleted, so we cannot reuse the volume even if the node still exists. This can be inconvenient if you want to reuse the state of your application after a rolling restart, for example.

Local path provisioner provides a way to mount local storage as persistent volumes in Kubernetes dynamically. It checks many of the boxes we are looking for. Let's take a closer look.

## How Does Local Path Provisioner Work?

[Local path provisioner](https://github.com/rancher/local-path-provisioner) is a Go application that can be installed in your Kubernetes cluster, e.g. via Helm. Based on your configuration, it will create either `hostPath` or `local` based PVs on the node automatically.

After installing the chart in your cluster, you will have access to the `local-path` storage class. To utilize it, you could create a `StatefulSet` with the respective volume claim template:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: volume-test
spec:
  serviceName: "test"
  replicas: 2
  selector:
    matchLabels:
      app: volume-test
  template:
    metadata:
      labels:
        app: volume-test
    spec:
      containers:
      - name: test-container
        image: busybox
        command: ['sh', '-c', 'echo "Test $(hostname)" > /data/test && sleep 3600']
        volumeMounts:
        - mountPath: /data
          name: local-storage
  volumeClaimTemplates:
  - metadata:
      name: local-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: local-path
      resources:
        requests:
          storage: 128Mi
```

After creating the `StatefulSet` resource, the following events will unfold:

1. The `StatefulSet` controller processes the first replica, creating the PVC and pod based on the template, setting the owner references, and mounting the PVC in the pod. Both resources will be `Pending`.
2. The PVC control loop detects an unbound PVC, matches the storage class `local-path` to the provisioner `rancher.io/local-path` and triggers dynamic provisioning since no matching PV exists.
3. Local path provisioner watches PVC events via the Kubernetes API. If the provisioner is configured with `volumeBindingMode: WaitForFirstConsumer` (default), it will defer the PV binding to pod scheduling. This is useful because there might be other constraints in your pods such as node selectors, or resource requests, which could result in unschedulable pods if the PV is bound to the wrong node.
4. The scheduler schedules the pod to a node and the PVC is annotated with `volume.kubernetes.io/selected-node`, indicating the selected node to the PVC binding controller.
5. The local path provisioner receives the PVC event, reads the `selected-node` annotation and creates a PV on the selected node using `hostPath` (default) in a node specific path, with a pod specific sub-path, avoiding conflicts. This is done via a helper pod that launches a container on the node to do the mounting. The PVC is then bound to the PV.
6. Kubelet observes that the PVC is fully bound, pulls the container image (if needed), mounts the host dir to the container and starts it.
7. The `StatefulSet` controller processes the second replica, similar to the first replica.

With the default configuration, if both replicas were to be scheduled on the same node, the layout on the node would look like this:

```
/opt/local-path-provisioner/
├── pvc-<uuid>_local-storage_volume-test_default_local-storage-volume-test-0/
│   └── test
└── pvc-<uuid>_local-storage_volume-test_default_local-storage-volume-test-1/
    └── test
```

When the PVC is deleted (and the reclaim policy is `Delete`), the PV will be deleted as well. The provisioner will detect this and clean up the host directory by scheduling another helper pod.

## What are the Limitations of Local Path Provisioner?

While local path provisioner addresses the main shortcomings of `emptyDir`, `local` and `hostPath` by dynamically and securely provisioning local volumes on nodes in a conflict-free manner, it comes with a few limitations of its own.

First, if a node with a bound `local-path` PV gets removed from the cluster, the provisioner cannot schedule the helper pod to unmount the PV upon PVC deletion, and thus the PV remains "stuck" until manually deleted (see [#215](https://github.com/rancher/local-path-provisioner/issues/215)).

While orphaned PVs are a minor inconvenience, the second issue is more severe: Since `local-path` PVCs are tied to a node, but the lifecycle of a PVC in a `StatefulSet` is decoupled from the pod lifecycle, pods can become unschedulable if recreated, because node selected for the PVC is not part of the cluster anymore, full, or otherwise unsuitable for scheduling. This leads to service outage, with pods stuck in `Pending` phase until the PVC is deleted manually.

Thirdly, while Kubernetes allows you to specify storage limits for PVCs, local path provisioner does not enforce them. This can lead to overcommitting resources causing unexpected out of disk errors in the applications.

Luckily, there are different buildings blocks we can combine to address these issues: [Local ephemeral storage](https://kubernetes.io/docs/concepts/storage/ephemeral-storage/), [filesystem quotas](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/storage_administration_guide/xfsquota), [generic ephemeral volumes](https://kubernetes.io/docs/concepts/storage/ephemeral-volumes/#generic-ephemeral-volumes), and a custom application I call local path cleaner. Let's dive into the details.

## Local Ephemeral Storage

The concept of local ephemeral storage was introduced in 2017 (v1.7) and [reached GA](https://kubernetes.io/blog/2022/09/19/local-storage-capacity-isolation-ga/) in 2022 (v1.25). This means you can specify storage requests (and limits) in your container specification:

```yaml
containers:
- name: test-container
  image: busybox
  command: ['sh', '-c', 'echo "Test $(hostname)" > /data/test && sleep 3600']
  resources:
    requests:
      ephemeral-storage: "5Gi"
  volumeMounts:
  - mountPath: /data
    name: local-storage
```

The scheduler will take storage requirements into account when scheduling pods. We can use this to avoid overcommitting local storage on a node. However, local ephemeral storage and persistent volumes serve different purposes (one is ephemeral, the other persistent). Kubernetes does not track PVC volumes as ephemeral storage consumption so we cannot combine local ephemeral storage requests and `local-path` PVCs out of the box.

Luckily, with a trick during node provisioning, we can still achieve what we are looking for. Let's consider GCP as an example. In our startup script, we might manually mount multiple local NVMe SSD in a RAID0 device:

```bash
# Find all SSDs
SSDs=($(readlink -f /dev/disk/by-id/google-local-nvme-ssd-*))

# Create RAID0 device
mdadm --create /dev/md0 \
  --level=0 --force \
  "--raid-devices=$${#SSDs[@]}" \
  "$${SSDs[@]}"

# Format RAID0 device
mkfs.xfs -s size=4096 /dev/md0

# Mount RAID0 device to /mnt/disks/ssd-array
mkdir -p /mnt/disks/ssd-array
mount /dev/md0 /mnt/disks/ssd-array
chmod a+w /mnt/disks/ssd-array

# Create fstab entry (to survive reboots)
raid_dev_uuid=$(blkid | grep dev/md0 | egrep -o '[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}')
echo "UUID=$raid_dev_uuid /mnt/disks/ssd-array xfs defaults,nofail,noatime 0 0" |\
  tee -a /etc/fstab
  
# Disable NODE_LOCAL_SSDS_EPHEMERAL as we manage ephemeral storage ourselves
sed -i 's|readonly NODE_LOCAL_SSDS_EPHEMERAL=true|readonly NODE_LOCAL_SSDS_EPHEMERAL=false|' \
  "$${KUBE_HOME}/kube-env"
```

Kubelet tracks ephemeral storage in certain locations. By bind mounting these into our RAID0 mount, we effectively enable Kubernetes to track the capacity of our custom local storage.

```bash
mkdir -p /mnt/disks/ssd-array/lib/kubelet
mv /var/lib/kubelet/* /mnt/disks/ssd-array/lib/kubelet
mount --bind /mnt/disks/ssd-array/lib/kubelet /var/lib/kubelet

mkdir -p /mnt/disks/ssd-array/lib/containerd
mv /var/lib/containerd/* /mnt/disks/ssd-array/lib/containerd
mount --bind /mnt/disks/ssd-array/lib/containerd /var/lib/containerd

mkdir -p /mnt/disks/ssd-array/stateful_partition
mount --bind /mnt/disks/ssd-array/stateful_partition /mnt/stateful_partition
```

Alternatively, we could hard code the available ephemeral storage capacity in the kubelet config based on the available space on the RAID0 device. This would allow the scheduler to take storage requests into account for your `local-path` PVs. If you wanted it to be 500Gi, you could run:

```bash
sed -i -E 's/(ephemeral-storage:).*/\1 500Gi/' /home/kubernetes/kubelet-config.yaml
```

When querying the node capacity, you should see the ephemeral storage capacity reflected:

```yaml
status:
  capacity:
    cpu: "16"
    ephemeral-storage: 500Gi
    memory: 128Gi
    pods: "110"
```

Now all we need to do is tell local path provisioner to use our custom mount point instead of the default `/opt/local-path-provisioner`. We can do this by customizing the `ConfigMap` via Helm:

```yaml
nodePathMap:
  - node: DEFAULT_PATH_FOR_NON_LISTED_NODES
    paths:
      - /mnt/disks/ssd-array/
```

If setup correctly, this should prevent Kubernetes from overcommitting `local-path` PVCs on a node. I admit that this is a bit of a hacky solution with two drawbacks: First, you have to specify the requested storage capacity in two places: In the PVC and in the pod spec. Second, you are repurposing the local ephemeral storage concept, which might cause confusion in larger organizations where many teams share the same multi-tenant Kubernetes cluster.  

If you wanted to avoid overcommitting without ephemeral storage requests, you could try to align CPU and memory requests with the expected storage usage. Either way, once you have the overcommitting problem under control, we can move to enforcing the storage limits.

## Filesystem Quotas

By default, containers that have a `local-path` PVC mounted, can use as much space in the volume as they want, independently of the space they requested. This can lead to unexpected out of disk errors in the applications. Note that by requested space we are referring to the storage requests of the PVC, not the ephemeral storage requests of the container.

Fortunately, filesystems such as XFS support configuring storage quotas. There is an excellent [minimal example](https://github.com/rancher/local-path-provisioner/blob/964c10d96f3098b3d8c0efc9db7e8ad253097ec9/examples/quota/setup#L1-L29) in the local path provisioner repository.

```bash
#!/bin/sh

xfsPath=$(dirname "$VOL_DIR")
pvcName=$(basename "$VOL_DIR")

mkdir -p "$VOL_DIR"

type=`stat -f -c %T ${xfsPath}`
if [ ${type} == 'xfs' ]; then
    project=`cat /etc/projects | tail -n 1`
    id=`echo ${project%:*}`

    if [ ! ${project} ]; then
        id=1
    else
        id=$[${id}+1]
    fi

    echo "${id}:${VOL_DIR}" >> /etc/projects
    echo "${pvcName}:${id}" >> /etc/projid

    xfs_quota -x -c "project -s ${pvcName}"
    xfs_quota -x -c "limit -p bhard=${VOL_SIZE_BYTES} ${pvcName}" ${xfsPath}
    xfs_quota -x -c "report -pbih" ${xfsPath}
fi
```

The script first checks if the filesystem is XFS. If not, we simply exit. Then, it reads the project file to determine if there are any existing projects so we can pick the next project ID. Project files look like this:

```text
1:/some/path
2:/another/path
```

We then increment the last project ID and create a new project for our PVC. Finally, we initialize the quota record for the project, set the limit, and print a report for debugging purpose. 

We can then pass this script via the Helm value `configmap.setup`. To avoid inconsistencies, it's wise to write a corresponding script for `configmap.teardown` that removes the quota + limits for the PVC. Note that for this approach to work, your node needs to have project quotas enabled on the mount point and your helper image needs to have `xfsprogs-extra` installed. We can achieve the former by modifying our init script `mount` and `/etc/fstab` contents, adding the `prjquota` option. 

```bash
mount -o prjquota /dev/md0 /mnt/disks/ssd-array
# ...
echo "UUID=$raid_dev_uuid /mnt/disks/ssd-array xfs defaults,nofail,noatime,prjquota 0 0" |\
  | sudo tee -a /etc/fstab
```

You can specify a custom helper pod, which uses a container image with the required dependency installed (`apk --no-cache add xfsprogs-extra`, e.g.) via the Helm values `configmap.helperPod`. We now have a way to address overcommitting and enforcing storage limits, which allows us to safely put multiple pods with `local-path` PVCs on the same node. Next, let's see how can we avoid unschedulable pods. 

## Generic Ephemeral Volumes

Generic ephemeral volumes are similar to `emptyDir` in that their lifecycle is bound to the pod. However, they allow accessing arbitrary PVC storage classes via a volume claim template. We can modify our `StatefulSet` to use a generic ephemeral volume by moving the `spec.volumeClaimTemplate[0]` into `spec.template.spec.volumes[0].ephemeral.volumeClaimTemplate`:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: volume-test
spec:
  serviceName: "test"
  replicas: 2
  selector:
    matchLabels:
      app: volume-test
  template:
    metadata:
      labels:
        app: volume-test
    spec:
      containers:
        - name: test-container
          image: busybox
          command: ['sh', '-c', 'echo "Test $(hostname)" > /data/test && sleep 3600']
          volumeMounts:
            - mountPath: /data
              name: local-storage
      volumes:
        - name: local-storage
          ephemeral:
            volumeClaimTemplate:
              metadata:
                name: local-storage
              spec:
                accessModes: ["ReadWriteOnce"]
                storageClassName: local-path
                resources:
                  requests:
                    storage: 128Mi
```

This shifts the responsibility for creating the `local-path` PVC from the `StatefulSet` controller to the ephemeral volume controller. In turn, the owner reference of the PVC will point to the pod and no longer the `StatefulSet`. When the pod is deleted, the Kubernetes garbage collector will delete the PVC, and if the reclaim policy is `Delete`, the PV as well.

This should prevent the situation where the new STS replica becomes unschedulable because the old PVC is still bound to a non-existing or otherwise unsuitable node. Note that this approach does not work if you want to reuse the existing PVCs, e.g. to facilitate rolling restarts / upgrades without losing temporary data (as long as the replica can get scheduled to the same node). Let's investigate a different approach you can use in case you want to reuse the PVCs, or are on an older Kubernetes version (< 1.23) that does not support generic ephemeral volumes.

## Local Path Cleaner

TODO

```python
import logging

import time
from kubernetes import config, client
from kubernetes.client import CoreV1Api
from kubernetes.client.models import V1NodeList, V1Node
from kubernetes.client.models.v1_persistent_volume import V1PersistentVolume
from kubernetes.client.models.v1_persistent_volume_list import V1PersistentVolumeList
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.client.models.v1_pod_condition import V1PodCondition
from kubernetes.client.models.v1_pod_status import V1PodStatus
from prometheus_client import Counter

from app.config import DRY_RUN, CLEAN_STUCK_PODS, K8S_API_PAGE_LIMIT, CLEAN_RELEASED_PVS, \
    SLEEP_BEFORE_DELETING_POD_SECONDS, CLEAN_UNSCHEDULABLE_PODS_AND_PVCS, NAMESPACE_PATTERN
from app.metrics import c_deleted_pvs, g_consecutive_errors, c_deleted_pvcs_no_node, c_deleted_pvcs_pod_unschedulable, c_deleted_pods_no_node, c_deleted_pods_pod_unschedulable

POD_CONTROLLERS = ['ReplicaSet', 'StatefulSet', 'Job']


def namespace_matches(namespace):
    return NAMESPACE_PATTERN.match(namespace) is not None


def create_core_api(local_mode):
    if local_mode:
        logging.info("Running in local mode, attempting to load kube configuration from file.")
        config.load_kube_config()
    else:
        logging.info(
            "Running in in-cluster mode, attempting to load the kube configuration from within the kubernetes cluster.")
        config.load_incluster_config()
    return client.CoreV1Api()


def get_pending_pods(v1: CoreV1Api):
    pods = []
    _continue = None

    while True:
        ret = v1.list_pod_for_all_namespaces(watch=False, _continue=_continue, limit=K8S_API_PAGE_LIMIT,
                                             field_selector="status.phase=Pending")
        for pod in ret.items:
            if namespace_matches(pod.metadata.namespace):
                pods.append(pod)
            else:
                logging.debug(f"Skipping pod {pod.metadata.namespace}/{pod.metadata.name} because it does not match the namespace regex")
        _continue = ret.metadata._continue
        if not _continue:
            break

    return pods


def find_pods_with_pvcs_on_active_nodes(pods, pvcs, nodes):
    pvc_res = []
    pods_res = []
    node_names = set(map(lambda n: n.metadata.name, nodes))
    pvcs_by_name = {pvc.metadata.name: pvc for pvc in pvcs}
    for pod in pods:
        if get_pod_owner_type(pod) not in POD_CONTROLLERS:
            # We don't want to delete pods that are not managed by a controller
            continue
        for volume in pod.spec.volumes:
            if volume.persistent_volume_claim:
                pod_pvc = pvcs_by_name.get(volume.persistent_volume_claim.claim_name)
                if pod_pvc is not None and pod_pvc.metadata.annotations['volume.kubernetes.io/selected-node'] in node_names:
                    pods_res.append(pod)
                    pvc_res.append(pod_pvc)
                    break

    return pvc_res, pods_res


def filter_pods_with_pvc_conflict(pods, pvcs):
    res = []
    pvc_names = set(map(lambda pvc: pvc.metadata.name, pvcs))
    for pod in pods:
        if get_pod_owner_type(pod) not in POD_CONTROLLERS:
            # We don't want to delete pods that are not managed by a controller
            continue
        pod_pvc = next((volume for volume in pod.spec.volumes if
                        volume.persistent_volume_claim and volume.persistent_volume_claim.claim_name in pvc_names),
                       None)
        if pod_pvc is not None:
            res.append(pod)
    return res


def delete_pods(v1: CoreV1Api, pods, reason, counter: Counter, dry_run=DRY_RUN):
    for pod in pods:
        logging.info("Deleting pending pod {}/{} (reason: {})".format(pod.metadata.namespace, pod.metadata.name, reason))
        counter.inc()
        if not dry_run:
            v1.delete_namespaced_pod(pod.metadata.name, pod.metadata.namespace)


def delete_pending_pods(v1: CoreV1Api, pvcs, reason, clean_stuck_pods=CLEAN_STUCK_PODS, dry_run=DRY_RUN):
    logging.debug("Deleting pending pods with PVC conflict (reason: {})".format(reason))
    if clean_stuck_pods:
        pending_pods = get_pending_pods(v1)
        deletion_candidates = filter_pods_with_pvc_conflict(pending_pods, pvcs)
        delete_pods(v1, deletion_candidates, reason, counter=c_deleted_pods_no_node, dry_run=dry_run)


def get_released_local_path_pvs(v1: CoreV1Api):
    pvs = []
    _continue = None

    while True:
        ret: V1PersistentVolumeList = v1.list_persistent_volume(watch=False, _continue=_continue, limit=K8S_API_PAGE_LIMIT)
        for pv in ret.items:
            storage_class = pv.spec.storage_class_name
            phase = pv.status.phase
            if storage_class == 'local-path' and phase == "Released":
                pvs.append(pv)
        _continue = ret.metadata._continue
        if not _continue:
            break

    return pvs


def get_bound_local_path_pvcs(v1: CoreV1Api):
    pvcs = []
    _continue = None

    while True:
        ret = v1.list_persistent_volume_claim_for_all_namespaces(watch=False, _continue=_continue,
                                                                 limit=K8S_API_PAGE_LIMIT)
        for pvc in ret.items:
            if namespace_matches(pvc.metadata.namespace):
                storage_class = pvc.spec.storage_class_name
                phase = pvc.status.phase
                if storage_class == 'local-path' and phase == "Bound":
                    pvcs.append(pvc)
            else:
                logging.debug(f"Skipping PVC {pvc.metadata.namespace}/{pvc.metadata.name} because it does not match the namespace regex")
        _continue = ret.metadata._continue
        if not _continue:
            break

    return pvcs


def get_nodes(v1: CoreV1Api) -> list[V1Node]:
    logging.debug("Getting nodes")
    nodes: list[V1Node] = []
    _continue = None

    while True:
        ret: V1NodeList = v1.list_node(watch=False, _continue=_continue, limit=K8S_API_PAGE_LIMIT)
        for node in ret.items:
            nodes.append(node)
        _continue = ret.metadata._continue
        if not _continue:
            break

    logging.debug("Got {} nodes".format(len(nodes)))
    return nodes


def find_pvs_on_missing_nodes(pvs, nodes: list[V1Node]):
    deletion_candidates = []
    node_names = set(map(lambda n: n.metadata.name, nodes))
    pv: V1PersistentVolume
    for pv in pvs:
        node_selector_match_expression = pv.spec.node_affinity.required.node_selector_terms[0].match_expressions[0]
        if node_selector_match_expression.key == 'kubernetes.io/hostname' and node_selector_match_expression.operator == 'In' \
                and node_selector_match_expression.values[0] not in node_names:
            deletion_candidates.append(pv)

    return deletion_candidates


def find_pvcs_on_missing_nodes(pvcs, nodes):
    deletion_candidates = []
    node_names = set(map(lambda n: n.metadata.name, nodes))
    for pvc in pvcs:
        if 'volume.kubernetes.io/selected-node' in pvc.metadata.annotations \
                and pvc.metadata.annotations['volume.kubernetes.io/selected-node'] not in node_names:
            deletion_candidates.append(pvc)

    return deletion_candidates


def delete_pvs(v1: CoreV1Api, candidates, dry_run=DRY_RUN):
    for candidate in candidates:
        c_deleted_pvs.inc()
        logging.info(
            "Deleting PV {} (PVC: {}/{}, phase: {}, class: {}, node: {}) because the node does not exist anymore".format(
                candidate.metadata.name,
                candidate.spec.claim_ref.namespace,
                candidate.spec.claim_ref.name, candidate.status.phase,
                candidate.spec.storage_class_name,
                candidate.spec.node_affinity.required.node_selector_terms[0].match_expressions[0].values[0]
            ))
        if not dry_run:
            v1.delete_persistent_volume(candidate.metadata.name)


def delete_pvcs(v1: CoreV1Api, candidates, reason, counter: Counter, dry_run=DRY_RUN):
    for candidate in candidates:
        counter.inc()
        logging.info("Deleting PVC {}/{} (phase: {}, class: {}, node: {}) because {}".format(
            candidate.metadata.namespace,
            candidate.metadata.name,
            candidate.status.phase,
            candidate.spec.storage_class_name,
            candidate.metadata.annotations['volume.kubernetes.io/selected-node'],
            reason
        ))
        if not dry_run:
            v1.delete_namespaced_persistent_volume_claim(candidate.metadata.name, candidate.metadata.namespace)


def clean_released_pvs(v1: CoreV1Api, nodes: list[V1Node], cleaning_on=CLEAN_RELEASED_PVS, dry_run=DRY_RUN):
    logging.debug("Cleaning released local-path PVs on missing nodes")
    if cleaning_on:
        pvs = get_released_local_path_pvs(v1)
        deletion_candidates = find_pvs_on_missing_nodes(pvs, nodes)
        delete_pvs(v1, deletion_candidates, dry_run=dry_run)


def clean_orphaned_pvcs(v1: CoreV1Api, nodes: list[V1Node], cleaning_on=CLEAN_STUCK_PODS, dry_run=DRY_RUN):
    logging.debug("Cleaning orphaned local-path PVCs on missing nodes")
    if cleaning_on:
        pvcs = get_bound_local_path_pvcs(v1)
        deletion_candidates = find_pvcs_on_missing_nodes(pvcs, nodes)
        delete_pvcs(v1, deletion_candidates, reason="the node does not exist anymore", counter=c_deleted_pvcs_no_node, dry_run=dry_run)
        return deletion_candidates
    return []


def get_pod_owner_type(pod):
    owner_references = pod.metadata.owner_references
    if not owner_references:
        return None

    for owner in owner_references:
        if owner.controller:
            return owner.kind

    return None


def get_condition(pod: V1Pod, condition_type):
    pod_status: V1PodStatus = pod.status
    condition: V1PodCondition
    return next(
        (
            condition
            for condition in pod_status.conditions
            if condition.type == condition_type
        ),
        None,
    )


def clean_orphaned_pvcs_and_pods(v1: CoreV1Api, nodes: list[V1Node], sleep_before_deleting_pod_seconds, dry_run=DRY_RUN):
    deleted_pvcs = clean_orphaned_pvcs(v1, nodes, dry_run=dry_run)
    logging.info("Sleeping a bit before deleting stuck pods to make sure the new replica gets a new PVC")
    time.sleep(sleep_before_deleting_pod_seconds)
    delete_pending_pods(v1, deleted_pvcs, reason="local-path PVC belongs to a non-existing node", dry_run=dry_run)


def clean_unschedulable_pod_pvc_conflicts(v1: CoreV1Api, nodes: list[V1Node], sleep_before_deleting_pod_seconds,
                                          clean_unschedulable_pods=CLEAN_UNSCHEDULABLE_PODS_AND_PVCS, clean_pods=CLEAN_STUCK_PODS, dry_run=DRY_RUN):
    logging.debug("Cleaning unschedulable pods with bound local path PVCs.")
    pending_pods = get_pending_pods(v1)
    unschedulable_pods = filter_unschedulable_pods(pending_pods)
    pvcs = get_bound_local_path_pvcs(v1)
    pvc_deletion_candidates, pod_deletion_candidates = find_pods_with_pvcs_on_active_nodes(unschedulable_pods, pvcs, nodes)

    reason = "local-path PVC belongs to an existing node that cannot schedule the pod"
    if clean_unschedulable_pods:
        delete_pvcs(v1, pvc_deletion_candidates, reason, counter=c_deleted_pvcs_pod_unschedulable, dry_run=dry_run)

        logging.info("Sleeping a bit before deleting unschedulable pods to make sure the new replica gets a new PVC")
        time.sleep(sleep_before_deleting_pod_seconds)
        if clean_pods:
            delete_pods(v1, pod_deletion_candidates, reason, counter=c_deleted_pods_pod_unschedulable, dry_run=dry_run)
    else:
        for pod_candidate, pvc_candidate in zip(pod_deletion_candidates, pvc_deletion_candidates):
            logging.info(
                f"Would delete pod {pod_candidate.metadata.namespace}/{pod_candidate.metadata.name} and PVC {pvc_candidate.metadata.namespace}/{pvc_candidate.metadata.name} ({reason}), "
                f"but CLEANER_INCLUDE_UNSCHEDULABLE_PODS_AND_PVCS is turned off.")


def filter_unschedulable_pods(pods):
    res = []
    for pod in pods:
        pod_condition: V1PodCondition = get_condition(pod, 'PodScheduled')
        if pod_condition is not None and pod_condition.status == 'False' and pod_condition.reason == 'Unschedulable':
            res.append(pod)
    return res


def clean(v1: CoreV1Api, sleep_before_deleting_pod_seconds=SLEEP_BEFORE_DELETING_POD_SECONDS, dry_run=DRY_RUN):
    nodes: list[V1Node] = get_nodes(v1)
    clean_released_pvs(v1, nodes, dry_run=dry_run)
    clean_orphaned_pvcs_and_pods(v1, nodes, sleep_before_deleting_pod_seconds, dry_run=dry_run)
    clean_unschedulable_pod_pvc_conflicts(v1, nodes, sleep_before_deleting_pod_seconds, dry_run=dry_run)
    g_consecutive_errors.set(0)
```

```python
import logging
import os
import re

LOG_LEVEL = os.getenv('CLEANER_LOG_LEVEL', 'INFO')
print("Log level set to {}".format(LOG_LEVEL))
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s %(message)s')

LOCAL_MODE = os.getenv('CLEANER_LOCAL_MODE', 'False') == 'True'
logging.info("Local mode set to {}".format(LOCAL_MODE))

RUN_ONCE = os.getenv('CLEANER_RUN_ONCE', 'False') == 'True'
logging.info("Run once set to {}".format(RUN_ONCE))

CLEANER_PORT = int(os.getenv('CLEANER_PORT', '8000'))
logging.info("HTTP server port set to {}".format(CLEANER_PORT))

SLEEP_INTERVAL = int(os.getenv('CLEANER_SLEEP_INTERVAL_SECONDS', "60"))
logging.info("Sleep interval set to {}s".format(SLEEP_INTERVAL))

DRY_RUN = os.getenv('CLEANER_DRY_RUN', 'True') == 'True'
logging.info("Dry run set to {}".format(DRY_RUN))

CLEAN_RELEASED_PVS = os.getenv('CLEANER_CLEAN_RELEASED_PVS', 'True') == 'True'
logging.info("Cleaning released PVs set to {}".format(CLEAN_RELEASED_PVS))

CLEAN_STUCK_PODS = os.getenv('CLEANER_CLEAN_STUCK_PODS', 'True') == 'True'
logging.info("Deleting stuck pods set to {}".format(CLEAN_STUCK_PODS))

K8S_API_PAGE_LIMIT = int(os.getenv('CLEANER_K8S_API_PAGE_LIMIT', '20'))
logging.info("K8s API page limit set to {}".format(K8S_API_PAGE_LIMIT))

SLEEP_BEFORE_DELETING_POD_SECONDS = int(os.getenv('CLEANER_SLEEP_BEFORE_DELETING_POD_SECONDS', '10'))
logging.info("Sleep before deleting pod set to {}s".format(SLEEP_BEFORE_DELETING_POD_SECONDS))

CLEAN_UNSCHEDULABLE_PODS_AND_PVCS = os.getenv('CLEANER_INCLUDE_UNSCHEDULABLE_PODS_AND_PVCS', 'False') == 'True'
logging.info("Cleaning unschedulable pods and PVCs on active nodes set to {}".format(CLEAN_UNSCHEDULABLE_PODS_AND_PVCS))

NAMESPACE_REGEX = os.getenv('CLEANER_NAMESPACE_REGEX', '.*')
NAMESPACE_PATTERN = re.compile(NAMESPACE_REGEX)
logging.info("Namespace regex set to {}".format(NAMESPACE_REGEX))
```

## Testing

```python
import os
from unittest.mock import MagicMock, call, patch

import urllib3
from kubernetes.client import CoreV1Api
from kubernetes.client.api_client import ApiClient
from kubernetes.client.models.v1_node_list import V1NodeList
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.client.models.v1_pod_condition import V1PodCondition
from kubernetes.client.models.v1_pod_list import V1PodList
from kubernetes.client.rest import RESTResponse

from app.k8s import get_nodes, get_released_local_path_pvs, get_bound_local_path_pvcs, get_pending_pods, clean, get_condition, clean_unschedulable_pod_pvc_conflicts

api_client = ApiClient()


def load_resource(file, resource_type):
    with open(os.path.join(os.path.dirname(__file__), 'resources', file), 'r') as f:
        urllib3_response = urllib3.HTTPResponse(body=f.read())
        response = RESTResponse(urllib3_response)
        return api_client.deserialize(response, resource_type)


def test_get_nodes():
    nodes_response: V1NodeList = load_resource('writerxl_nodes.json', 'V1NodeList')
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_node.return_value = nodes_response

    nodes = get_nodes(v1)

    assert set(map(lambda node: node.metadata.name, nodes)) == {
        'gke-main-writerxl-v3-be6cf51e-zgvj',
        'gke-main-writerxl-v3-c51c4677-285f',
    }


def test_get_released_local_path_pvs():
    pvs_response = load_resource('writerxl_pvs.json', 'V1PersistentVolumeList')
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_persistent_volume.return_value = pvs_response

    pvs = get_released_local_path_pvs(v1)

    assert set(map(lambda pv: pv.metadata.name, pvs)) == {
        "pvc-released-on-existing-node-001",
        "pvc-released-non-existing-node-001",
    }


def test_get_bound_local_path_pvcs():
    pvcs_response = load_resource('writerxl_pvcs.json', 'V1PersistentVolumeClaimList')
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_persistent_volume_claim_for_all_namespaces.return_value = pvcs_response

    pvcs = get_bound_local_path_pvcs(v1)

    assert set(map(lambda pvc: pvc.metadata.name, pvcs)) == {
        'ad-hoc-pod-volume',
        'db-storagerack-volume-db-storage-rack0-v0-0',
        'db-storagerack-volume-db-storage-rack1-v0-0',
        'db-storagerack-volume-db-storage-rack2-v0-0',
    }


def test_get_pending_pods():
    pods_response = load_resource('writerxl_pending_pods.json', 'V1PodList')
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_pod_for_all_namespaces.return_value = pods_response

    pods = get_pending_pods(v1)

    v1.list_pod_for_all_namespaces.assert_called_with(watch=False, _continue=None, limit=20, field_selector="status.phase=Pending")

    assert set(map(lambda pod: pod.metadata.name, pods)) == {
        'db-storage-rack2-v0-0', 'ad-hoc-pod',
    }


def test_clean_unschedulable_pod_pvc_conflicts__happy_path():
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_node.return_value = load_resource('unschedulable_node.json', 'V1NodeList')
    nodes = get_nodes(v1)
    v1.list_persistent_volume_claim_for_all_namespaces.return_value = load_resource('unschedulable_pvc.json', 'V1PersistentVolumeClaimList')
    v1.list_pod_for_all_namespaces.return_value = load_resource('unschedulable_pod.json', 'V1PodList')

    clean_unschedulable_pod_pvc_conflicts(v1, nodes, clean_unschedulable_pods=True, clean_pods=True,
                                          sleep_before_deleting_pod_seconds=0, dry_run=False)

    v1.delete_namespaced_pod.assert_has_calls([call.delete_namespaced_pod('sts-1-0', 'local-path-storage')])


def test_clean_unschedulable_pod_pvc_conflicts__pvc_not_bound():
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_node.return_value = load_resource('unschedulable_node.json', 'V1NodeList')
    nodes = get_nodes(v1)
    v1.list_persistent_volume_claim_for_all_namespaces.return_value = load_resource('unschedulable_unbound_pvc.json', 'V1PersistentVolumeClaimList')
    v1.list_pod_for_all_namespaces.return_value = load_resource('unschedulable_pod.json', 'V1PodList')

    clean_unschedulable_pod_pvc_conflicts(v1, nodes, clean_unschedulable_pods=True, clean_pods=True,
                                          sleep_before_deleting_pod_seconds=0, dry_run=False)

    v1.delete_namespaced_pod.assert_not_called()


def test_clean_unschedulable_pod_pvc_conflicts__feature_turned_off():
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_node.return_value = load_resource('unschedulable_node.json', 'V1NodeList')
    nodes = get_nodes(v1)
    v1.list_persistent_volume_claim_for_all_namespaces.return_value = load_resource('unschedulable_pvc.json', 'V1PersistentVolumeClaimList')
    v1.list_pod_for_all_namespaces.return_value = load_resource('unschedulable_pod.json', 'V1PodList')

    clean_unschedulable_pod_pvc_conflicts(v1, nodes, clean_unschedulable_pods=False, clean_pods=True,
                                          sleep_before_deleting_pod_seconds=0, dry_run=False)

    v1.delete_namespaced_pod.assert_not_called()


def test_clean_unschedulable_pod_pvc_conflicts__no_deletion_if_not_unschedulable():
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_node.return_value = load_resource('unschedulable_node.json', 'V1NodeList')
    nodes = get_nodes(v1)
    v1.list_persistent_volume_claim_for_all_namespaces.return_value = load_resource('unschedulable_pvc.json', 'V1PersistentVolumeClaimList')
    v1.list_pod_for_all_namespaces.return_value = load_resource('scheduler_error_pod.json', 'V1PodList')

    clean_unschedulable_pod_pvc_conflicts(v1, nodes, clean_unschedulable_pods=True, clean_pods=True,
                                          sleep_before_deleting_pod_seconds=0, dry_run=False)

    v1.delete_namespaced_pod.assert_not_called()


@patch('app.k8s.namespace_matches')
def test_clean(mock_namespace_matches):
    mock_namespace_matches.side_effect = lambda namespace: namespace == 'db-shadow'

    v1 = MagicMock(spec=CoreV1Api)
    v1.list_node.return_value = load_resource('writerxl_nodes.json', 'V1NodeList')
    v1.list_persistent_volume.return_value = load_resource('writerxl_pvs.json', 'V1PersistentVolumeList')
    v1.list_persistent_volume_claim_for_all_namespaces.return_value = load_resource('writerxl_pvcs.json', 'V1PersistentVolumeClaimList')
    v1.list_pod_for_all_namespaces.return_value = load_resource('writerxl_pending_pods.json', 'V1PodList')

    clean(v1, sleep_before_deleting_pod_seconds=0, dry_run=False)

    v1.delete_persistent_volume.assert_has_calls([call.delete_persistent_volume('pvc-released-non-existing-node-001')])
    v1.delete_namespaced_persistent_volume_claim.assert_has_calls(
        [call.delete_namespaced_persistent_volume_claim('db-storagerack-volume-db-storage-rack2-v0-0', 'db-shadow')])
    assert 1 == v1.delete_persistent_volume.call_count
    v1.delete_namespaced_pod.assert_has_calls([call.delete_namespaced_pod('db-storage-rack2-v0-0', 'db-shadow')])
    assert 1 == v1.delete_namespaced_pod.call_count


def test_clean_dry_run():
    v1 = MagicMock(spec=CoreV1Api)
    v1.list_node.return_value = load_resource('writerxl_nodes.json', 'V1NodeList')
    v1.list_persistent_volume.return_value = load_resource('writerxl_pvs.json', 'V1PersistentVolumeList')
    v1.list_persistent_volume_claim_for_all_namespaces.return_value = load_resource('writerxl_pvcs.json', 'V1PersistentVolumeClaimList')
    v1.list_pod_for_all_namespaces.return_value = load_resource('writerxl_pending_pods.json', 'V1PodList')

    clean(v1, sleep_before_deleting_pod_seconds=0, dry_run=True)

    v1.delete_persistent_volume.assert_not_called()
    v1.delete_namespaced_persistent_volume_claim.assert_not_called()
    v1.delete_namespaced_pod.assert_not_called()


def test_get_condition():
    pods: V1PodList = load_resource('writerxl_pods.json', 'V1PodList')
    pod: V1Pod = pods.items[0]
    scheduled_condition: V1PodCondition = get_condition(pod, 'PodScheduled')
    assert scheduled_condition.status == "True"
```

```toml
[tool.poetry.dependencies]
python = "^3.11"
kubernetes = "^31.0.0"
prometheus-client = "^0.21.1"
python-dateutil = "^2.9.0.post0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.4"
urllib3 = "^2.2.3"
```


```md
## Description



## Configuration

### Feature Toggles / Configuration

- `CLEANER_DRY_RUN=True|False` to configure dry run by setting 
- `CLEANER_NAMESPACE_REGEX=".*"` to configure the namespace regex to filter the PVCs and pods to clean. PVs are not namespaced.
- `CLEANER_CLEAN_RELEASED_PVS=True|False` to configure whether to clean released local-path PVs
- `CLEANER_CLEAN_STUCK_PODS=True|False` to configure whether to clean orphaned (node not part of cluster) local-path PVCs and get the corresponding pods unstuck
- `CLEANER_INCLUDE_UNSCHEDULABLE_PODS_AND_PVCS=True|False` to configure whether to clean local-path PVCs and pods on active nodes if the pods are unschedulable, e.g. because the node does not have enough capacity.
- `CLEANER_SLEEP_INTERVAL_SECONDS=60` to configure sleep interval between runs
- `CLEANER_SLEEP_BEFORE_DELETING_POD_SECONDS=10` to configure sleep interval after deleting PVC, before deleting the respective pod.
- `CLEANER_K8S_API_PAGE_LIMIT=20` to configure the page size when using k8s APIs.

### Operations

- `CLEANER_LOCAL_MODE=True|False` to configure in-cluster (running inside a pod) vs local mode with 
- `CLEANER_RUN_ONCE=True|False` to configure whether to run the cleaner once or in a loop (recommended for quick local testing)
- `CLEANER_PORT=8000` to set the port the HTTP server will be running on

### Observability

- `CLEANER_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL` to configure log level 
- `PROMETHEUS_DISABLE_CREATED_SERIES=True|False` to disable `_created` metrics. See https://github.com/prometheus/client_python/blob/master/README.md#disabling-_created-metrics.

```

```yaml
---
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: local-path-cleaner
rules:
  - apiGroups: [""]
    resources: ["persistenvolumes", "persistentvolumeclaims", "pods"]
    verbs: ["get", "list", "delete"]
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list"]

---
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: local-path-cleaner
subjects:
  - kind: ServiceAccount
    name: local-path-cleaner
roleRef:
  kind: ClusterRole
  name: local-path-cleaner
  apiGroup: rbac.authorization.k8s.io

---
kind: ServiceAccount
apiVersion: v1
metadata:
  name: local-path-cleaner
```

---

```bash
#!/bin/bash
set -x
# Get Hostname
host=$(hostname)
writer='cast'

echo "tsc" | sudo tee /sys/devices/system/clocksource/clocksource0/current_clocksource
sudo mkdir -p /var/lib/kubelet
sudo tee /var/lib/kubelet/config.json > /dev/null <<EOF
    {
      "auths": {
        "${var.registry_host}": {
          "auth": "${var.registry_auth}"
        }
      }
    }
EOF

# Doing this to help make debugging easier, startup script logs can be searched by connecting to instance and running.
# sudo journalctl -u kube-node-installation.service
lsblk --json

SSDS=($(readlink -f /dev/disk/by-id/google-local-nvme-ssd-*))
if [ $SSDS == "/dev/disk/by-id/google-local-nvme-ssd-*" ]; then
  echo No SSD was detected
  exit 0
fi

sudo umount "$${SSDS[@]}" 2>/dev/null || true

/usr/bin/yes | sudo mdadm --create /dev/md0 --level=0 --force "--raid-devices=$${#SSDS[@]}" "$${SSDS[@]}" || true
sudo mkfs.xfs -s size=4096 /dev/md0
raid_dev_uuid=$(sudo blkid | grep dev/md0 | egrep -o '[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}')

sudo mkdir -p /mnt/disks/ssd-array
sudo mount -o prjquota /dev/md0 /mnt/disks/ssd-array
sudo chmod a+w /mnt/disks/ssd-array
echo "UUID=$raid_dev_uuid /mnt/disks/ssd-array xfs defaults,nofail,noatime,prjquota 0 0" | sudo tee -a /etc/fstab

# Verify the readahead setting...
read_ahead="$(cat /sys/class/block/md0/queue/read_ahead_kb)"
if [[ $read_ahead == "8" ]]; then
  echo "read_ahead set to 8K."
else
  echo "Failed to set read_ahead."
fi

export KUBE_HOME="/home/kubernetes"
if [[ ! -e "$${KUBE_HOME}/kube-env" ]]; then
  echo "The $${KUBE_HOME}/kube-env file does not exist!! Terminate cluster initialization."
  exit 1
fi
sed -i 's|readonly NODE_LOCAL_SSDS_EPHEMERAL=true|readonly NODE_LOCAL_SSDS_EPHEMERAL=false|' "$${KUBE_HOME}/kube-env"

#sed -i -E 's/(ephemeral-storage:).*/\1 10Gi/' /home/kubernetes/kubelet-config.yaml

mkdir -p /mnt/disks/ssd-array/lib/kubelet
mkdir -p /mnt/disks/ssd-array/lib/containerd
mv /var/lib/kubelet/* /mnt/disks/ssd-array/lib/kubelet
mv /var/lib/containerd/* /mnt/disks/ssd-array/lib/containerd
mount --bind /mnt/disks/ssd-array/lib/kubelet /var/lib/kubelet
mount --bind /mnt/disks/ssd-array/lib/containerd /var/lib/containerd
```

---

If you liked this post, you can [support me on ko-fi](https://ko-fi.com/frosnerd).
