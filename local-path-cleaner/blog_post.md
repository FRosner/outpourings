---
title: Addressing the Limitations of Local Path Provisioner in Kubernetes
published: false
description: In this post we will discuss how to manage ephemeral and semi-persistent local storage in Kubernetes by combining different Kubernetes features such as local ephemeral storage, filesystem quotas, and generic ephemeral volumes to address the limitations of local path provisioner.
tags: kubernetes, cloud, devops, infrastructure
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/3zcyrttro68enzhm57rt.png
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

1. The `StatefulSet` controller processes the first replica, creating the PVC and pod based on the template and setting the owner references. The pod will reference the PVC and both resources will be `Pending`.
2. The PVC control loop detects an unbound PVC, matches the storage class `local-path` to the provisioner `rancher.io/local-path` and triggers dynamic provisioning since no matching PV exists.
3. Local path provisioner watches PVC events via the Kubernetes API. If the storage class is configured with `volumeBindingMode: WaitForFirstConsumer` (default), it will defer the PV binding to pod scheduling. This is useful because there might be other constraints in your pods such as node selectors, or resource requests, which could result in unschedulable pods if the PV is bound to the wrong node.
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

Alternatively, we could hard code the available ephemeral storage capacity in the kubelet config based on the available space on the RAID0 device. While this would allow the scheduler to take storage requests into account for your `local-path` PVs, tracking actual usage will not work. If you wanted it to be 500Gi, you could run:

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

If setup correctly, this should prevent Kubernetes from overcommitting `local-path` PVCs on a node. I admit that this is a bit of a hacky solution with multiple drawbacks: 

- We have to specify the requested storage capacity in two places: In the PVC and in the pod spec.
- Ephemeral storage usage tracking might be off, causing kubelet to not properly enforce ephemeral storage limits.
- We are repurposing the local ephemeral storage concept, which might cause confusion in larger organizations where many teams share the same multi-tenant Kubernetes cluster.

If you wanted to avoid overcommitting without ephemeral storage requests, you could try to align CPU and memory requests with the expected storage usage. Either way, once you have the overcommitting problem under control, we can move to enforcing the storage limits.

## Filesystem Quotas

By default, containers that have a `local-path` PVC mounted, can use as much space in the volume as they want, independently of the space they requested. This can lead to noisy neighbor issues such as unexpected out of disk errors in the applications. Note that by requested space we are referring to the storage requests of the PVC, not the ephemeral storage requests of the container.

Fortunately, filesystems such as XFS support configuring storage quotas. There is an excellent [minimal example](https://github.com/rancher/local-path-provisioner/blob/964c10d96f3098b3d8c0efc9db7e8ad253097ec9/examples/quota/setup#L1-L29) in the local path provisioner repository.

```bash
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

The script first checks if the filesystem is XFS. If not, we exit and the PV is created without quotas. Then, it reads the project file to determine if there are any existing projects so we can pick the next project ID. Project files look like this:

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

To achieve the latter, you can specify a custom helper pod, which uses a container image with the required dependency installed (`apk --no-cache add xfsprogs-extra`, e.g.) via the Helm values `configmap.helperPod`. We now have a way to address overcommitting and enforcing storage limits, which allows us to safely put multiple pods with `local-path` PVCs on the same node. Next, let's see how can we avoid unschedulable pods. 

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

A few years ago, I wrote a Python application that I named "local path cleaner". It fulfills the following objectives:

- Clean up released local-path PVs on nodes that are no longer part of the cluster.
- Clean up local-path PVCs and the corresponding pods that are unschedulable.

### Cleaning Released PVs

To clean released local-path PVs, we implement the following steps:

1. List all released local-path PVs.
2. For each PV, check if the node it is bound to is part of the cluster.
3. If the node is not part of the cluster, delete the PV.

Let's walk through the code. We're going to use the Kubernetes Python client to interact with the API. First, we use `list_persistent_volume` to list all PVs. In Kubernetes, PVs are not namespaced, so we can list them all at once. Note that you should specify a page size and handle pagination accordingly.

```python
def get_released_local_path_pvs(v1: CoreV1Api):
    result = []
    _continue = None

    while True:
        pvs: V1PersistentVolumeList = v1.list_persistent_volume(
            watch=False, 
            _continue=_continue,
        )
        for pv in pvs.items:
            storage_class = pv.spec.storage_class_name
            phase = pv.status.phase
            if storage_class == 'local-path' and phase == "Released":
                result.append(pv)
        _continue = pvs.metadata._continue
        if not _continue:
            break

    return result
```

Next, let's write a similar function to obtain all nodes:

```python
def get_nodes(v1: CoreV1Api) -> list[V1Node]:
    result: list[V1Node] = []
    _continue = None

    while True:
        nodes: V1NodeList = v1.list_node(
            watch=False, 
            _continue=_continue
        )
        for node in nodes.items:
            result.append(node)
        _continue = nodes.metadata._continue
        if not _continue:
            break

    return result
```

Then, we can find the PVs that are bound to nodes which are no longer part of the cluster. We'll walk through all the PVs, checking the node affinity selector terms to determine the assigned node. E.g. the following PV is bound to node `gke-main-data-node-c51c4677-285f`:

```json
{
  "apiVersion": "v1",
  "kind": "PersistentVolume",
  "metadata": {
    "annotations": {
      "pv.kubernetes.io/provisioned-by": "cluster.local/local-path-storage-local-path-provisioner"
    },
    "name": "pvc-db-001"
  },
  "spec": {
    "capacity": {
      "storage": "2000Gi"
    },
    "hostPath": {
      "path": "/mnt/disks/ssd-array/pvc-db-app-0",
      "type": "DirectoryOrCreate"
    },
    "nodeAffinity": {
      "required": {
        "nodeSelectorTerms": [
          {
            "matchExpressions": [
              {
                "key": "kubernetes.io/hostname",
                "operator": "In",
                "values": [
                  "gke-main-data-node-c51c4677-285f"
                ]
              }
            ]
          }
        ]
      }
    },
    "persistentVolumeReclaimPolicy": "Delete",
    "storageClassName": "local-path",
    "volumeMode": "Filesystem"
  }
}
```

And here's the Python code. We don't delete the PVs immediately but gather them first so we can implement a dry-run mode where we simply log all the PVs we would have deleted.

```python
def find_pvs_on_missing_nodes(v1: CoreV1Api, pvs):
    nodes: list[V1Node] = get_nodes(v1)
    deletion_candidates = []
    node_names = set(map(lambda n: n.metadata.name, nodes))
    pv: V1PersistentVolume
    for pv in pvs:
        node_selector_match_expression = pv.spec.node_affinity.required.node_selector_terms[0].match_expressions[0]
        if node_selector_match_expression.key == 'kubernetes.io/hostname' \ 
            and node_selector_match_expression.operator == 'In' \
            and node_selector_match_expression.values[0] not in node_names:
            deletion_candidates.append(pv)
    return deletion_candidates
```

Finally, we can put everything together and delete the PVs:

```python
def clean_released_pvs(v1: CoreV1Api):
    pvs = get_released_local_path_pvs(v1)
    deletion_candidates = find_pvs_on_missing_nodes(pvs)
    for candidate in deletion_candidates:
        v1.delete_persistent_volume(candidate.metadata.name)
```

### Cleaning Unschedulable Pods

When using `local-path` PVCs via `StatefulSet` instead of ephemeral volumes on the pod level, pods can become unschedulable. A common reason is that the PVC is bound to a node that has been scaled down by the cluster autoscaler, has been cordoned, or another workload has moved onto it so it does not have enough capacity.

While it is straightforward to reliably detect the first case, by comparing the node the PVC is bound to with the list of active nodes, I did not find a way to detect the other two cases. The Kubernetes events sometimes show hints about volume affinity conflicts, but this did not happen reliably in all cases.

In the end I decided to purge bound local-path PVCs of unschedulable pods aggressively, as they could always be recreated and I'd rather live with losing temporary data than dealing with a prolonged service outage. Here's the high level algorithm:

1. List all pending pods.
2. Identify unschedulable pods from the pending pods.
3. List all bound local-path PVCs.
4. For each unschedulable pod, check if it has a bound local-path PVC.
5. Delete the PVC and the pod, if the pod has a managing controller.

I found that deleting not only the PVC but also the pod reduces the time to recovery, as the managing controller will immediately recreate both the PVC and the pod in that case, triggering the scheduler and subsequently the local-path provisioner to get the pod onto a new node. Let's build the code step by step:

First, we want to list all pending pods. We can use the `list_pod_for_all_namespaces` method with the field selector `status.phase=Pending` for that. Here we could also employ some namespace filtering to only consider pods in namespaces that match a given regular expression.

```python
def get_pending_pods(v1: CoreV1Api):
    result = []
    _continue = None

    while True:
        pods = v1.list_pod_for_all_namespaces(
            watch=False, _continue=_continue,
            field_selector="status.phase=Pending"
        )
        result += pods.items
        _continue = pods.metadata._continue
        if not _continue:
            break

    return result
```

Next, we keep only unschedulable pods. The information whether a pod is unschedulable is stored in `status.conditions`. Here's an example:

```json
{
    "apiVersion": "v1",
    "kind": "Pod",
    "status": {
        "conditions": [
            {
                "lastProbeTime": null,
                "lastTransitionTime": "2025-01-10T13:20:15Z",
                "message": "0/3 nodes are available: 1 node(s) were unschedulable. preemption: 0/3 nodes are available: 3 Preemption is not helpful for scheduling.",
                "reason": "Unschedulable",
                "status": "False",
                "type": "PodScheduled"
            }
        ],
        "phase": "Pending",
        "qosClass": "Burstable"
    }
}
```

Based on that we can write a helper function `get_condition` that allows to get the condition of a given type from a pod (or `None` if it does not exist):

```python
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
```

Then we can write a function to filter unschedulable pods by checking the `PodScheduled` condition to be `False` and the reason to be `Unschedulable`:

```python
def filter_unschedulable_pods(pods):
    result = []
    for pod in pods:
        pod_condition: V1PodCondition = get_condition(pod, 'PodScheduled')
        if pod_condition is not None \
            and pod_condition.status == 'False' \
            and pod_condition.reason == 'Unschedulable':
            result.append(pod)
    return result
```

Now that we know which pods are unschedulable, we need to keep only the ones that have bound PVCs. Unfortunately, this information is not available in the pod resource, so we need to fetch the PVCs, too. If you need the ability to filter certain namespaces, you could add that here.

```python
def get_bound_local_path_pvcs(v1: CoreV1Api):
    result = []
    _continue = None

    while True:
        pvcs = v1.list_persistent_volume_claim_for_all_namespaces(
            watch=False,
            _continue=_continue,
        )
        for pvc in pvcs.items:
            storage_class = pvc.spec.storage_class_name
            phase = pvc.status.phase
            if storage_class == 'local-path' and phase == "Bound":
                result.append(pvc)
        _continue = pvcs.metadata._continue
        if not _continue:
            break

    return result
```

Now we combine the unschedulable pods and the PVCs to find the pods that have a bound PVC. We convert the bound local-path PVC list into a dictionary by PVC name to efficiently check each of the volumes of each unschedulable pod and match them if possible. 

```python
def find_pods_with_pvcs(pods, pvcs):
    pvc_res = []
    pods_res = []
    pvcs_by_name = {pvc.metadata.name: pvc for pvc in pvcs}
    for pod in pods:
        for volume in pod.spec.volumes:
            if volume.persistent_volume_claim:
                pod_pvc = pvcs_by_name.get(volume.persistent_volume_claim.claim_name)
                pods_res.append(pod)
                pvc_res.append(pod_pvc)
                break

    return pvc_res, pods_res
```

That's it! Now we can combine everything together. I ended up adding a small `sleep` call between deleting the PVC and the pod to reduce the risk of hitting a race condition where the pod would get recreated before the PVC, causing it to become unschedulable again.

```python
def clean_unschedulable_pod_pvc_conflicts(v1: CoreV1Api):
    pending_pods = get_pending_pods(v1)
    unschedulable_pods = filter_unschedulable_pods(pending_pods)
    pvcs = get_bound_local_path_pvcs(v1)
    pvc_deletion_candidates, pod_deletion_candidates = find_pods_with_pvcs(unschedulable_pods, pvcs)

    for candidate in pvc_deletion_candidates:
        v1.delete_namespaced_persistent_volume_claim(candidate.metadata.name, candidate.metadata.namespace)

    time.sleep(2)
    
    for candidate in pod_deletion_candidates:
        v1.delete_namespaced_pod(candidate.metadata.name, candidate.metadata.namespace)
```

This method relies on the fact that upon deletion of the PVC and the pod, some controller will recreate them. To prevent accidentally deleting pods that are not managed by a `StatefulSet`, we can add a filter based on the owner reference:

```python
POD_CONTROLLERS = ['StatefulSet']

def get_pod_owner_type(pod):
    owner_references = pod.metadata.owner_references
    if not owner_references:
        return None

    for owner in owner_references:
        if owner.controller:
            return owner.kind

    return None

for pod in pods:
    if get_pod_owner_type(pod) in POD_CONTROLLERS:
        # Delete the pod and PVC
```

### Operations

We can run this code on a schedule, either by using a Kubernetes cron job, or by having a pod running with a sleep loop. I prefer the long-running pod by using a `Deployment`, as we want the code to run very frequently to reduce the impact of unschedulable pods. I recommend implementing proper logging, metrics, a dry-run mode, a configurable interval, filters, and flags for the different pieces for optimal operability.

Since the cleaner has to interact with the Kubernetes API, it needs the following RBAC permissions, if you have RBAC enabled:

```yaml
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
```

## Summary and Conclusion

In this post we explored different options to provide ephemeral or semi-persistent local storage to your Kubernetes workload. For most use cases, `emptyDir` volumes should be sufficient and those are the easiest to set up and manage. If you need customizable local storage, consider using `local-path` PVCs managed by the generic ephemeral volume controller to avoid unschedulable pods. If the local storage needs to be semi-persistent, you can use `local-path` PVCs managed by a `StatefulSet` in combination with local path cleaner.

In my opinion, managing state on Kubernetes has become a lot easier over the past few years. There are different controllers and mechanisms available to assist you. However, I would not call the problem solved, as there are still some use cases that are not covered by the standard Kubernetes buildings blocks, especially in applications with very specific I/O and operational requirements.

Have you used local path provisioner? What is your experience in terms of operability? Let me know in the comments!

---

If you liked this post, you can [support me on ko-fi](https://ko-fi.com/frosnerd).
