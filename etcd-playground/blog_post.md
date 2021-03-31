---
title: Managing Cluster Membership with Etcd
published: true
description: In this post we want to take a look at how we can utilize etcd to manage cluster membership in a distributed application.
tags: java, distributedsystems, cluster, etcd
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/zw2jhpftbtkf77mitdb1.png
---

# Introduction

In the era of global internet services, distributed systems have become ubiquitous. To harness the power of distributed computation and storage however, coordination of the involved parties is required. Distributed algorithms combine multiple physical components into a single logical component. When a user sends a request to a load balancing cluster or distributed database, the fact that there are multiple processes involved should be transparent.

A cluster is a collection of nodes which are connected through a network. Most distributed algorithms require a consistent (or at least eventually consistent) view of all nodes that are members of the cluster. In a distributed data processing engine for example, we use the cluster view to determine how to partition and distribute the data. How can we maintain a consistent view of the cluster inside each member?

Our goal is to maintain an in-memory membership list in each node. When a node joins or leaves the cluster, we need to update the membership lists in all nodes. Ideally, we also want to detect nodes that are down, since they might not be able to send a leave request in case of a hardware fault, out of memory error, or a similar problem.

Generally there are two types of distributed communication paradigms that can be used to share membership updates across a cluster: Decentralized and centralized approaches. Decentralized approaches include epidemic, or gossip-style protocols that distribute information among peers without a central coordinator / single source of truth. Centralized approaches rely on some sort of coordinator that acts as the single source of truth and distributes updates to all interested parties.

Gossip-style protocols became popular because of their scalability and the lack of a single point of failure. Since all members are equal, they can be replaced easily. In the face of concurrent modifications, however, resolving conflicts and reaching consensus can be challenging. This is why many applications rely on an external application to manage and track membership information consistently. Popular examples of such coordination services are [Apache Zookeeper](https://zookeeper.apache.org/), [Consul](https://www.consul.io/), or [etcd](https://etcd.io/).

In this post we want to take a look at how we can utilize etcd to manage cluster membership in a distributed application. We will combine different etcd APIs, such as the key value store, watchers and leases to build and maintain an in-memory membership list in our nodes. The application is written in Java and the [source code](https://github.com/FRosner/etcd-playground) is available on GitHub. The remainder of the post is structured as follows.

First, we will give an overview of the target architecture, introducing the different etcd functionality needed on a conceptual level. Afterwards, we will implement the design step by step. We are closing the post by summarizing the main findings and discuss potential improvements. The [source code](https://github.com/FRosner/etcd-playground) is available on GitHub.

# Design

The target architecture consists of a set of application nodes forming a cluster, and etcd. Each node stores its metadata in the etcd key-value (KV) store when joining the cluster. We can identify a node by a randomly generated UUID.

Every node subscribes to membership updates through the etcd watch API, in order to update its local state. Failure detection is implemented by connecting the metadata of a node to a lease. If the node fails to keep the lease alive because it crashed, it will be removed from the cluster automatically.

For more information about the etcd APIs, you can check ["Interacting with etcd"](https://etcd.io/docs/next/dev-guide/interacting_v3/). The following diagram illustrates the setup of a four-node cluster.

![four node cluster with etcd leases, watches, and key value store](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/zw2jhpftbtkf77mitdb1.png)

In the next section we will implement this functionality step by step.

# Implementation

## Foundations

As a first step we will implement a class encapsulating all functionality of a single node. Each node needs a connection to etcd and a membership list. Let's look at the entire file first and then go through it step by step.

```java
package de.frosner.server;

import ...

public class Node implements AutoCloseable {
  
  private final NodeData nodeData;

  private final Client etcdClient;

  private final ConcurrentHashMap<UUID, NodeData> clusterMembers = 
    new ConcurrentHashMap<>();

  public Node(List<URI> endpoints) {
    nodeData = new NodeData(UUID.randomUUID());
    etcdClient = Client.builder().endpoints(endpoints).build();
  }

  public void join() throws JoinFailedException {
    // TODO
  }

  public void leave() throws LeaveFailedException {
    // TODO
  }

  public Set<NodeData> getClusterMembers() {
    return ImmutableSet.copyOf(clusterMembers.values());
  }

  public NodeData getNodeData() {
    return nodeData;
  }

  @Override
  public void close() {
    leave();
    etcdClient.close();
  }
}
```

We want to associate metadata with each node. The `NodeData` class stores this information. Metadata could be system specific, such as the time the node joined the cluster, or application specific, such as the partitions the node is responsible for in case of a distributed database. For the sake of simplicity, we will only have a UUID inside `NodeData`.

To communicate with etcd, we will use [jetcd](https://github.com/etcd-io/jetcd). Each node has an etcd client that connects to our central etcd cluster. The membership list will be represented as a `ConcurrentHashMap<UUID, NodeData>` to ensure that we can safely interact with it from different threads later on.

We also created stubs for the `join()` and `leave()` methods, and implemented `AutoCloseable` so we can use the `Node` inside a try-with-resources statement. The `JoinFailedException` and `LeaveFailedException` are custom exceptions we created to indicate that something went wrong during joining or leaving the cluster.

Next, we will create a test skeleton, so we can check our implementation through automated tests. Thanks to the amazing [Testcontainers](https://www.testcontainers.org/) library it is very easy to create an etcd server as part of the test lifecycle. Here goes the test class:

```java
package de.frosner.server;

import ...

@Testcontainers
class NodeTest {

  private static final Network network = Network.newNetwork();
  private static final int ETCD_PORT = 2379;

  private ToxiproxyContainer.ContainerProxy etcdProxy;

  @AfterAll
  private static void afterAll() {
    network.close();
  }

  @Container
  private static final GenericContainer<?> etcd =
    new GenericContainer<>(EtcdContainer.ETCD_DOCKER_IMAGE_NAME)
      .withCommand("etcd",
        "-listen-client-urls", "http://0.0.0.0:" + ETCD_PORT,
        "--advertise-client-urls", "http://0.0.0.0:" + ETCD_PORT,
        "--name", NodeTest.class.getSimpleName())
      .withExposedPorts(ETCD_PORT)
      .withNetwork(network);

  @Container
  public static final ToxiproxyContainer toxiproxy = 
    new ToxiproxyContainer("shopify/toxiproxy:2.1.0")
      .withNetwork(network)
      .withNetworkAliases("toxiproxy");

  @BeforeEach
  public void beforeEach() {
      etcdProxy = toxiproxy.getProxy(etcd, ETCD_PORT);
  }

  private List<URI> getClientEndpoints() {
    return List.of(URI.create(
      "https://" + etcd.getContainerIpAddress() +
        ":" + etcd.getMappedPort(ETCD_PORT)
    ));
  }

  private List<URI> getProxiedClientEndpoints() {
    return List.of(URI.create(
      "https://" + etcdProxy.getContainerIpAddress() + 
        ":" + etcdProxy.getProxyPort()
    ));
  }

  @Test
  public void testNodeJoin() throws Exception {
    try (Node node = new Node(getClientEndpoints())) {
      node.join();
    }
  }
}
```

The skeleton contains a single test that makes a node join the cluster and then closes it, causing it to leave again. Since we did not implement any functionality, yet, we do not expect anything to happen.

Note that we are creating a custom docker network and a [Toxiproxy](https://github.com/Shopify/toxiproxy) container. For the initial tests this is not required, but we need it later on when we want to simulate network failures. For the sake of simplicity we will only use a single etcd node. In a production scenario you should have an etcd cluster of at least three nodes.

Let's implement a basic join algorithm next.

## Joining a Cluster

When joining the cluster, a node puts its metadata to etcd. We are storing all node metadata under `NODES_PREFIX = "/nodes/"`, which enables us to watch for membership changes based on this prefix later on. 

```java
public void join() throws JoinFailedException {
  try {
    putMetadata();
  } catch (Exception e) {
    throw new JoinFailedException(nodeData, e);
  }
}

private void putMetadata() throws Exception {
  etcdClient.getKVClient().put(
    ByteSequence.from(
      NODES_PREFIX + nodeData.getUuid(),
      StandardCharsets.UTF_8
    ),
    ByteSequence.from(
      JsonObjectMapper.INSTANCE.writeValueAsString(nodeData),
      StandardCharsets.UTF_8
    )
  ).get(OPERATION_TIMEOUT, TimeUnit.SECONDS);
}
```

Given this implementation, we can modify the existing test case to query etcd for the node metadata.

```java
@Test
public void testNodeJoin() throws Exception {
  try (Node node = new Node(getClientEndpoints())) {
    node.join();
    assertThat(getRemoteState(node.getNodeData()))
      .isEqualTo(node.getNodeData());
  }
}

private NodeData getRemoteState(NodeData node) throws Exception {
  String nodeDataJson = etcdClient.getKVClient()
    .get(ByteSequence.from(Node.NODES_PREFIX + node.getUuid(),
      StandardCharsets.UTF_8))
    .get(Node.OPERATION_TIMEOUT, TimeUnit.SECONDS)
    .getKvs()
    .get(0)
    .getValue()
    .toString(StandardCharsets.UTF_8);
  return JsonObjectMapper.INSTANCE
    .readValue(nodeDataJson, NodeData.class);
}
```

Now a node can join the cluster but it will not notice when other nodes join as well. So let's implement that functionality next. 

## Updating Cluster Membership

When constructing a new node object, we want to keep the membership list up-to-date. To accomplish this, we first load an existing snapshot of the cluster metadata and then watch for changes starting from the last seen revision. The updated constructor looks like this:

```java
public Node(List<URI> endpoints, long leaseTtl) throws Exception {
  nodeData = new NodeData(UUID.randomUUID());
  etcdClient = Client.builder().endpoints(endpoints).build();
  long maxModRevision = loadMembershipSnapshot();
  watchMembershipChanges(maxModRevision + 1);
}
```

Loading the snapshot is done using the key value API by providing a prefix as an additional `GetOption`. We then populate `clusterMembers` based on the returned values and calculate the maximum data revision. 

```java
private long loadMembershipSnapshot() throws Exception {
  GetResponse response = etcdClient.getKVClient().get(
    ByteSequence.from(NODES_PREFIX, StandardCharsets.UTF_8),
    GetOption.newBuilder()
      .withPrefix(ByteSequence.from(NODES_PREFIX, StandardCharsets.UTF_8))
      .build()
  ).get(OPERATION_TIMEOUT, TimeUnit.SECONDS);
  
  for (KeyValue kv : response.getKvs()) {
    NodeData nodeData = JsonObjectMapper.INSTANCE.readValue(
      kv.getValue().toString(StandardCharsets.UTF_8),
      NodeData.class
    );
    clusterMembers.put(nodeData.getUuid(), nodeData);
  }
  
  return response.getKvs().stream()
    .mapToLong(KeyValue::getModRevision).max().orElse(0);
}
```

Using the watch API we can create a watch for the same prefix, starting from the next revision, so we do not lose any membership changes that might happen between the snapshot and the watch query. We handle the incoming watch events in a separate function `handleWatchEvent`.

```java
private void watchMembershipChanges(long fromRevision) {
  logger.info("Watching membership changes from revision {}", fromRevision);
  watcher = etcdClient.getWatchClient().watch(
    ByteSequence.from(NODES_PREFIX, StandardCharsets.UTF_8),
    WatchOption.newBuilder()
      .withPrefix(ByteSequence.from(NODES_PREFIX, StandardCharsets.UTF_8))
      .withRevision(fromRevision)
      .build(),
    watchResponse -> {
      watchResponse.getEvents().forEach(this::handleWatchEvent);
    },
    error -> logger.error("Watcher broke", error),
    () -> logger.info("Watcher completed")
  );
}
```

The watch response might contain `PUT` or `DELETE` events, depending on whether nodes join or leave the cluster. `PUT` events contain the updated node metadata which we can add to `clusterMembers`. `DELETE` events contain the key that has been deleted, from which we can extract the node UUID to update `clusterMembers` accordingly. Note that in production you might want to handle events on a separate thread to not block the gRPC executor thread.

```java
private void handleWatchEvent(WatchEvent watchEvent) {
  try {
    switch (watchEvent.getEventType()) {
      case PUT:
        NodeData nodeData = JsonObjectMapper.INSTANCE.readValue(
          watchEvent.getKeyValue().getValue().toString(StandardCharsets.UTF_8),
          NodeData.class
        );
        clusterMembers.put(nodeData.getUuid(), nodeData);
        break;
      case DELETE:
        String etcdKey = watchEvent.getKeyValue().getKey()
          .toString(StandardCharsets.UTF_8);
        UUID nodeUuid = UUID.fromString(extractNodeUuid(etcdKey));
        clusterMembers.remove(nodeUuid);
        break;
      default:
        logger.warn("Unrecognized event: {}", watchEvent.getEventType());
    }
  } catch (Exception e) {
    throw new RuntimeException("Failed to handle watch event", e);
  }
}

private String extractNodeUuid(String etcdKey) {
  return etcdKey.replaceAll(Pattern.quote(NODES_PREFIX), "");
}
```

Given our new functionality to update the membership list, we can create a new test case where two nodes join the cluster and expect that to be reflected in the local state of each node eventually. Thanks to the [Awaitility](https://github.com/awaitility/awaitility) DSL we can conveniently wait for the eventual update to happen.

```java
@Test
public void testTwoNodesJoin() throws Exception {
  try (Node node1 = new Node(getClientEndpoints())) {
    node1.join();
    try (Node node2 = new Node(getClientEndpoints())) {
      node2.join();
      Awaitility.await("Node 1 to see all nodes")
        .until(() -> node1.getClusterMembers()
        .containsAll(List.of(node1.getNodeData(), node2.getNodeData())));
      Awaitility.await("Node 2 to see all nodes")
        .until(() -> node2.getClusterMembers()
        .containsAll(List.of(node1.getNodeData(), node2.getNodeData())));
    }
  }
}
```

Next, let's see how we can detect failed nodes and remove them from the cluster automatically.

## Failure Detection

Failure detection will be performed by a simple centralized heartbeat failure detector. Etcd provides a lease API for that purpose. Leases expire after a configurable amount of time unless they are kept alive. We will store the lease ID and the keep alive client in new fields in order to clean up the lease when leaving later on. 

```java
private volatile long leaseId;

private volatile CloseableClient keepAliveClient;
```

Now we modify the `join` method to first request a lease grant before putting the metadata.

```java
public void join() throws JoinFailedException {
  try {
    grantLease();
    putMetadata();
  } catch (Exception e) {
    throw new JoinFailedException(nodeData, e);
  }
}
```

Granting the lease is done using the lease API. When the lease is granted, we have to keep it alive. We can provide a `StreamObserver` that reacts to successful, failed, or completed keep-alive operations, as shown in the following code.

```java
private void grantLease() throws Exception {
  Lease leaseClient = etcdClient.getLeaseClient();
  leaseClient.grant(5) // 5 sec TTL
    .thenAccept((leaseGrantResponse -> {
      leaseId = leaseGrantResponse.getID();
      logger.info("Lease {} granted", leaseId);
      keepAliveClient = leaseClient.keepAlive(leaseId,
        new StreamObserver<>() {
          @Override
          public void onNext(LeaseKeepAliveResponse leaseKeepAliveResponse) {
            // you can increment some metric counter here
          }
          @Override
          public void onError(Throwable throwable) {
            // log and handle error
          }
          @Override
          public void onCompleted() {
            // we're done, nothing to do
          }
        });
    })).get(OPERATION_TIMEOUT, TimeUnit.SECONDS);
}
```

The node metadata is attached to the newly acquired lease, so it gets deleted automatically when the lease expires or is removed.

```java
private void putMetadata() throws Exception {
  etcdClient.getKVClient().put(
    ByteSequence.from(
      NODES_PREFIX + nodeData.getUuid(),
      StandardCharsets.UTF_8
    ),
    ByteSequence.from(
      JsonObjectMapper.INSTANCE.writeValueAsString(nodeData),
      StandardCharsets.UTF_8
    ),
    PutOption.newBuilder().withLeaseId(leaseId).build()
  ).get(OPERATION_TIMEOUT, TimeUnit.SECONDS);
}
```

To test the lease functionality, we make use of the [Toxiproxy Testcontainers module](https://www.testcontainers.org/modules/toxiproxy/) to introduce network delay that exceeds the lease TTL, triggering the removal of the failed node.

```java
@Test
public void testTwoNodesLeaseExpires() throws Exception {
  try (Node node1 = new Node(getClientEndpoints())) {
    node1.join();
    try (Node node2 = new Node(getProxiedClientEndpoints())) {
      node2.join();

      Awaitility.await("Node 1 to see all nodes")
        .until(() -> node1.getClusterMembers()
          .containsAll(List.of(node1.getNodeData(), node2.getNodeData())));

      etcdProxy.toxics()
        .latency("latency", ToxicDirection.UPSTREAM, 6000);

      Awaitility.await("Node 1 to see that node 2 is gone")
        .until(() -> node1.getClusterMembers()
          .equals(Set.of(node1.getNodeData())));
    }
  }
}
```

Note that additional actions can be added as a reaction to a lease which failed to be kept-alive. Nodes could attempt to rejoin the cluster, for example. The concrete actions depend on the application, obviously. Last but not least, let's implement a graceful leave operation.

## Leaving a Cluster

Leaving a cluster is as simple as revoking the lease. Etcd will automatically remove all keys associated with the lease, essentially removing the node metadata. 

```java
public void leave() throws LeaveFailedException {
  try {
    logger.info("Leaving the cluster");
    if (keepAliveClient != null) {
      keepAliveClient.close();
    }
    etcdClient.getLeaseClient().revoke(leaseId)
      .get(OPERATION_TIMEOUT, TimeUnit.SECONDS);
  } catch (Exception e) {
    throw new LeaveFailedException(nodeData, e);
  }
}
```
We extend the test suite by adding a test case where a node joins and leaves, and the remaining nodes should observe the membership changes.

```java
@Test
public void testTwoNodesJoinLeave() throws Exception {
  try (Node node1 = new Node(getClientEndpoints())) {
    node1.join();
    try (Node node2 = new Node(getClientEndpoints())) {
      node2.join();
      Awaitility.await("Node 1 to see all nodes")
        .until(() -> node1.getClusterMembers()
          .containsAll(List.of(node1.getNodeData(), node2.getNodeData())));
      Awaitility.await("Node 2 to see all nodes")
        .until(() -> node2.getClusterMembers()
          .containsAll(List.of(node1.getNodeData(), node2.getNodeData())));
    }
    Awaitility.await("Node 1 to see that node 2 is gone")
      .until(() -> node1.getClusterMembers()
        .equals(Set.of(node1.getNodeData())));
  }
}
```

That's it! We have a working implementation of a node that can join and leave a cluster and manages membership through etcd! 

# Summary and Discussion

In this post we have implemented a very basic distributed application. Etcd manages and propagates the cluster membership through its key-value API and watch API, but also acts as a failure detector thanks to its lease API. Implementing automated tests was easy thanks to Testcontainers. The Toxiproxy module provides a convenient way to simulate faults during test execution.

Note that the Java code we wrote is only a foundation. Depending on the tasks your distributed application is supposed to perform, you will have to add functionality to the join and leave algorithm, for example. Etcd also provides a lock API, which you can use to add additional coordination.
