---
title: Read Efficient Data Structures
published: true
description: In this post we want to take a closer look at data structures designed for low read overhead that are commonly used in practice, i.e. hash tables, red-black trees, and skip lists. This blog post is the second part of the RUM series.
tags: programming, learning, java, computerscience
cover_image: https://thepracticaldev.s3.amazonaws.com/i/0lleley5lwzxtvufva2u.jpg
---

# Introduction

The [previous blog post](https://dev.to/frosnerd/rum-conjecture---reasoning-about-data-access-4781) introduced the RUM conjecture. It describes the trade-off between read (RO), update (UO), and memory (MO) overheads that one should take into account when designing data structures and access methods.

In this post we want to take a closer look at data structures designed for low read overhead that are commonly used in practice, i.e. hash tables, red-black trees, and skip lists. This blog post is the second part of the RUM series:

1. [RUM Conjecture - Reasoning About Data Access](https://dev.to/frosnerd/rum-conjecture---reasoning-about-data-access-4781)
2. [Read Efficient Data Structures](#)
3. [Update Efficient Data Structures](https://dev.to/frosnerd/update-efficient-data-structures-7cn)
4. Memory Efficient Data Structures (TBD)
5. Adaptive Data Structure (TBD)

In order to compare the different implementations we are using the same example as in the previous post. The task is to implement a set of integers, this time focusing on a small amount of read overhead.

The post is structured as follows. In the first section we want to recap the solution from the last post which has minimum read overhead. The following sections take a closer look at three practical alternatives, starting with hash tables, then red-black trees, and closing with skip lists. The final section is wrapping up by comparing the three different data structures from a theoretical point of view as well as conducting simple run time experiments.

# Minimizing The Read Overhead

We have seen an optimal implementation in terms of read overhead: Given possible integers from 0 to 1000, we can utilize a boolean array `a` of size `1001`. The array elements are initialized with `false`. To mark an integer `i` as member of the set, we set `a[i] := true`. Recall the following overheads:

- *RO = 1*
- *UO = 1*
- *MO → ∞*

This is impractical for most real life scenarios as the memory overhead grows with the number of possible values. While it might be theoretically possible to use this method for integers, it gets impossible if we're trying to store strings in a set, for example. How can we reduce the memory overhead without losing too much read (and write) performance?

In practice this is achieved by using hash, sorted tree or list based approaches. Let's take a look at three data structures designed to be read efficient without sacrificing too much of write and memory performance: Hash tables, red-black trees, and skip lists.

# Hash Tables

## Concept

The idea of hash tables is similar to the one used in the optimal solution. Instead of reserving a boolean slot for every possible integer we limit the space to an integer array *a* of size *m*. Then we pick a function *h* such that for each integer *i: h(i) ∈ [0..m-1]*. This function can be used to compute the array index and we can store *i* in `a[h(i)]`.

The following diagram illustrates how the integer 3 is stored in the set implemented using a hash table. We compute *h(3)* and store the value in the corresponding field of the array.

![hash table](https://thepracticaldev.s3.amazonaws.com/i/bj1cw270wi72zfgb73yv.png)

How do we pick *h*? A practical choice for *h* is to reuse an existing cryptographic hash function (e.g. [MD5](https://en.wikipedia.org/wiki/MD5)) and take the resulting value modulo *m*. The disadvantage is that these hash functions might be slow. This is why Java, e.g., relies on custom hash functions for every data type (e.g. [`String`](http://grepcode.com/file/repository.grepcode.com/java/root/jdk/openjdk/6-b14/java/lang/String.java#String.hashCode%28%29)).

If we know all possible values upfront we can pick a [perfect hash function](https://en.wikipedia.org/wiki/Perfect_hash_function). But this is not possible most of the time. What do we do if two integers *i* and *j* get mapped to the same index *h(i) = h(j)*? There are different techniques how to resolve these so called collisions.

One collision resolution method is [separate chaining](https://en.wikipedia.org/wiki/Hash_table#Separate_chaining). In separate chaining we do not store the actual values in the array but another layer of data structures. A value is read from the hash table by first computing the array index and then querying the data structure stored there. Possible candidates are tree or list based structures as introduced in the following sections. But it is also common to simply use a linked list, if the number of collisions is expected to be low.

Another commonly used method is called [open addressing](https://en.wikipedia.org/wiki/Open_addressing). If a collision happens, we compute a new index based on some probing strategy, e.g. linear probing with *h(i) + 1*.

## RUM Overheads

The RUM overheads of a hash table implementation heavily depends on the selected hash function, the array size *m*, as well as the collision resolution strategy. This makes it possible to tune the RUM overheads of your hash table.

If there is no collision, the read overhead is influenced only by the overhead of computing *h(i)*. A smaller overhead in evaluating the hash function results in a smaller overall read overhead. In case of a collision there is additional overhead which depends on the resolution strategy. Although it is useful to avoid collisions by choosing an almost perfect hash function, the total overhead might be smaller if we make the hash function reasonably fast and live with a few extra operations when resolving collisions.

As an update requires a read operation first, the update overhead is equal to the read overhead, plus an insertion / deletion operation on either the array or the chained data structures in case of separate chaining.

The memory overhead is indirectly proportial to the load factor (*n/m*). We also have to take additional memory into account if we are using separate chaining for collision resolution.

If we are inserting more and more data, the memory overhead decreases. However the read overhead increases as we have to resolve more collisions. In this case, it is possible to rescale the hash table, which requires a full copy of the existing data into a bigger array and a re-computation of all hash values.

## Asymptotic Complexity

Read and update operations have constant asymptotic complexity on average, as computing the hash value takes constant time, independent of the amount of data stored in the table. In the worst case (all *n* input values get the same hash value), we have *n - 1* collisions to resolve. Thus the worst case performance is as bad as if we stored the data in an unordered array and performed a full scan. If *m* is chosen as small as possible and the hash table is resized if required, the amortized memory requirement is linear in the number of values stored in the set.

Type | Average	| Worst case
--- | --- | ---
Read | *O(1)*	| *O(n)*
Update | *O(1)* |	*O(n)*
Memory | *O(n)* | *O(n)*

Read performance of hash table based data structures is constant on average. However, by its design it only supports point queries efficiently. If your access patterns contain range queries, e.g. checking if the integers *[0..500]* are contained in the set, hash sets are not the right choice. To efficiently support range queries, we can store the data in a sorted manner. One of the most common types of data structure for this use case are binary search trees.

# Red-Black Trees

## Concept

In a [binary search tree](https://en.wikipedia.org/wiki/Binary_search_tree), the data is stored in the nodes. Each node has up to two child nodes. The left sub-tree contains only elements that are smaller than the current node. The right sub-tree contains only larger elements. If the tree is balanced, i.e. for all nodes the height of the left and right sub-trees differ at most by 1, searching a node takes logarithmic time. The following picture illustrates how to store the set *{0..6}* in a binary search tree.

![binary search tree](https://thepracticaldev.s3.amazonaws.com/i/yqy1fxkchdm2trqr8t3m.png)

The question is how do we keep the tree balanced when inserting and deleting elements? We need to design our insertion and deletion algorithm accordingly to make the tree self-balancing. A widely used variant of such self-balancing binary search trees are red-black trees [1].

In a [red-black tree](https://en.wikipedia.org/wiki/Red%E2%80%93black_tree), each node stores its color in addition to the actual value. The color information is used when inserting or deleting nodes in order to determine how to rebalance the tree. Rebalancing is done by changing color and rotating sub-trees around their parents recursively until the tree is balanced again.

Explaining the algorithm in detail is beyond the scope of this post, so please feel free to look it up on your own. Also there is an amazing [interactive visualization](https://www.cs.usfca.edu/~galles/visualization/RedBlack.html) of red-black trees by David Galles which is worth checking out. Now let's take a look at the same example set *{0..6}* stored in a red-black tree.

![red-black tree](https://thepracticaldev.s3.amazonaws.com/i/dm6ki4yv0l950r1ihsln.png)

Note that red-black trees are not necessarily balanced perfectly, but rather in terms of of the height of black nodes in the sub-trees. Due to the invariants of red-black trees, a balanced red-black tree is never much worse than a perfectly balanced tree, i.e. they have the same asymptotic complexity for searches.

## RUM Overheads

The RUM overheads in self-balancing binary search trees depend on the algorithm to keep the tree balanced. In red-black trees rebalancing happens recursively and might affect nodes all the way up to the root.

A read operation involves traversing the tree until the element is found. If the element is stored in a leaf node, it takes at most *log(n) + c* traversal steps, with *c* being the potential overhead if the tree is not perfectly balanced.

As in the hash table based implementation, an update operation on a red-black tree based set requires a read operation first. In addition to the read overhead, the update overhead depends on the value to be updated, whether it should be inserted and removed, as well as the current structure of the tree. In the most trivial cases an update only requires a single operation on the parent node, i.e. modifying the pointer to the child. Worst case we have to rebalance the tree all the way up to the root.


## Asymptotic Complexity

Read operations have logarithmic complexity as red-black trees are balanced, thus searching a value conceptually corresponds to a [binary search](https://en.wikipedia.org/wiki/Binary_search_algorithm). Update operations have the same complexity, as they require logarithmic search, plus worst case rebalancing operations from a leaf to the root, which is again logarithmic. As we require one node per value, the memory requirements are linear.

Type | Average	| Worst case
--- | --- | ---
Read | *O(log n)*	| *O(log n)*
Update | *O(log n)* |	*O(log n)*
Memory | *O(n)* | *O(n)*

We have seen that self-balancing binary search trees are useful data structures if range queries are required or the data should be presented to the user in a sorted manner. However, the algorithms required to make them self-balancing are rather complex. In addition, if we want to support concurrent access, we have to lock parts of the tree during rebalancing. This might lead to unpredictable slow-downs if a lot of rebalancing is required.

How can we design a concurrency-friendly data structure that also supports logarithmic search cost?

# Skip Lists

## Concept

By design linked lists are very concurrency-friendly as updates are highly localized and cache-friendly [3]. If our data would be a sorted sequence, we could utilize binary search to achieve logarithmic read complexity. The problem with a sorted linked list is, however, that we cannot access a random element of the list. Thus, binary search is not possible. Or is it? This is where skip lists come in.

Skip lists are a probabilistic alternative to balanced trees [4, 5, 6]. The core idea of a skip list is to provide express lanes to later parts of the data using skip pointers.

To perform binary search we have to compare our query against the median. If the median is not the element we are looking for, we take either the left or right sublist and recursively repeat the median comparison. This means we do not really need complete random access, but rather access to the median of the current sublist. The following figure illustrates how we can achieve this using skip pointers.

![perfect skip list](https://thepracticaldev.s3.amazonaws.com/i/omhubcge7dt50dodwkl1.png)

This skip list has three levels. The lowest level contains the full set of integers *{0..6}*. The next level only *{1, 3, 5}*, while the upper level only contains *{3}*. We are adding two artificial nodes *-∞* and *∞*. Each node holds a value and an array of pointers, one to each successor on the corresponding level. If we now want to check if *4* is member of the set, we proceed as follows.

- Start from the leftmost element (*-∞*) with the top most pointer (level 3)
- Compare the query (*4*) with the next element in the current level (*3*)
- As *3 < 4*, we move one element to the right (to *3*)
- We then again compare the query (*4*) with the next element in the current level (*∞*)
- As *∞ >= 4*, we move one level down (to level 2)
- We then again compare the query (*4*) with the next element in the current level (*5*)
- As *5 >= 4*, we move one level down (to level 1)
- We then again compare the query (*4*) with the next element in the current level (*4*)
- As *4 = 4*, the query returns successfully

This algorithm works perfectly if the list is static and we can build up the skip pointers to support our binary search. In a real life scenario, however, we want to be able to insert or delete elements. How can we efficiently support inserts and deletions without losing the nice properties of well-placed skip pointers? Completely rebuilding the skip list after each modification is not practical. In the end we want to have highly localized updates to support high concurrency.

We introduced skip lists as a *probabilistic* alternative to balanced trees. And the probabilistic part is exactly the one needed to solve the problem of where and how to place skip pointers.

For each element we want to insert into the skip list, we first search for its position in the existing elements. Then we insert it into the lowest level. Afterwards we flip a coin. If the coin shows tails, we are done. If it shows heads, we "promote" the element to the next level, inserting it into the higher level list, and repeat the procedure. In order to delete an element, we search for it and then simply remove it from all levels. Feel free to check out this amazing [interactive skip list visualization](https://people.ok.ubc.ca/ylucet/DS/SkipList.html).

Due to the non-deterministic nature of the insertion algorithm, real-life skip lists do not look as optimal as the one in the figure above. They will most likely look a lot more messy.  Nevertheless it can be shown that the expected search complexity is still logarithmic [7].

## RUM Overheads

The RUM overheads in skip lists are non-deterministic. This is also why the asymptotic complexity analysis is more complex than usual, as it involves probability theory as well. Nevertheless we are going to take a look at the different overheads on a conceptual level.

A read operation requires walking through a sequence of horizontal and vertical pointers, comparing the query against different list elements along the way. This means that there is a potentially high number of auxiliary reads until the query can return.

As you might have guessed, we require a read operation before we can perform an update. The number of auxiliary updates, i.e. promotions, are non-deterministic. However they are completely local and do not depend on the structure of the remaining skip list. This makes it easy to parallelize updates.

The memory overhead depends on the number of promotions, as we have to store additional pointers for each promotion. By using a non-fair coin, i.e. using a probability for a promotion / non-promotion of *[p, 1-p]* with *0 < p < 1* instead of *[0.5, 0.5]*, we can actually tune the memory overhead, potentially trading against additional read and update overhead. If we chose *p = 0* we would get a linked list which has the minimum memory overhead we can achieve in this data structure. If we choose *p* to be too large I believe that both the memory and the read overhead increases, as we have to potentially perform a lot of vertical moves along the different levels.

## Asymptotic Complexity

There are different ways to analyze the asymptotic complexity of skip-lists. Two commonly used methods are to look at the expected asymptotic complexity or an asymptotic complexity that holds [with high probability](https://en.wikipedia.org/wiki/With_high_probability). For simplicity reasons, let us take a look at the expected complexity here.

When implementing skip lists as described above, there is a small chance to end up with an infinitely promoted element. While the expected number of levels is *O(log(n))*, it is theoretically unbounded. To solve this it is possible to choose a maximum number of levels *M* that an element can get promoted. If *M* is sufficiently large, there are no negative implications in practice.

The expected read and update complexity in the average case is logarithmic. The expected height of a skip list is *O(log(n))*. However, higher promoted elements are less likely, allowing us to derive linear expected memory requirements [8].

Analyzing the worst case is more interesting for the bounded list, as the unbounded worst case is an infinitely high skip list. In the worst case of a bounded list we promoted every element to the maximum level. If we choose the maximum level to depend on *n*, we can derive linear complexity for read and update operations.

Type | Average	| Worst case (*M*-bounded) | Worst case (unbounded)
--- | --- | --- | ---
Read | *O(log n)*	| *O(n)* | *∞*
Update | *O(log n)* |	*O(n)* | *∞*
Memory | *O(n)* | *O(nM)* | *∞*

Now we got to know three different types of data structures which are widely used in the industry. We looked at them from a theoretical point of view one by one. The next section contains a static comparison, summarizing our findings, as well as some run time experiments using implementations from the Java standard library.

# Comparison

## Theoretical Comparison

From what we have learned today it is safe to say that read-efficient data structures aim at sub-linear read overhead. Hash tables are great for in-memory maps or sets. The disadvantages lie in the need to rescale the underlying array if the data grows, as well as the lack of range-query support. Tree based data structures are a good alternative if range queries or sorted output is of concern. Skip lists are sometimes preferred over trees due to their simplicity, especially when it comes to lock-free implementations.

Some of the data structures are configurable in terms of RUM overheads. By tuning parameters like the collision resolution strategy or the desired load factor, we can trade memory overhead against read overhead in hash tables. In skip lists we can achieve this by modifying the promotion probability.

The following table summarizes the average asymptotic read, update, and memory requirements, as well as the RUM  tunability aspect of the three data structures we have seen in this post.

            | Hash Table | Red-Black Tree | Skip List
----------- | ---------- | -------------- | ---------
Avg. Read   | *O(1)*     | *O(log n)*     | *O(log n)*
Avg. Update | *O(1)*     | *O(log n)*     | *O(log n)*
Avg. Memory | *O(n)*     | *O(n)*         | *O(n)*
RUM Tuning Parameters | load factor, hash function, collision resolution strategy | - | promotion probability

## Runtime Experiments

Last but not least, we want to take a look at the actual read performance of three Java standard library data structures: [`HashSet`](https://docs.oracle.com/javase/8/docs/api/java/util/HashSet.html), [`TreeSet`](https://docs.oracle.com/javase/8/docs/api/java/util/TreeSet.html), and [`ConcurrentSkipListSet`](https://docs.oracle.com/javase/8/docs/api/java/util/concurrent/ConcurrentSkipListSet.html).

`HashSet` uses separate chaining for collision resolution. If the number of elements in a bucket is small enough, they will be stored in a list. If the number exceeds the [`TREEIFY_THRESHOLD`](http://hg.openjdk.java.net/jdk8u/jdk8u/jdk/file/a006fa0a9e8f/src/share/classes/java/util/HashMap.java#l257), it will be migrated to a red-black tree. `TreeSet` is implemented using a red-black tree. Both, `HashSet` and `TreeSet` are not thread safe and do not support concurrent modifications. As the name suggests, `ConcurrentSkipListSet` supports concurrent access. The base lists use a variant of the Harris-Maged linked ordered set algorithm [9, 10].

As a benchmark we generate a set from *n* random integers, and copy it into a `HashSet`, `TreeSet`, and `ConcurrentSkipListSet`, respectively. We also create a read-optimal set from those numbers, i.e. using a huge boolean array. We then create a list of *n* random point queries and measure the run time for all queries to complete.

We are using [ScalaMeter](http://scalameter.github.io/) for measuring the runtime performance. Feel free to check out my [microbenchmarking blog post](https://dev.to/frosnerd/microbenchmarking-your-scala-code-4885) which contains more details about the tool.

The following chart shows the run time for 100 000 point queries on the different sets generated from 100 000 random integers.

![read-chart](https://thepracticaldev.s3.amazonaws.com/i/5fk69w087bs8ncsx4s5a.png)
![read-chart-legend](https://thepracticaldev.s3.amazonaws.com/i/nzfe73ah6bb1vxrcz76k.png)

As expected, the read-optimal implementation performs significantly better than all the others. The second place goes to the hash set. Both the read-optimal implementation and the hash set have constant asymptotic read overhead. The tree set and skip list set perform much worse. This is also expected, as they have logarithmic run time complexity.

It would be interesting to also look at the other overheads of the four implementations, as well as including concurrency into the mix. But I am leaving this exercise to the reader :P In the next post we are going to take a closer look at write efficient data structures which are designed to have low update overhead.

# References

- [1] Guibas, L.J. and Sedgewick, R., 1978, October. A dichromatic framework for balanced trees. In Foundations of Computer Science, 1978., 19th Annual Symposium on (pp. 8-21). IEEE.
- [2] [Memory consumption of popular Java data types – part 2](http://java-performance.info/memory-consumption-of-java-data-types-2/) by Mikhail Vorontsov
- [3] [Choose Concurrency-Friendly Data Structures
](http://www.drdobbs.com/parallel/choose-concurrency-friendly-data-structu/208801371?pgno=1) By Herb Sutter
- [4] Pugh, W., 1989, August. Skip lists: A probabilistic alternative to balanced trees. In Workshop on Algorithms and Data Structures (pp. 437-449). Springer, Berlin, Heidelberg.
- [5] Fraser, K. and Harris, T., 2007. Concurrent programming without locks. ACM Transactions on Computer Systems (TOCS), 25(2), p.5.
- [6] Herlihy, M., Lev, Y., Luchangco, V. and Shavit, N., 2006. A provably correct scalable concurrent skip list. In Conference On Principles of Distributed Systems (OPODIS).
- [7] Papadakis, T., 1993. Skip lists and probabilistic analysis of algorithms. Ph. D. Dissertation: University of Waterloo.
- [8] [Skip lists](https://www.cs.bgu.ac.il/~ds162/wiki.files/07-skip-list.pdf) - Data Structures Course of Ben-Gurion University of the Negev
- [9] Harris, T.L., 2001, October. A pragmatic implementation of non-blocking linked-lists. In International Symposium on Distributed Computing (pp. 300-314). Springer, Berlin, Heidelberg.
- [10] Michael, M.M., 2002, August. High performance dynamic lock-free hash tables and list-based sets. In Proceedings of the fourteenth annual ACM symposium on Parallel algorithms and architectures (pp. 73-82). ACM.
- Cover image by Smabs Sputzer - It's a Rum Do... auf flickr, CC BY 2.0, https://commons.wikimedia.org/w/index.php?curid=59888481
