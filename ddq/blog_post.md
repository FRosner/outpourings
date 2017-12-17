---
title: Monitoring Data Quality in Data Science Applications
published: false
description: Working with data is not easy. In this blog post we are going to take a closer look at challenges related to data quality. How does data quality impact your results? How can you measure it? The answer is a Spark package called Drunken Data Quality.
tags: showdev, data science, scala, spark
cover_image: https://thepracticaldev.s3.amazonaws.com/i/rukwmn5pkytd2wqz8eiz.jpg
---

## Introduction

Working with data is not easy. Often times you do not have the data available that you need. But even if, new challenges are already waiting. These challenges might differ from project phase to project phase, from data source to data source, and depending on your technology stack.

In this blog post we are going to take a closer look at challenges related to *data quality*. How does data quality impact your results? How can you measure it? How can you improve it? Some of these questions will be answered by a Spark package I published some time ago: [Drunken Data Quality](https://github.com/FRosner/drunken-data-quality). It provides helper functions for measuring and monitoring data quality throughout the different phases of your project lifecycle.

Do not worry if you are not familiar with [Apache Spark](https://spark.apache.org). The concepts presented in the next sections are valid for any data driven software solution. The code is written in Scala but should be understandable by anyone with a bit of programming experience.

## Working with Data

### The Tasks

Before working on a new data driven application or solution, you typically want to assess the feasibility of your approach. There will be an initial prototype or study, where you receive a one-shot delivery of the data sets (or samples) that are important for your application.

Then you are most likely going to explore the data, understanding what is inside, and what are its characteristics. This can be achieved using techniques from descriptive statistics, data visualization, unsupervised learning methods, and so on.

If the first study was successful, it makes sense to setup more sophisticated workflows and processes. Data will be delivered continuously, either via batches or in a streaming fashion. As the code which is developed will probably survive more than a few weeks, you start revising topics like continuous integration, delivery, and deployment.

### The Challenges

In every phase, with any task related to data, you might face different challenges.

When reading data, there are different file formats and structures. Maybe you get CSV files through an ETL process from one data source, log files from another source, row-wise structured [Avro](https://avro.apache.org/) files, or column-wise structured [Parquet](https://parquet.apache.org/). If the department responsible for the data source thought about analytics, you might be able to query a read-only replica of the production database directly.

If the data is unstructured or semi-structured, it can be useful to parse it. You need to think about character encodings, delimiters, date formats, and so on. Are there any missing values? How are they encoded (`null`, `"NA"`, `"-"`, `"--"`, `""`, `" "`)?  How do you want to deal with them?

After you managed to get the data into the right format and structure for your analysis, you have to think about semantic constraints. Which customer IDs are valid? Can an age of a person be negative? Are duplicates allowed? How are duplicates defined? Are there connections between two tables and how are they modeled (e.g. foreign keys)?

### The Code

The more data sources you have and the richer they are, the more complex and manifold the challenges will be. In order to deal with the complexity, we write code, use libraries and tools. Typical queries for data parsing, extraction, and validation are:

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

The first two examples manipulate the data, while the other two are trying to check certain constraints or assumptions. We run those transformations and checks in the shell, or in a notebook like [Jupyter](http://jupyter.org/) or [Zeppelin](https://zeppelin.apache.org/), or maybe in a scheduled workflow.

## Data Quality

### Definition

Data quality is defined as different aspects of the data which have an effect on your results.

#### Aspects of Data

- Correctness (Is the customer age correct?)
- Completeness (Do I have all my customers in the data base?)
- Accuracy (What tolerance does my temperature sensor have?)
- Reliability (Will the promised constraints hold for all data points?)
- Consistency (Is the same unit used for measuring distance in different tables?)
- Accessibility (Is the data available for me to access?)
- Relevance (Does the table contain the information required to answer my question?)
- Immutability (Will the data be the same, next time I rerun my analysis?)
- ...

#### Effects on Results

- Correctness (Is the computed age segment correct?)
- Completeness (Am I calling all customers who need to be called?)
- Accuracy (Is my input to the heating accurate?)
- Reliability (Will my results have the promised quality all the time?)
- Consistency (Is my predicted time to arrival the same unit for different means of transportation?)
- Accessibility (Can the customer access the results?)
- Relevance (Does my prediction help to solve my business problem?)
- Reproducibility (Will the results be the same, next time I rerun my analysis?)
- ...

Or to summarize: Garbage In, Garbage Out (GIGO)

### Example: Cancellation of Contracts

Let's look at a practical example. Imagine you are a mobile phone service provider. You store your contract data in a database, from which you extracted the following snapshot table storing contract information:

Field | Type
----- | ----
`ContractID` | `String`
`CustomerID` | `String`
`StartDate` | `Date`
`EndDate` | `Date`
`DataVolumeMB` | `Int`
`MonthlyPriceCent` | `Int`

Now you would like to predict the contract duration for new customers who did not cancel, yet. In order to get a training data set, you might perform the following steps:

1. Filter out the existing contracts that have not ended, yet
2. Engineer target variable `ContractDuration` = `EndDate` - `StartDate`
3. Engineer feature variables, maybe joining with the customer table
4. Train regression model to predict duration

What can go wrong? Well, there are a couple of things. For now let's only look at the step of engineering the target variable `ContractDuration` = `EndDate` - `StartDate`.

- What happens if `StartDate` is not defined?
- What happens if `StartDate` > `EndDate`?

![negative contract duration](https://thepracticaldev.s3.amazonaws.com/i/s8dimjv60avsxw8hoslg.png)

If you do not think about these issues before, your model might get thrown off by negative contract durations just because of poor data quality. You should write those assumptions down, putting them in code, and checking them every time you receive new data. Then you should think about a strategy to mitigate quality issues. Mostly it is good enough to discard bad data points, but you might also want to correct them.

The question is, how can you express your definition of data quality for this particular data set (e.g. the end date should always be bigger than the start date)? Can we write down our assumptions on the data in a way that they are documented but also checked automatically? Can we do it in a way that will work during the initial study phase where quick results matter but also later when running in productive, scheduled workflows, connecting the quality checks with our monitoring and alerting systems?

The answer is *yes*!

## Drunken Data Quality

*[Drunken Data Quality](https://github.com/FRosner/drunken-data-quality) (DDQ) is a small library for checking constraints on Spark data structures. It can be used to assure a certain level of data quality, especially when continuous imports happen.*

### Usage Example

We are starting our Spark shell, specifying that we want to use the DDQ package.

```sh
spark-shell --packages FRosner:drunken-data-quality:4.1.1-s_2.11
```

Now let's define two dummy tables.

```scala
case class Customer(id: Int, name: String)
case class Contract(id: Int, customerId: Int, duration: Int)

val customers = spark.createDataFrame(List(
  Customer(0, "Frank"),
  Customer(1, "Alex"),
  Customer(2, "Alex")
))

val contracts = spark.createDataFrame(List(
  Contract(0, 0, 5),
  Contract(1, 0, 10),
  Contract(0, 1, 6)
))
```

Finally we are going to run a few constraints on those.

```scala
import de.frosner.ddq.core._

Check(customers)
  .hasNumRows(_ >= 3)
  .hasUniqueKey("id")
  .run()

Check(contracts)
  .hasNumRows(_ > 0)
  .hasUniqueKey("id", "customerId")
  .satisfies("duration > 0")
  .hasForeignKey(customers, "customerId" -> "id")
  .run()
```

The results will be shown on the console.

> **Checking [id: int, name: string]**
>
> It has a total number of 2 columns and 3 rows.
>
> - *SUCCESS*: The number of rows satisfies (count >= 3).
> - *SUCCESS*: Column id is a key.
>
> **Checking [id: int, customerId: int ... 1 more field]**
>
> It has a total number of 3 columns and 3 rows.
>
> - *SUCCESS*: The number of rows satisfies (count > 0).
> - *SUCCESS*: Columns id, customerId are a key.
> - *SUCCESS*: Constraint duration > 0 is satisfied.
> - *SUCCESS*: Column customerId->id defines a foreign key pointing to the reference table [id: int, name: string].

### Features

DDQ consists of constraints, a runner, and reporters. First, you define one or multiple constraints on your data. Then you pick reporters that will process the constraint results. Finally, you pass both to the runner, which will run the constraints on the data. Please see the [official documentation](https://github.com/FRosner/drunken-data-quality/wiki/Drunken-Data-Quality-4.1.1) for more details.

The following types of constraints are supported at the moment:

- Column constraints (e.g. null, date formats, regex)
- Table constraints (e.g. number of rows, unique key)
- Relationship constraints (e.g. foreign key, joinability)
- User defined constraints

You can report your constraint results to the following reporters:

- Console (e.g. from spark-shell)
- Markdown (e.g. for storing the report in a file)
- Zeppelin (from within the [Apache Zeppelin](https://zeppelin.apache.org) notebook)
- Log4j (e.g. when using Kibana for quality monitoring)
- Email (e.g. for direct alerting)

In addition, the constraint results will be returned from the runner so they can be accessed programatically.

There is also a Python API available ([pyddq](https://pypi.python.org/pypi/pyddq/4.1.1)), if you prefer to use PySpark. However the Scala API is slightly more powerful and customizable.

## Improving Data Quality

*"If we don’t know what the data is supposed to look like, we won’t know whether it is right or wrong."* - [When Bad Data Happens to Good Companies](https://www.sas.com/content/dam/SAS/en_us/doc/whitepaper1/bad-data-good-companies-106465.pdf)

Defining and measuring data quality is a key step in a successful data driven application. The next logical step after measuring data quality is working on avoiding it. But how can you improve data quality?

1. Understand the business context. Talk to the data owners and ask smart questions. Make your assumptions explicit and challenge them regularly.
2. Identify data quality issues (preferably with DDQ :P) before using the data for anything else.
3. Communicate the issues. Try to address the root cause by reducing complexity, getting rid of unnecessary steps in your data flow. Avoid [ETL](http://noetl.org/) if possible, making the data owners more sensible for analytics so that they can avoid data silos.

## Conclusion

We have seen that working with data is not as easy as one might think. There are different challenges throughout the different phases of development. DDQ provides an easy to use, flexible and fluent API to define and check data quality constraints. However, in order to solve the issues in a long term way, all different stakeholders need to work together.

What were your experiences with bad data quality? Did you ever make a decision that had negative business impact based on low quality data? Did you talk to people who believe that big data technology can make you escape the GIGO principle? Please comment and let me know what you think!
