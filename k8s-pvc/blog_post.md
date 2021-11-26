---
title: Reclaiming Persistent Volumes in Kubernetes
published: true
description: Managing and migrating stateful apps on Kubernetes can be hard. This post shows how to manually reclaim persistent volumes in Kubernetes in order to rename stateful sets or migrate existing stateful cloud applications into Kubernetes.
tags: kubernetes, cloud, devops, azure
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/zmnwhel88wvpsh76iddg.jpg
canonical_url: https://medium.com/building-the-open-data-stack/reclaiming-persistent-volumes-in-kubernetes-5e035ba8c770
---

# Introduction

Kubernetes is a widely used open-source container management platform. It works great for running stateless, containerized applications at scale. In recent years, Kubernetes has been extended to also support stateful workloads such as databases, key-value stores, and so on.

There are three important API resources when it comes to managing stateful applications in Kubernetes: [`StatefulSet`](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) (STS), [`PersistentVolume`](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) (PV), and [`PersistentVolumeClaim`](https://kubernetes.io/docs/concepts/storage/storage-classes/) (PVC). STSs schedule stateful pods, which can claim PVs through PVCs and mount them as volumes.

Once a PV is claimed by an STS replica, Kubernetes will make sure that the volume stays with the replica, even if the pod gets rescheduled. This mechanism relies on certain naming conventions however, involving the STS name, the PVC template name, as well as the STS replica index. If you want to rename your STS for whatever reason, Kubernetes will not be able to reassign your existing PVs to the new pods created by the new STS.

In this blog post we will see how to manually reassign a PV from one STS to another. The remainder of the post is structured as follows. In the next section we are going to explain the STS, PV and PVC API resources in greater detail. Afterwards we will present step-by-step instructions for the reassignment of PVs including the `kubectl` commands for each step. We conclude by summarizing and discussing the main findings.

We are going to use Azure Kubernetes Service (AKS) for the given examples, but they are easily transferable to other cloud providers.

# Concepts

## Persistent Volumes

In Kubernetes, pods can request resources such as CPU, memory, and (persistent) storage. While CPU and memory are provided by nodes, storage can be provided by PVs. Just like nodes, PVs have a lifecycle which is independent of the pods that use it. The PV resource captures all the details of the storage implementation, e.g. NFS, Azure File, AWS EBS, and so on.

PVs can either be provisioned statically, e.g. by an administrator, or dynamically. Dynamic PV provisioning kicks in if no static PV exists that matches the specifications from a given PVC. To enable dynamic provisioning, the storage request needs to specify a supported storage class. AKS initially creates [four storage classes](https://docs.microsoft.com/en-us/azure/aks/concepts-storage#storage-classes) for clusters using the [in-tree storage plugins](https://github.com/kubernetes/community/blob/master/sig-storage/volume-plugin-faq.md#in-tree-vs-out-of-tree-volume-plugins): 

- Standard Managed Disk (`default`)
- Premium Managed Disk (`managed-premium`)
- Standard Azure File Share (`azurefile`)
- Premium Azure File Share (`azurefile-premium`)

## Persistent Volume Claims

PVCs consume storage resources, just like pods consume CPU and memory resources. A PVC resource specification has different fields, such as access modes, volume size, and storage classes. Once a PVC is created, Kubernetes attempts to bind any existing, unassigned, statically created PV that matches the given criteria. If it does not succeed, it attempts to dynamically create a PV based on the specified storage class. To disable dynamic provisioning, `storageClassName` must be set to an empty string.

A PVC can only be bound to a single PV, and a PV can only be bound to a single PVC at the same time. The PV `spec.claimRef` field contains a reference to the PVC, while `spec.volumeName` in the PVC resource references the respective PV. PVCs remain unbound as long as no matching PV exists.

Pods can use PVCs as volumes, effectively making the PV storage available to the containers inside the pod. In stateful applications it is important that a given replica keeps the initially assigned PV even if pods get rescheduled. To ensure that, pods need to be managed as stateful sets.

## Stateful Sets

STSs are similar to `Deployment`s, as they manage the deployment and scaling of pods. They provide additional guarantees about ordering and uniqueness of these pods, however. Pods are created based on an identical specification, but the STS maintains a sticky identity for each of the replicas. The identity stays with the replica even if the pod gets scheduled on a different node.

The identity comprises the following:

- **Ordinal index.** An STS with *N* replicas will assign an integer index from *0..N-1* to each replica.
- **Network ID.** Each pod derives its stable hostname using the following pattern: `$STS_NAME-$REPLICA_INDEX`. You can use a headless service to enable access to the pods, but we are not going to go into detail, since networking is beyond the scope of this post.
- **Storage.** Kubernetes creates PVCs for each replica (if they don't exist already) based on the specified `VolumeClaimTemplate`, which is part of the STS specification. The naming scheme for the PVC is `$PVC_TEMPLATE_NAME-$STS_NAME-$REPLICA_INDEX`.

STSs can be used instead of deployments if pods are required to have stable network names, stable persistent storage, or ordered scaling / rollouts. Note that deleting/down-scaling an STS will not delete the PVCs that have been created. Instead, the user is required to clean those up manually. This is done to ensure data safety.

Now that we have all the necessary theory at hand, let's take a look at the required steps to rename an STS while keeping the previously assigned storage.  

# Steps to Reclaim a PV

## Overview

For demonstration purposes, we will use an example STS deployed to an AKS cluster that consists of 2 replicas. Renaming a given STS while reassigning the given PVCs can be accomplished with the following steps:

1. Retain PVs
2. Derive new PVC manifests from existing PVCs
3. Delete old STS
4. Delete old PVCs
5. Allow reclaiming of PVs
6. Create new PVCs
7. Create new STS

The steps are illustrated in the video below. The next sections will go through the process step by step, providing the respective `kubectl` commands needed for each step. 

{% youtube 8CSTdrPsOu4 %}

## Preparation

Before we can start, let's define a few variables for our own convenience. We will need the name of our old STS, the name of the new STS including the manifest file for the new STS, the PVC template name (which could change as well, but we are keeping it the same), the old and new PVC names based on the naming scheme described in the STS concepts section, the names of the PVs that are claimed by the existing PVCs, as well as filenames for the new PVC manifest files that will be generated from the existing ones.

```bash
OLD_STS_NAME="old-app"
NEW_STS_NAME="new-app"
NEW_STS_MANIFEST_FILE="new-app.yaml"
PVC_TEMPLATE_NAME="app-pvc"

OLD_PVC_NAME_0="$PVC_TEMPLATE_NAME-$OLD_STS_NAME-0"
OLD_PVC_NAME_1="$PVC_TEMPLATE_NAME-$OLD_STS_NAME-1"
NEW_PVC_NAME_0="$PVC_TEMPLATE_NAME-$NEW_STS_NAME-0"
NEW_PVC_NAME_1="$PVC_TEMPLATE_NAME-$NEW_STS_NAME-1"

PV_NAME_0=$(kubectl get pvc $OLD_PVC_NAME_0 \
  -o jsonpath="{.items[0].spec.volumeName}")
PV_NAME_1=$(kubectl get pvc $OLD_PVC_NAME_1 \
  -o jsonpath="{.items[0].spec.volumeName}")

NEW_PVC_MANIFEST_FILE_0="$NEW_PVC_NAME_0.yaml"
NEW_PVC_MANIFEST_FILE_1="$NEW_PVC_NAME_1.yaml"
```

Alternatively to specifying the resource names directly, you can also use label selectors and use the index in the JSON path `{.items[i]}` to access individual results.

To avoid code duplication, we will use a short-hand pseudo-code notation to indicate that commands should be repeated for each replica. E.g. `kubectl get pvc $OLD_PVC_NAME_i` needs to be expanded to `kubectl get pvc $OLD_PVC_NAME_0` and `kubectl get pvc $OLD_PVC_NAME_1`.

## Execution

### Retain PVs

When a PVC that is bound to a PV gets deleted, the PV reclaim policy dictates what will happen to the PV. The default behaviour is that PVs are deleted once their claim is released. We can prevent that by setting the reclaim policy to `Retain`.

```bash
kubectl patch pv $PV_NAME_i -p \
  '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

### Create New PVC Manifests

Before we can delete the old PVCs, we will export their manifests and modify them to match the naming scheme of the new STS. We are going to use [`jq`](https://stedolan.github.io/jq/) in combination with `-o json` in this example, but you might also use [`yq`](https://github.com/mikefarah/yq) and `-o yaml`.

```bash
kubectl get pvc $OLD_PVC_NAME_i -o json | jq "
  .metadata.name = \"$NEW_PVC_NAME_i\" 
  | with_entries(
      select([.key] | inside([\"metadata\", \"spec\", \"apiVersion\", \"kind\"]))
    ) 
  | del(
      .metadata.annotations, .metadata.creationTimestamp, .metadata.finalizers, 
      .metadata.resourceVersion, .metadata.selfLink, .metadata.uid
    )
  " > $NEW_PVC_MANIFEST_FILE_i
```

While exporting the JSON manifest, we clean it up a little because it contains internal status information that is not needed to create a new PVC. Specifically, we delete all keys except `metadata`, `spec`, `apiVersion`, and `kind`. We also remove some additional metadata that was created by Kubernetes automatically. The resulting JSON manifest allows us to create new PVCs that will be bound to the correct PVs.

```json
{
  "apiVersion": "v1",
  "kind": "PersistentVolumeClaim",
  "metadata": {
    "labels": {},
    "name": "$NEW_PVC_NAME_i"
  },
  "spec": {
    "accessModes": [
      "ReadWriteOnce"
    ],
    "resources": {
      "requests": {
        "storage": "100Gi"
      }
    },
    "storageClassName": "azurefile-premium",
    "volumeMode": "Filesystem",
    "volumeName": "pvc-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
  }
}
```

### Delete Old STS

Next, we delete the old STS. Note that this will terminate the pods in no guaranteed order. If you need graceful termination, please scale the STS to 0 before deleting it.

```bash
kubectl delete sts $OLD_STS_NAME
```

### Delete Old PVCs

Since the PVCs do not get deleted automatically, we delete them manually.

```bash
kubectl delete pvc $OLD_PVC_NAME_i
```

### Make PVs Available Again

When a PVC is deleted and the PV is supposed to be reclaimed, it needs to be made available first. This is accomplished by nulling the PV `claimRef`.

```bash
kubectl patch pv $PV_NAME_i -p '{"spec":{"claimRef": null}}'
```

### Create new PVCs

After making the PVs available again, we create the PVCs from the derived JSON manifests.

```bash
kubectl apply -f $NEW_PVC_MANIFEST_FILE_i
```

### Create new STS

Finally, we can create the new STS. 

```bash
kubectl apply -f $NEW_STS_MANIFEST_FILE
```

Please find an example STS pseudo-YAML manifest below. Note that you would have to replace the variables to make it valid YAML. 

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: $NEW_STS_NAME
spec:
  selector:
    matchLabels:
      app: $NEW_STS_NAME
  serviceName: "new-app"
  replicas: 2
  template:
    metadata:
      labels:
        app: $NEW_STS_NAME
    spec:
      terminationGracePeriodSeconds: 10
      containers:
      - name: nginx
        image: k8s.gcr.io/nginx-slim:0.8
        ports:
        - containerPort: 80
          name: web
        volumeMounts:
        - name: $PVC_TEMPLATE_NAME
          mountPath: /usr/share/nginx/html
  volumeClaimTemplates:
  - metadata:
      name: $PVC_TEMPLATE_NAME
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 100Gi
      storageClassName: "azurefile-premium"
```

The new STS should now use the newly created PVCs and mount the data from the existing PVs.

# Summary and Discussion

In this blog post we have seen how PVs, PVCs, and STSs can be used to manage stateful applications on Kubernetes. We saw that by changing the reclaim policy of a PV it can be reclaimed manually. Creating PVCs that match the naming scheme of a new STS enables us to mount existing PVs into the STS replicas.

This technique is not only useful when renaming an existing STS, but can also be used to mount existing cloud storage volumes to an application that is deployed to Kubernetes for the first time.

Note that when using this method to rename an STS, there will be downtime. Zero-downtime migrations require more sophisticated methods, such as keeping the new and old STS active at the same time, streaming data, and potentially controlling live traffic through a higher level proxy. This requires application specific knowledge though and is beyond the scope of this post.

---

Cover image by <a href="https://unsplash.com/@ibrahimboran?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Ibrahim Boran</a> on <a href="https://unsplash.com/s/photos/helmsman?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
  