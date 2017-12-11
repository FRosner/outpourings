---
title: Monitoring Data Quality in Data Science Applications
published: false
description: Working with data is not easy. In this blog post we are going to take a closer look at challenges related to data quality. How does data quality impact your results? How can you measure it? The answer is a Spark package called Drunken Data Quality.
tags: showdev, data science, scala, python
---

http://slides.com/frosner/monitoring-of-data-quality-in-data-science-applications

## Working with Data

Working with data is not easy. Often times you do not have the data available that you need. But even if you do, new challenges await you. These challenges might differ from project phase to project phase, from data source to data source, and depending on your technology stack.

In this blog post we are going to take a closer look at challenges related to *data quality*. How does data quality impact your results? How can you measure it? How can you improve it? Some of these questions will be answered by a Spark package I wrote some time ago: Drunken Data Quality (DDQ). It provides helper functions for measuring and monitoring data quality in the different phases of your project lifecycle.

Do not worry if you are not familiar with [Apache Spark](https://spark.apache.org). Even if you do not want to or cannot use Spark at the moment or in the future, the concepts presented in the next sections are valid for any data driven software solution. The code is written in Scala but should be understandable for anyone with a bit of programming experience.

### The Tasks

- Prototype Phase
 - One-off data delivery (sample or full)
 - Data exploration
 - Modeling
- Product Phase
 - Continous data delivery (batch / streaming)
 - Versioning, releases and continuous integration

### The Challenges

- File formats (text vs. binary, structured vs. unstructured)
- Encodings (charset, date formats, ...)
- Missing values (null, "NA", "-", "--", "", " ", ...)
- Constraint violations (negative age, illegal customer id, ...)

### The Code

```sh
awk -F "\"*,\"*" '{print $3 $1}' contracts.csv
```

```sh
sed 's/\(\([^,]\+,\)\{1\}\)[^,]\+,\(.*\)/\1\3/' flights.csv
```

```sql
SELECT TRIM(name), age
FROM customers
WHERE age > 0 AND age < 150
```

```scala
val distinctBefore = base.distinct.count
val join = base.join(ref, joinColumns)
val matchingRows = join.distinct.count
val matchPercentage = matchingRows.toDouble / distinctBefore
```

## Data Quality

*Aspects of Data*

- Correctness
- Completeness
- Accuracy
- Reliability
- Consistency
- Accessibility
- Relevance
- Immutability
- ...

*Effects on Results*

- Correctness
- Completeness
- Accuracy
- Reliability
- Consistency
- Accessibility
- Relevance
- Reproducibility
- ...

Garbage In, Garbage Out (GIGO)

### Example: Cancellation of Contracts

- Mobile phone contract database (snapshot deliveries)
 - ContractID, CustomerID, StartDate, EndDate, Cancellation, DataVolume, MonthlyPrice
- Predict contract duration for a given contract and time
 - Filter on cancelled contracts (cancellation == true)
 - Use contract duration as target variable (end - start)
 - Engineer feature variables
 - Train regression model to predict duration

- What can go wrong?
 - There is no start date
 - There is no end date
 - Start date > end date

### Tools

Many different tools available (word cloud)


## Drunken Data Quality

"Drunken Data Quality (DDQ) is a small library for checking constraints on Spark data structures. It can be used to assure data quality, especially when continuous imports happen." - https://github.com/FRosner/drunken-data-quality

```sh
spark-shell --packages \
FRosner:drunken-data-quality:x.y.z-s_2.10
```

```scala
Check(customers).hasUniqueKey("id").run(
  MarkdownReporter(System.out)
)
```

```md
**Checking [id: int, name: string]**

It has a total number of 2 columns and 3 rows.

- *SUCCESS*: Column id is a key.
```

- Features (TODO: Get from Wiki)

## Summary

- How to avoid data quality (gotta get the last slide I guess)
