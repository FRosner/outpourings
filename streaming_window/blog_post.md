---
title: Window Functions in Stream Analytics
published: true
description: In this blog post we want to take a closer look at different window functions that can be used to perform aggregations on data streams.
tags: bigdata, cloud, streams, analytics
cover_image: https://thepracticaldev.s3.amazonaws.com/i/pggwvkisklg1kces0x2y.png
---

# Introduction to Stream Analytics

In the past decades data analytics was dominated by batch processing. Records from transactional databases were copied into analytical databases by regular extract-transform-load (ETL) jobs when business was not running. Reports were generated nightly by aggregating huge batches of data.

Those analytical databases are pretty fast in computing the batch queries but the speed comes at a price: Flexibility and latency. The database schema is designed to give maximum performance for the queries needed by the report. If a new report is requested by the business it can take several weeks or even months to modify the whole process. As data comes in only at night, reports will only get updated the next day.

Nowadays many businesses do not work from 9 to 5 anymore. Customers expect services to be available 24/7 from anywhere in the world. Analysts need to have up-to-date information and with the rise of machine learning automated near real-time actions have become state of the art. This is why many companies are switching their architecture from ETL based batch processing towards stream processing.

In a data stream driven architecture services emit individual records, so called *events*. Whoever is interested in events of a particular service can simply subscribe to them and will receive them as soon as they are available. Because every service can have access to the raw events it does not have to wait for ETL processes to finish. The following figure illustrates individual events happening over time.

![events in time](https://thepracticaldev.s3.amazonaws.com/i/hfq0sbm3tz5t844blzml.png)

But how do we perform analytics on streams? How can we generate the reports based on moving data rather than fixed batches? Streams are by definition unbounded so if we are looking for an aggregated view, e.g. the amount of clicks on our website coming from a particular country, we need to introduce some boundary. In the batch world this boundary was heavily influenced by the ETL schedule. In stream analytics we are free to discretize the stream any way we want in order to perform aggregations on top.

Discretizing the stream into groups of events is called *windowing*. Windowing can technically be done based on any attribute of your events as long as it has an order. Nevertheless it is most commonly done based on time. There are some subtleties to take into account, however.

One question is which timestamp are you using to assign an event to a window? The time when the event was generated or the time when the event arrived at the processor? If you are using the creation time, you need to be aware that event producers might not have properly synchronized clocks. There are techniques to deal with those kinds of issues but they are beyond the scope of this post. Instead, in this blog post we want to take a closer look at different window functions that can be used to perform aggregations on data streams.

The remainder of the post is structured as follows. First we will introduce the four common types of window functions: Tumbling window, hopping window, sliding window, and session window. Afterwards we will take a look into the different tools and products available on the market and what functionality they provide in terms of window functions. We are closing the post by summarizing and discussing the main findings.

# Window Functions

## Definition

A window function assigns events in your stream to windows. To be precise it is more a window relation rather than a function because it theoretically does not have to assign all events to windows, i.e. it is not total, and it can assign an event to multiple windows. In addition it is neither surjective (not all windows have to contain events) nor injective (a window can contain multiple events). Nevertheless we are going to stick to the mathematically incorrect term window function.

Given a window function and a stream of data we can compute aggregates on events inside each window. As mentioned earlier an event might be assigned to multiple windows or a window might have no events assigned at all, depending on the selected window function. This is important to keep in mind when working with the derived stream of aggregates as. For example a graph of event counts based on overlapping windows will look very different from a graph based on counts computed from distinct windows.

Martin Kleppmann mentions four commonly used window functions [1]: *Tumbling window*, *hopping window*, *sliding window* and *session window*. The next sections are going to explain each of them in detail.

## Tumbling Window

A tumbling window has a fixed length. The next window is placed right after the end of the previous one on the time axis. Tumbling windows do not overlap and span the whole time domain, i.e. each event is assigned to exactly one window. You can implement tumbling windows by rounding down the event time to the nearest window start. The following animation illustrates a tumbling window of length 1.

![tumbling window animation](https://thepracticaldev.s3.amazonaws.com/i/c1n1b45h73yahej0cx5k.gif)

Because tumbling windows are only configured through a single property, the window length *s*, and they include every event exactly once, they are often used for simple reporting. You can use tumbling windows to sum all incoming requests towards your server within a 1 minute window and then display a graph where each minute corresponds to one data point.

The Azure Stream Analytics query below represents an example of counting the number of clicks on your website based the country of the visitor, grouped in a 10 second tumbling window. We are using the creation timestamp to calculate the window assignment.

```sql
SELECT Country, Count(*) AS Count
FROM ClickStream TIMESTAMP BY CreatedAt
GROUP BY Country, TumblingWindow(second, 10)
```

## Hopping Window

Like tumbling windows, hopping windows also have a fixed length. However they introduce a second configuration parameter: The hop size *h*. Instead of moving the window of length *s* forward in time by *s* we move it by *h*.

This means that tumbling windows are a special case of hopping windows where *s = h*. If *s > h* windows are overlapping and if *s < h* some events might not be assigned to any window. The following animation illustrates a hopping window of length 1 with hop size 0.25. It is common to choose *h* to be a fraction of *s*.

![hopping window animation](https://thepracticaldev.s3.amazonaws.com/i/13sikpcme4mhsliibhe6.gif)

Hopping windows where *h* is a fraction of *s* can be implemented by computing tumbling windows of size *h* and aggregating them into a bigger hopping window. A common use case for hopping windows are moving average computations.

The Azure Stream Analytics query below represents an example of a moving average on the number of clicks on your website based the country of the visitor grouped in a 10 second window hopping 2 seconds. Again we are using the creation timestamp to calculate the window assignment.

```sql
SELECT Country, Avg(*) AS Average
FROM ClickStream TIMESTAMP BY CreatedAt
GROUP BY Country, HoppingWindow(second, 10, 2)
```

## Sliding Window

Sliding windows can be viewed as hopping windows with *h → 0*. While they are discretizing the input stream the derived aggregated stream is not discrete. A sliding window moves along the time axis, grouping together events that happen within the window length *s*.

However as our data points are discrete we can implement a sliding window by moving forward based on actual events rather than continuously in time. A new window is created whenever an event enters or exits the length of the sliding window moving foward. This mathematically corresponds to a deduplication of all possible windows based on the set of events that have been assigned to them. The following figure illustrates a sliding window of length 1.

![sliding window animation](https://thepracticaldev.s3.amazonaws.com/i/i6gei09zof2p0vkmruje.gif)

Sliding windows are, for example, used to compute moving averages. What makes them unique is that they provide a resolution based the event time pattern in your stream rather than a fixed one. If events are more dense you will get a higher resolution of your moving aggregate. If no events are coming in, the aggregate stream stays the same without emitting new values.

Note that sliding windows are not always implemented the same way. In some tools the aggregation computation is only triggered when a new event *enters* the window but not if an old event *exits*. Make sure to check the documentation or source code of the tool you are using.

The Azure Stream Analytics query below represents an example of a moving average on the number of clicks on your website based the country of the visitor grouped in a 10 second sliding window. Again we are using the creation timestamp to calculate the window assignment.

```sql
SELECT Country, Avg(*) AS Average
FROM ClickStream TIMESTAMP BY CreatedAt
GROUP BY Country, SlidingWindow(second, 10)
```

## Session Window

In contrast to the previous window functions session windows have a variable length. When using a session window function you need to specify a time threshold between consecutive events that must not be exceeded. The window will keep expanding as long as new events are coming in that are close enough in time. The animation below illustrates a session window with a threshold of 0.5.

![session window animation](https://thepracticaldev.s3.amazonaws.com/i/2s7fvhumgbarpmtj5i2g.gif)

You can implement a session window by keeping the current events in a buffer and adding new events as long as they are within the specified session interval. As streams are unbounded sessions can theoretically grow indefinitely. Thus some implementations take a second parameter which represents the maximum session time or the maximum amount of events per session.

Session windows are useful to group together events that are expected to be related when they happen in close succession. The name suggests the prominent use case for this window function: Grouping clicks inside user sessions on your website. As long as the user keeps clicking within a short period of time your window function will aggregate all clicks in one session.

The Azure Stream Analytics query below represents an example of a click count on your website based the country of the visitor grouped in a 5 second interval session window lasting at most 10 seconds. Again we are using the creation timestamp to calculate the window assignment.

```sql
SELECT Country, Count(*) AS Count
FROM ClickStream TIMESTAMP BY CreatedAt
GROUP BY Country, SessionWindow(second, 5, 10)
```

# Window Functions in Practice

In the previous section we looked at the theory behind tumbling, hopping, sliding, and session windows. Now we want to get some insight in which window functions are available in the different tools and products on the market. The table below compares the availability of different window functions inside the following tools and products:

- [Apache Flink](https://flink.apache.org/)
- [Kafka Streams](https://kafka.apache.org/documentation/streams/)
- [Azure Stream Analytics](https://azure.microsoft.com/en-us/services/stream-analytics/)
- [Google Cloud Dataflow](https://cloud.google.com/dataflow/)
- [Amazon Kinesis Data Analytics](https://aws.amazon.com/kinesis/data-analytics/)

Flink and Kafka Streams are open source frameworks. Azure Stream Analytics, Google Cloud Dataflow, and Amazon Kinesis Data Analytics are proprietary, managed solutions by public cloud providers. Only preconfigured window functions taken into consideration. Some tools, e.g. Flink, allow definition of custom window functions which gives a great deal of flexibility.

![available window functions in different tools and products](https://thepracticaldev.s3.amazonaws.com/i/gm6h9abrro0spcfxdu63.png)

Tumbling windows are supported by all tools although in Google Cloud Dataflow they are called fixed time windows. Hopping windows are supported by all tools except Amazon Kinesis Data Analytics. However both Flink as well as Dataflow are calling them sliding windows which is inconsistent with the terminology introduced in the previous section.

Sliding windows are supported by Azure Stream Analytics as well as Amazon Kinesis Data Analytics only. Kafka streams uses sliding windows for stream joins but you cannot aggregate on them directly. Session windows are available in all tools except Amazon Kinesis Data Analytics.

Amazon provides an alternative to tumbling windows called stagger windows which are non-overlapping fixed-length windows aligned with event timestamps. According to the documentation stagger windows are the recommended way to aggregate data using time-based windows, because they reduce late or out-of-order data compared to tumbling windows.

Both Flink and Google Cloud Dataflow offer global windows. Global windows are a trick to aggregate over all data within the stream that is available up to the point the window is triggered. Because computation of global aggregates are expensive they can only be triggered manually. Google Cloud Dataflow also provides other custom window functions such as interval windows and calendar windows.

When writing the comparison between the different tools and products I spent a lot of time reading documentation and I might have missed something. If you find a mistake or have a remark regarding the table above please leave a comment!

# Conclusion

In this post we have seen how window functions play an important role in stream analytics. Using concepts like tumbling windows, hopping windows, sliding windows, session windows, or other window functions we are able to compute aggregates on an unbounded data stream.

By today every good stream processing engine provides different windowing functions. Which one you should pick depends on your use case as they produce different results and have different complexity to compute. By migrating your batch jobs to streaming jobs you are able to report results in near real-time and react to important events in your business quickly.

Which stream processing engine is your favourite? Which window functions do you typically use and why? I'm looking forward to discussing with you in the comments :)

# References

- [1] Kleppmann, Martin. Designing data-intensive applications: The big ideas behind reliable, scalable, and maintainable systems. O'Reilly Media, Inc., 2017.
