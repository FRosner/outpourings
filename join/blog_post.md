---
title: Choosing The Right Join Strategy
published: false
description: ???
tags: ???
cover_image: ???
---

# Motivation

- Joining in traditional relational databases is a complex topic.
- When performing a join in a DB, the query optimizers utilizes existing table constraints, statistics of the data (size, value distribution, etc.), available indexes, and so on.
- Joining two tables locally is hard, joining two tables which are distributed across a cluster of nodes is even harder
- Frameworks like Apache Spark are powerful tools for working with distributed data
- Spark supports distributed joins

# Naive Join Implementation



# Spark

- Catalyst Optimizer uses cost based optimization to select join algorithm
  => Problem: Often times there are no constraints, indexes or global information available for a distributed dataframe => Optimization only relies on heuristics and is rather basic
- Two join algorithms available:
  - Hash Join
  - Sort-Merge Join => "Shuffle Hash Join"
