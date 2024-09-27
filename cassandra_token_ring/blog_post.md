---
title: Visualizing the Apache Cassandra Token Ring with Plotly
published: true
description: What is the Cassandra token ring and how can you visualize it using Plotly? Learn how to calculate token ranges and represent them in a circular plot. 
tags: python, plotly, cassandra, database
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/nk3c39owdq5zqgrxqhkj.png
---

## Cassandra's Partitioning Mechanism

[Apache Cassandra](https://cassandra.apache.org/_/index.html) is a powerful, distributed NoSQL database designed to handle large amounts of data across many servers while providing linear horizontal scalability, high availability with flexible consistency guarantees, as well as fault tolerance.

One of the core mechanisms behind Cassandra's scalability is the data partitioning based on **consistent hashing**. In a typical hashing scenario, a hash function takes an input (e.g., the primary key of a row) and maps it to a fixed output range. In a distributed database, each node could be responsible for a subset of that range. However, if nodes are added or removed, the entire data distribution could change, causing large-scale data movement between nodes.

Consistent hashing solves this problem by mapping both data and nodes onto the same hash ring (a conceptual circle). Here’s how it works:

- **The Hash Ring.** Imagine a circle where hash values are placed in a clockwise manner, ranging from 0 to the maximum value of the hash function. Database nodes are placed on this circle based on their own hash value. Data is also hashed and placed on the circle.
- **Assigning Data to Nodes.** Data is assigned to the first node clockwise from its position on the ring. This node becomes responsible for that piece of data.
- **Node Addition/Removal.** When a node is added, only the data between the new node and its predecessor in the ring is reassigned. When a node is removed, its data is reassigned to the next node clockwise.

We call each position on the ring a token. When a row needs to be stored, its primary key is hashed to calculate its token. The token is then used to determine which node stores the data by walking the ring until the next token owned by a node is found. This process ensures that data is evenly distributed across all nodes, avoiding hot spots and ensuring the cluster remains balanced as nodes are added or removed. This algorithm effectively partitions the token ring into ranges, with each range assigned to a node.

To make this algorithm more resilient and flexible, Cassandra uses a concept called **virtual nodes** (vnodes). Instead of assigning a single large token range to each node, Cassandra divides the token space into many smaller ranges and assigns multiple vnodes to each physical node. This allows the cluster to be more evenly balanced, especially when nodes are added or removed, since the system can redistribute small token ranges across the remaining nodes, avoiding load imbalances. 

It also allows to combine heterogeneous hardware in a single cluster, as you can adjust the number of vnodes based on the available resources on your physical node.

## Why Visualize the Token Ring?

Cassandra's distributed nature, combined with its use of consistent hashing and vnodes, makes it an efficient and scalable database. However, one of the challenges that arises when operating a Cassandra cluster is understanding how the data is distributed across nodes. Although Cassandra ensures that tokens are distributed evenly across the cluster, certain situations - such as manual node additions, removals, misconfiguration, or hardware failures - can lead to unbalanced token distribution.

For Cassandra operators and users, having insight into the token distribution can be a useful tool to debug issues with the database. Token imbalances can lead to unequal data distribution, resulting in hotspots where certain nodes handle significantly more traffic or store more data than others. This can cause performance degradation, uneven resource usage, and even outages.

While Cassandra offers command-line tools to check token ranges and node responsibilities (such as `nodetool ring`), these tools output the data in a raw, tabular format that can be difficult to interpret.

## Fetching Token Ranges

Cassandra uses [Murmur3](https://github.com/apache/cassandra/blob/trunk/src/java/org/apache/cassandra/dht/Murmur3Partitioner.java), a hashing function that generates 64-bit tokens in the range of {% katex inline %} [-2^{63},2^{63} - 1] {% endkatex %}. Each vnode in the cluster assigned a token it is responsible for. The token marks the end of a range, and the previous token defines the start. To visualize the token ring, we first need to calculate the token ranges, by:

1. Gathering all tokens from all nodes
2. Sorting the tokens
3. Pairing each token with the previous one to compute the range for each node

The [Cassandra drivers](https://docs.datastax.com/en/developer/java-driver/4.2/manual/core/metadata/token/index.html) have access to the token metadata, which includes both the raw tokens and the calculated ranges:

```java
Metadata metadata = session.getMetadata();
TokenMap tokenMap = metadata.getTokenMap().get();

Set<TokenRange> ring = tokenMap.getTokenRanges();
// Returns [Murmur3TokenRange(Murmur3Token(12), Murmur3Token(2)),
//          Murmur3TokenRange(Murmur3Token(2), Murmur3Token(4)),
//          Murmur3TokenRange(Murmur3Token(4), Murmur3Token(6)),
//          Murmur3TokenRange(Murmur3Token(6), Murmur3Token(8)),
//          Murmur3TokenRange(Murmur3Token(8), Murmur3Token(10)),
//          Murmur3TokenRange(Murmur3Token(10), Murmur3Token(12))]
```

## Visualizing Token Ranges

Now that we’ve calculated the token ranges, we can proceed to visualize them. To represent the Cassandra token ring, we use Plotly’s polar plot feature, which is perfect for this kind of circular visualization.

Here’s the function that creates the visualization:

```python
max_token = math.pow(2, 64)

def plot_token_ranges(token_ranges: dict[str, list[(int, int)]]):
    fig = graph_objects.Figure()
    nodes = list(token_ranges.keys())
    colors = plotly.express.colors.sample_colorscale("Rainbow", len(nodes))
    color_map = {node: color for node, color in zip(nodes, colors)}

    for node, ranges in token_ranges.items():
        v_node_idx = 0
        for start, end in ranges:
            if end < start:
                range_width = abs(end + max_token - start)
            else:
                range_width = abs(end - start)
            # Theta needs to be in the middle of the range, because
            # the polar bar gets drawn from theta width/2 in both directions
            theta = (start + range_width / 2) * 360 / max_token
            fig.add_trace(
                graph_objects.Barpolar(
                    r=[1],
                    theta=[theta],
                    width=range_width * 360 / max_token,
                    customdata=[[start, end]],
                    hovertemplate="[%{customdata[0]}, %{customdata[1]}]",
                    name=node,
                    legendgroup=node,
                    marker_color=color_map[node],
                    showlegend=(v_node_idx == 0),
                )
            )
            v_node_idx += 1

    fig.show()
```

- First we pass a token ranges dictionary, where each key is a node, and the value is a list of token ranges for that node (one per vnode).
- Then we assign each node a unique color from a predefined color scale for easy identification in the visualization.
- For each node, we loop through its token ranges and calculate:
  - The width of each token range (`range_width`).
  - The angle (`theta`) where the range should be displayed on the circular plot.
- Each token range is represented as a polar bar. The hover text displays the start and end of each range, and we ensure the legend appears only once per node.

The following screenshot shows the output of the function for a simple three-node cluster.

![Example cluster with 3 nodes, 8 vnodes per node](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/eloewrn3bc86wt8n6tc2.png)

## Taking Replication Into Account

Most datasets stored in Cassandra are configured with a replication factor (RF) > 1, which means that each row is replicated to multiple nodes. Replication increases data availability and fault tolerance at the cost of storage and increased coordination between nodes.

How exactly the data is replicated depends on the configured replication strategy. If your cluster spans multiple racks (e.g. availability zones), you should use the [`NetworkTopologyStrategy`](https://docs.datastax.com/en/cassandra-oss/3.x/cassandra/architecture/archDataDistributeReplication.html). This strategy determines the additional replicas by walking the ring clockwise until it finds a node in a different rack, repeating the process until it reaches the desired number of replicas.

What does that mean for our token ring visualization? When looking at token ownership, i.e., which nodes own a given token, we would have to add the rack dimension to the plot, and the viewer would have to mentally perform the clockwise "walk" to determine the replicas. 

An alternative approach is possible if the replication factor is equal to the number of racks. In that case, the algorithm can be simplified by calculating a separate token ring for each rack. We then only consider the nodes in each rack to calculate the ranges and can use the algorithm with RF = 1 to determine the node that owns the token in each rack. To visualize the ownership we can either plot the ring for each rack, or even overlay the different plots.

The following animation shows the per-rack token ranges for a six node cluster hosted across three racks and a replication factor of three:

![ring per rack with tabs](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/84hczfr8qiak7z7sxxh1.gif)

## Overlaying SSTable Ranges

Cassandra's storage engine is based on [Log-Structured Merge (LSM) Trees](https://www.cs.umb.edu/~poneil/lsmtree.pdf). Data is written to a memtable in memory, and when the memtable reaches a certain size, it is flushed to disk as an SSTable. SSTables are immutable and are periodically merged into larger SSTables to reduce the number of files on disk.

The data in the SSTable files is sorted by the partition key. By computing the tokens of the partitions within the file, we can derive a token range based on the minimum and maximum token it contains. This allows us to overlay the token ranges of the nodes with an SSTable range.

To add the SSTable overlay, we extend the code, adding two additional parameters `sstable_min_token` and `sstable_max_token` to the function. We then add a new barpolar trace for the SSTable:

```python
if sstable_max_token < sstable_min_token:
    sstable_range_width = abs(sstable_max_token + max_token - sstable_min_token)
else:
    sstable_range_width = abs(sstable_max_token - sstable_min_token)
sstable_theta = (sstable_min_token + sstable_range_width / 2) * 360 / max_token
fig.add_trace(
    graph_objects.Barpolar(
        r=[0.5],
        theta=[sstable_theta],
        width=sstable_range_width * 360 / max_token,
        customdata=[[sstable_min_token, sstable_max_token]],
        hovertemplate="[%{customdata[0]}, %{customdata[1]}]",
        name=sstable_name,
        legendgroup=sstable_name,
        marker_color="grey",
    )
)
```

When calculating the width of the SSTable, we need to take into account that the max token might be smaller than the min token, which effectively means that the range wraps around the ring. We choose `r=[0.5]` to place the SSTable overlay closer to the center of the plot, and color it grey to distinguish it from the token ranges.

The following screenshot shows our updated graph with an SSTable file overlapping with one vnode of the first node in the first rack.

![SSTable token range overlay](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/5h3os5cd27iz5mf2zdpm.png)

# Conclusion

Visualizing the Cassandra token ring with Plotly was a fun exercise to understand how tokens are distributed across nodes in a cluster, how replication works, and how SSTables fit into the mix. Looking into the token distribution helps you identify potential token imbalances.

If you do not want to worry about token ranges, vnodes, replication and SSTable files, and just want to benefit from the scalability and fault tolerance of Cassandra, consider using a managed service such as [DataStax AstraDB](https://www.datastax.com/products/datastax-astra?utm_medium=social_organic&utm_source=twitter&utm_campaign=frank_rosner).

---

If you liked this post, you can [support me on ko-fi](https://ko-fi.com/frosnerd).
