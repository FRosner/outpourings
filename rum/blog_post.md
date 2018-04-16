---
title: RUM Conjecture - Reasoning About Data Access
published: true
description: Looking at read, update and memory overhead of different access methods can help when reasoning about different implementations. The RUM conjecture formulates how the three overheads influence each other.
tags: programming, learning, databases, computerscience
cover_image: https://thepracticaldev.s3.amazonaws.com/i/j1p6jiuchuuvowacwpgr.jpg
---

# Motivation

In one of my previous posts I was talking about [choosing the right data model](https://dev.to/frosnerd/making-the-invalid-impossible---choosing-the-right-data-model-9e6) in order to avoid invalid state and to make code more understandable. In addition to choosing the right data model it is also important to choose the right implementation. You might have to decide whether to use a hash or a tree based implementation for your set. For persisting data inside a database, you also have different options, e.g. [SQLite](https://www.sqlite.org/index.html), [PostgreSQL](https://www.postgresql.org/), or [Cassandra](http://cassandra.apache.org/). How to decide which one to use?

Data systems researchers developed a theoretical model to reason about, and compare different data structures in terms of their overhead when *reading* (R), *updating* (U), and storing the data in *memory* (M). They formulated the results in the so called *RUM conjecture* [1]. In this blog post we are going to look at the RUM overheads and the trade-offs associated with them. We are also taking a look at the conjecture and its implications for us as developers.

The post is structured as follows. The first section formally defines RUM overheads. The next section introduces the RUM conjecture, which explains how the three overheads are connected and influencing each other. We are going to look at some example implementations as well. Afterwards there will be a discussion about the implications of the RUM conjecture for us as developers. We are closing the blog post with an outlook for future posts.

# RUM Overheads

Given *base data* as the main data that is stored in the data management system, and *auxiliary data* as additional data such as indexes to improve access performance, we can define the following access metrics:

- *BR* as the amount of base data read
- *AR* as the amount of auxiliary data read
- *RR* as the amount of data returned by a read query
- *BU* as the amount of base data updated
- *AU* as the amount of auxiliary data updated
- *BM* as the amount of space required to store the base data
- *AM* as the amount of space required to store the auxiliary data

The authors in [1] define the RUM overheads as follows:

- Read Overhead *RO = (BR + AR) / RR*
- Update Overhead *UO = (BU + AU) / BU*
- Memory Overhead *MO = (BS + AS) / BS*

While this definition seems intuitive in my opinion there is one problem with it. When performing an update you might need to perform read operations first (e.g. to find the value to update), depending on the access pattern and data structure you are using. This is not captured by the update overhead described in the paper.

In my opinion it makes sense to include the read overhead in the update overhead calculation if an update requires a read. In a later section we are going to see a simple example and also why it matters. For the rest of this blog post we are thus going to use the following definitions:

- **Read Overhead** *RO = (BR + AR) / RR*
- **Update Overhead** *UO = (BU + AU) / BU + RO*
- **Memory Overhead** *MO = (BM + AM) / BM*

Now let's take a look on how the different overheads relate to each other when it comes to choosing the right access method for your data.

# RUM Conjecture

## Definition

> **The RUM Conjecture.** An access method that can set an upper bound for two out of the read, update, and memory overheads, also sets a lower bound for the third overhead. [1]

In other words choosing the right access method becomes an optimization problem. E.g. if your data structure should support fast reads and consume little space you have to accept higher update overhead. To visualize this effect we are going to take a look at an example which varies a bit from the one in the paper.

## Minimizing RUM Overheads

Consider the following problem: We want to store a set of *N* integers (i.e. no duplicates allowed). To get an intuition of the trade-off between the different overheads we are going to look at three different implementations, each one minimizing one of the three overheads. For simplicity reasons let's assume that the numbers we can store are between 0 and 1000.

The given examples are very simple solutions. You are probably aware of other data structures that would be more suitable (e.g. a hash or tree based implementation). Looking at the following implementations, however, gives a good intuition on how minimizing one overhead affects the others.

### Minimizing RO

To minimize RO we can store the integers in a boolean array `a` of size `1001`. The array elements are initialized with `false`. To mark an integer `i` as member of the set, we set `a[i] := true`. A point query can now look up the membership directly by accessing the array at the corresponding index. Updates are performed the same way and don't require an additional read as we can access the element by index. The space required for this data structure depends on the possible values that can be stored in the set and it theoretically infinite.

When choosing this implementation, we derive the following RUM overheads of the RO-minimizing implementation:

- *RO = 1*
- *UO = 1*
- *MO →	∞*

### Minimizing UO

To minimize UO we store each insert and delete operation in a sequence which supports constant time appends (e.g. a list). Updates correspond to appending the value and the operation (whether it is inserted or deleted) to the update log. A point query requires us to walk through the log starting from the latest update. If we find an insert operation of the value we are looking for it is a member of the set. If we find a delete operation or reach the end of the log the value is not a member. The space required for this data structure grows with every update operation.

We can derive the following RUM overheads for the UO-minimizing implementation:

- *RO →	∞*
- *UO =	1*
- *MO →	∞*

### Minimizing MO

To minimize MO we store all values of the set in a dense array. A point query now requires a full scan of the data. Update operations also require a full scan: An insert needs to check if the value is already there to avoid duplicates and a delete needs to remove the value from the sequence. Also on every delete we have to fill the gap. The space required however is minimal, as only the integers are stored and no auxiliary data is required.

This gives us the following RUM overheads for the MO-minimizing implementation:

- *RO ≤ N*
- *UO ≤ N + 2*
- *MO = N*

# Implications

When choosing a physical representation of your data (or choosing a database which uses a specific representation), there will always be a trade-off between read, update, and memory overhead. Taking the memory hierarchy (see my [previous blog post](https://dev.to/frosnerd/hit-me-baby-one-more-time---what-are-cache-hits-and-why-should-you-care-4500)) into account the overheads have different impact, depending on whether the data is accessed within the CPU cache, the main memory, or a persistent storage for example.

Having this in mind it makes sense to first understand what the data you are going to store looks like and which are the typical access patterns going to be. Will there be many writes? What is the required response time of a read? How much space do you have available?

# Outlook

Going forward I want to shed more light on some common data structures focusing on low read (e.g. B-Trees [2] and Skip Lists [3]), write (e.g. Log-structured Merge Trees [4]), and space (e.g. Bloom Filters [5] and ZoneMaps [6]) overhead. There is also research about data structures that can adapt based on the access patterns (e.g. database cracking [7] and adaptive indexing [8]). So stay tuned for the upcoming posts.

Did you ever take the RUM overheads into account when selecting a data structure or data base? Are you aware of the internals of the databases that you are using every day? Do you agree with my change to the update overhead, incorporating also the read overhead? Let me know your thoughts in the comments.

# References

- [1] Athanassoulis, M., Kester, M.S., Maas, L.M., Stoica, R., Idreos, S., Ailamaki, A. and Callaghan, M., 2016. Designing Access Methods: The RUM Conjecture. In EDBT (Vol. 2016, pp. 461-466). [PDF](https://stratos.seas.harvard.edu/files/stratos/files/rum.pdf)
- [2] G. Graefe. Modern B-Tree Techniques. Found. Trends Databases, 3(4):203–402, 2011.
- [3] W. Pugh. Skip lists: a probabilistic alternative to balanced trees. CACM, 33(6):668–676, 1990.
- [4] P. E. O’Neil, E. Cheng, D. Gawlick, and E. J. O’Neil. The log-structured merge-tree (LSM-tree). Acta Informatica, 33(4):351–385, 1996.
- [5] B. H. Bloom. Space/Time Trade-offs in Hash Coding with Allowable Errors. CACM, 13(7):422–426, 1970.
- [6] P. Francisco. The Netezza Data Appliance Architecture: A Platform for High Performance Data Warehousing and Analytics. IBM Redbooks, 2011.
- [7] S. Idreos, M. L. Kersten, and S. Manegold. Database Cracking. In CIDR, 2007.
- [8] G. Graefe, F. Halim, S. Idreos, H. Kuno, and S. Manegold. Concurrency control for adaptive indexing. PVLDB, 5(7):656–667, 2012.
- Cover Image by O'Dea at WikiCommons, CC BY-SA 3.0, https://commons.wikimedia.org/w/index.php?curid=12469449
