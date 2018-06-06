---
title: Memory Efficient Data Structures
published: true
description: In this post we want to take a closer look at two data structures designed for low space overhead - Bloom filters and bitmap indexes.
tags: learning, databases, computerscience, programming
cover_image: https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Rhums_de_Guadeloupe.JPG/640px-Rhums_de_Guadeloupe.JPG
---

# Introduction

The [first blog post of the RUM series](https://dev.to/frosnerd/rum-conjecture---reasoning-about-data-access-4781) introduced the RUM conjecture. It describes the trade-off between read (RO), update (UO), and memory (MO) overheads that one should take into account when designing data structures and access methods.

In this post we want to take a closer look at two data structures designed for low space overhead: Bloom filters and bitmap indexes.

This blog post is the fourth part of the RUM series:

1. [RUM Conjecture - Reasoning About Data Access](https://dev.to/frosnerd/rum-conjecture---reasoning-about-data-access-4781)
2. [Read Efficient Data Structures](https://dev.to/frosnerd/read-efficient-data-structures-57i5)
3. [Update Efficient Data Structures](https://dev.to/frosnerd/update-efficient-data-structures-7cn)
4. [Memory Efficient Data Structures](#)

The blog is structured as follows. First, we will recap the memory-optimal solution from the initial blog post and motivate how we can achieve even better memory overhead when sacrificing the correctness of the results. The next section introduces Bloom filters, an approximate data structure aiming at low and tunable memory overhead. After that we are discussing bitmap indexes which represent a way to encode data in a memory efficient way and support fast multi-dimensional queries. Next, we will summarize the main ideas of this post. We are closing the RUM series in the last section.

# Memory-Optimal Solution

The simplest way to achieve constant memory overhead is to store no auxiliary data. In our integer set example the memory-optimal implementation stores all integers in an array of exactly the size required, resizing the array as required. We derived the following RUM overheads:

- *RO ≤ N*
- *UO ≤ N + 2*
- *MO = 1*

In this implementation we can trade read overhead against update overhead when sorting the integers. This allows binary search but requires to maintain the order on insertion. Another way would be to use compression, which reduces the memory requirements. However it can be applied to any data structure and going into details is beyond the scope of this post.

In practice however we usually do not have too strict memory requirements as storage became increasingly cheap over the last decades. Using a hash table or other read-efficient data structures have reasonable memory overhead for most use cases. This is why in the next section we are going to look at a data structures that achieves a memory overhead less than 1.

# Bloom Filters

## Concept

A Bloom filter [1] is a space-efficient approximate data structure. It can be used if not even a well-loaded hash table fits in memory and we need constant read access. Due to its approximate nature, however, one must be aware that false positives are possible, i.e. a membership request might return true although the element was never inserted into the set.

The idea behind a Bloom filter is similar to a hash table. The first difference is that instead of reserving space for an array of integers, we allocate an array of *m* bits. Secondly, we utilize not one but *k* independent hash functions. Each hash function takes a (potential) element of the set and produces a position in the bit array.

![bloom filter illustration](https://thepracticaldev.s3.amazonaws.com/i/tgp11bpflakmwhzlwtdd.png)

Initially all bits are set to 0. In order to insert a new value into the set, we compute its hash value using each of the *k* hash functions. We then set all bits at the corresponding positions to 1.

A membership query also computes all hash values and checks the bits at every position. If all bits are set to 1, we return true with a certain probability of being correct. If we see at least one 0, we can be sure that the element is not a member of the set.

The probability of false positives depends on the number of hash functions *k*, the size of the bit array *m*, and the number of elements *n* already inserted into the Bloom filter. Assuming that all bits are set independently, the false positive rate *FP* can be approximated by

![false positive rate formula](https://thepracticaldev.s3.amazonaws.com/i/ea5iz4sisnkfy0fbh0s1.png)

For a Bloom filter with 1 million bits, 5 hash functions, and 100k elements already inserted, we get *FP ≈ 1%*. If you want to play around with the variables yourself, check out this awesome [Bloom filter calculator](https://hur.st/bloomfilter) by Thomas Hurst.

A big disadvantage besides the fact that there can be false positives is that deletions are not supported. We cannot simply set all positions of the element to be deleted to 0, as we do not know if there have been hash collisions while inserting other elements. Well, we cannot even be sure if the element we are trying to delete is inside the Bloom filter because it might be a false positive.

So what are Bloom filters used for in practice? One use case is in web crawling. In order to avoid duplicate work a crawler needs to determine whether he already visited a site before following a link. Bloom filters are perfect as storing all visited websites in memory is not really possible. Also if we get a false positive it means that we are not visiting a website although it has not been visited before. If the output of the crawler is used as an input to a search engine we do not really mind as highly ranked websites will most likely not have only one incoming link and thus we have a chance of seeing it again.

Another use case is in databases. Bloom filters are used in combination with LSM trees which we know already from the [previous blog post](https://dev.to/frosnerd/update-efficient-data-structures-7cn). When performing a read operation we potentially have to inspect every level of the log. We can use a Bloom filter to efficiently check if the key we are looking for is present in each of the blocks. If the Bloom filter tells us that the key is not present we can be sure and do not have to touch that block, which is very useful for higher levels which are commonly stored on disk.

## RUM Overheads

The RUM overheads of Bloom filters are similar to the ones of hash tables. Both read and update overhead correspond to the one in hash tables without collision resolution. The overhead for computing the hash function however is *k* times higher as we are using *k* hash functions.

The memory overhead depends on the element size, i.e. the larger the elements stored the greater the effect, as well as the load factor of the filter. For 100k 32 bit integer values stored in a 1 MB Bloom filter we get a memory overhead of around 0.33.

# Bitmap Indexes

## Concept

A bitmap index [2] is a data structure commonly used in database indexing. Similar to Bloom filters, bitmap indexes are based on bit arrays, also known as bitmaps.

Conceptually a bitmap index is a set of bit arrays which encode values of a database column in a logical bit vector. For each possible value we store a bit array of the column size. Let's look at an example for a boolean column. The first column in the table denotes the original value. The second and third columns are the bit arrays for each possible value. If the value is unset, we simply leave all bits as 0.

| Boolean | True | False |
|---------|------|-------|
| `True`    | `1`    | `0`     |
| `False`   | `0`    | `1`     |
| `Null`    | `0`    | `0`     |

This means that we represent `True` as `[1, 0]`, `False` as `[0, 1]`, and `Null` as `[0, 0]`. We can generalize this procedure for higher cardinality columns as well.

What do we gain from that? The main motivation behind bitmap indexes is the possibility to answer multi-dimensional queries efficiently by using bitwise logical operations. If we want to know all customers who live in Germany and have a premium contract, we simply combine the `Germany` and `premium` bit array using pairwise `and`. Also bitmap indexes can have significantly less space overhead than a B tree index or comparable data structures.

One disadvantage is that the low memory overhead effect only works if the cardinality is reasonably low. Additionally, updates in the original column require to update all bitmaps. Thus, the performance is best when applied on read-only data, e.g. in data warehouse applications.

## RUM Overheads

Using a bitmap index to implement a set of integers is not a good idea. If cardinality is too high, you need to perform binning before. So for the sake of argumentation let's consider a set of strings for now.

As the bitmaps are just a different way to encode the original data, the read overhead is proportional to the number of elements within the column. If we are looking for a specific value, let's say `Frank`, we have to scan the whole `Frank` bit array for the 1. The update overhead is similarly high with the addition that inserting elements requires resizing of the bit arrays.

As far as the memory overhead is concerned, we represent *n* values with cardinality *c* as an *n×c* bit matrix. The memory overhead depends not only on the cardinality but also the size of the original values.

Let's say we want to represent a set of states of the United States of America. If we stored them as an array of 256 ASCII character long strings this would mean each state now takes up 50 bits instead of 256 bytes. The additional memory overhead of such representation would be *50 / (256 ⋅ 8) ≈ 0.02* with the effect of efficient multi-dimensional queries. The calculation is a bit shaky as one could argue that for calculation of memory consumed for the base data you should take the most efficient encoding into account. Nevertheless I hope you get the idea.

# Summary

In this blog post we have seen Bloom filters as a way to improve beyond the optimal memory overhead by sacrificing a bit of correctness. Bitmap indexes were a good example of how we can get some of the benefits indexes provide without adding too much additional memory overhead.

Have you used Bloom filters or other approximate data structures / extensions to Bloom filters in a project? How did you determine the number of hash functions and size of the filter? Were you monitoring the false positive rate during run time?

# Closing Words

In the RUM series I wanted to shed light on the different trade-offs you face when designing or reasoning about data structures and access patterns. Taking read, update, and memory overheads into account when comparing different implementations can help to understand the differences better or even pick the right one for your job. I also wanted to give an overview about different data structures that exist, especially in the context of the RUM conjecture.

I learned a lot while working on the posts. I was not familiar with the internals of some of the data structures in greater detail. Reading the papers was fun and I also enjoyed the discussions I had in person and in the comments so far, and am looking forward to the ones in the future. Thank you all for your feedback and stay tuned for upcoming blog posts.

# References

- [1] Bloom, B.H., 1970. Space/time trade-offs in hash coding with allowable errors. Communications of the ACM, 13(7), pp.422-426.
- [2] Spiegler, Israel, and Rafi Maayan. "Storage and retrieval considerations of binary data bases." Information processing & management 21.3 (1985): 233-254.
- Cover image: Par LPLT — Travail personnel, CC BY-SA 3.0, https://commons.wikimedia.org/w/index.php?curid=26568662
