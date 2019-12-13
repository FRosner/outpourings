---
title: Publishing Application Metrics to CloudWatch Using Micrometer
published: true
description: Observability is an important quality attribute. The Micrometer CloudWatch Registry exports meter values as CloudWatch metrics.
tags: aws, devops, kotlin, cloud
cover_image: https://thepracticaldev.s3.amazonaws.com/i/r40zmf9lv3yo1w2vcvlt.png
canonical_url: https://blog.codecentric.de/en/2019/12/publishing-application-metrics-to-cloudwatch-using-micrometer/
---

# Why Metrics?

In my post about [Quality Attributes In Software](https://dev.to/frosnerd/quality-attributes-in-software-1ha9) we introduced observability as an important quality attribute of modern software applications. Observability expresses whether changes in a system are reflected in a quantitative measure.

Especially in a DevOps culture, where automation is key in order to stay productive, observability plays an important role. Your team should define alarms based on relevant system metrics to ensure that service level objectives are met. However, most modern applications are very complex distributed systems and it is hard to measure everything.

Luckily if you are using a managed platform many metrics will be collected for you automatically. Your favorite cloud platform already collects metrics of your load balancers, application containers, databases, object storages, and so on. What the cloud providers cannot offer, however, are application specific metrics, because they depend on your application logic.

[Micrometer](https://micrometer.io/) is a vendor-neutral application metrics facade for the JVM that can be used to collect application specific metrics. It's a bit like [SLF4J](http://www.slf4j.org/) but for metrics.

In this blog post we will look at how to publish application metrics to AWS CloudWatch using Micrometer. The remainder of the post is structured as follows. First we will introduce some key concepts of Micrometer. The next section lists all meters that are available out of the box. Afterwards we are going to explain in detail how to publish metrics to CloudWatch using the CloudWatch meter registry. We are closing the post summarizing the main findings and discussing some problems we were facing.

All code examples are written in Kotlin.

# Micrometer Key Concepts

A *meter* is an abstraction for a set of measurements about your application. A meter is uniquely identified by its name and tags. A *meter registry* holds meters.

Depending on the implementation of the registry, meter values are exported to an external metric system such as [Promotheus](https://prometheus.io/) ([`PromotheusMeterRegistry`](https://micrometer.io/docs/registry/prometheus)) or [Graphite](https://graphiteapp.org/) ([`GraphiteMeterRegistry`](https://micrometer.io/docs/registry/graphite)). The most basic meter registry is the `SimpleMeterRegistry` which holds the latest value of each meter in memory.

Although there are more advanced concepts in Micrometer, meters and registries is all you need to know to get started. Next let's look at the meters that are available out of the box in Micrometer.

# Available Meters

## Basic Meters

### Counter

A counter reports a single value representing a count. It can be incremented by a positive amount. Counters are typically used to measure the frequency of certain events happing, e.g. the number of messages published to a queue or the number of errors when calling an external service. The following code snippet increments an API error counter by one.

```kotlin
val counter = Metrics.counter("api.errors")
counter.increment()
```

### Timer

A timer is used to measure short-duration latencies. A common use case for a timer is the time it takes to complete an HTTP request. A timer implicitly contains a counter that is incremented for each recording. The following code snippet records that our API request took 1234 ms.

```kotlin
val timer = Metrics.timer("api.request")
timer.record(Duration.ofMillis(1234))
```

The timer API also has methods that take a function argument. Micrometer will then execute the function and measure the time, finally returning the result. If you want to measure the time yourself, you may simply record the computed duration in the end as done in the code above.

### Gauge

Gauges are used to report a numeric state at a certain time. In contrast to a counter which you can increment, a gauge watches the state of an object and reports the current state whenever the metric is exported. A common example is the number of messages in a queue, or the number of connections in your connection pool. The following code snippet creates a gauge that monitors the size of a queue.

```kotlin
val queue = Metrics.gauge(
    "queue.size",
    ArrayBlockingQueue<String>(10),
    { it.size.toDouble() }
)
```

Note that the return value is the queue and not the gauge. There is no need to interact with the gauge again after creation. It will automatically export the size. The gauge will not block garbage collection of the queue once as it uses only a weak reference internally.

### Distribution Summary

A distribution summary is similar to a timer but it does not record time but other units, e.g. bytes. It will then export metrics of different summary statistics, such as mean, quantiles, and count. The following code snippet shows how to create a distribution summary that measures the number of bytes in each request.

```kotlin
val summary = Metrics.summary("request.payload.size")
summary.record(120.0)
```

If you want to configure the meter, e.g. changing the quantiles that are reported or adjust the unit of measurement, you need to use the distribution summary builder.

## Advanced Meters

### Long Task Timer

A long task timer is a timer that emits values even if the task is not finished. A normal timer only records the duration once the event is complete. This can be useful for long running processes such as batch jobs which might take multiple hours.

If you have an alarm configured based on an upper threshold of one hour and the job takes ten hours instead, you want to be alarmed at the moment the one hour is passed and not wait for nine more hours to receive metrics data.

Long task timers are constructed as regular timers:

```kotlin
val timer = Metrics.more().longTaskTimer("job.duration")
```

### Function Counter

A function counter is a counter that takes a monotonically increasing function as an argument and reports the function value. It could be viewed as a mixture between a counter and a gauge.

The code below shows how you can use a function counter to measure the eviction count of your [Caffeine](https://github.com/ben-manes/caffeine) cache.

```kotlin
val cache: LoadingCache<String, String> = TODO()
Metrics.more().counter(
    "cache.evictions", // name
    emptyList(),       // tags
    cache,             // object
    { it.stats().evictionCount().toDouble() } // count function
)
```

### Function Timer

A function timer is an extension of the function counter. In addition to the monotonically increasing count function you can also provide a timer function that measures the total time. In the next snippet you can see an example where we track the number and the total time of cache loads.

```kotlin
val cache: LoadingCache<String, String> = TODO()
Metrics.more().timer(
    "cache.get.latency", // name
    emptyList(),         // tags
    cache,               // object
    { it.stats().loadCount() },                // count function
    { it.stats().totalLoadTime().toDouble() }, // time function
    TimeUnit.NANOSECONDS // time unit
)
```

### Time Gauge

A time gauge is a gauge that represents a time value. It can be created similarly to a gauge. The following code snippet creates a custom time gauge that records the value of an atomic integer as seconds.

```kotlin
val value = Metrics.more().timeGauge(
    "custom.timeGauge",
    emptyList(),
    AtomicInteger(5),
    TimeUnit.SECONDS,
    { it.toDouble() }
)
```

# Micrometer CloudWatch Registry

After you figured out which application metrics you are interested in and know how to express them in terms of meters you can register those meters to the registries you want to use. This section explains how to use the Micrometer CloudWatch registry in order to export your metrics to AWS CloudWatch.

We will not go into details about CloudWatch metrics terminology now. Feel free to checkout my other post [Monitoring AWS Lambda Functions with CloudWatch](https://dev.to/frosnerd/monitoring-aws-lambda-functions-with-cloudwatch-1nap) for more information on the CloudWatch metrics concepts.

## Registry Setup

First, you need to add the registry as a dependency to your project. There are two modules available: [`micrometer-registry-cloudwatch`](https://mvnrepository.com/artifact/io.micrometer/micrometer-registry-cloudwatch) and [`micrometer-registry-cloudwatch2`](https://mvnrepository.com/artifact/io.micrometer/micrometer-registry-cloudwatch2). The only difference is that the former uses the AWS Java SDK version 1 and the latter uses version 2. It is recommended to use version 2.

To create a new registry you first need to create a `CloudWatchConfig`. As the CloudWatch registry is a `StepMeterRegistry`, `CloudWatchConfig` inherits from the `StepConfig` interface. A step meter registry publishes metrics in predefined intervals (steps) and normalizes the metric values for each step, e.g. by adding up individual counter increments.

In addition to the configuration options available for every step meter registry, the CloudWatch config requires to specify a namespace for the metrics to be published. The following snippet creates a new CloudWatch config that publishes all metrics to the `Company/App` namespace every minute.

```kotlin
val config = object : CloudWatchConfig {
    private val configuration = mapOf(
        "cloudwatch.namespace" to "Company/App",
        "cloudwatch.step" to Duration.ofMinutes(1).toString()
    )

    override fun get(key: String): String? =
        configuration[key]
}
```

Next we create the meter registry by providing the config, a clock, and an asynchronous CloudWatch client.

```kotlin
val registry = CloudWatchMeterRegistry(
  config,
  Clock.SYSTEM,
  CloudWatchAsyncClient.create()
)
```

We can then either add the registry to the Micrometer singleton using `Metrics.addRegistry(registry)`, or register new meters directly.

## Registering Meters

Registering new meters is easy. You can either use the factory methods provided by the global `Metrics` singleton (if you added the CloudWatch registry before) or the ones provided directly by the registry. The meter examples of the previous section were created like this. For more flexibility you can use the meter builders and call the `register` method at the end.

At every step the CloudWatch registry will collect the data for all registered meters and publish CloudWatch metrics accordingly. Those metrics will be published in the namespace specified in the registry configuration. The metric dimensions are directly derived from the meter tags.

The number of metrics published per meter and their names depend on the meter type. The name of each metric is created by concatenating the name prefix and suffix. The prefix is always set to the meter name. The suffix depends on the value that is represented by this metric.

A counter, for example, emits only a single metric which represents the count but a long task timer emits the task duration as well as the number of active tasks. The following table illustrates the different metrics (represented by their suffixes) that are emitted for the respective meter.

| Meter   | Metrics Suffixes |
|---------|------------------|
| Counter | `count` |
| Timer | `sum`, `count`, `avg`, `max` |
| Gauge | `value` |
| Distribution Summary | `sum`, `count`, `avg`, `max` |
| Long Task Timer | `activeTasks`, `duration` |
| Function Counter | `count` |
| Function Timer | `count`, `avg` |
| Time Gauge | `value` |

If you did everything correctly, Micrometer should now start publishing your recorded meter values to CloudWatch.

# Summary and Discussion

In this post we have seen how Micrometer can be used to publish metrics from your application to different monitoring systems. It works as a flexible layer of abstraction between your code and the monitoring systems so that you can easily swap or combine them.

Thanks to the CloudWatch meter registry we can export meter values as CloudWatch metrics. The configuration is simple but we also encountered two problems. First we had the problem that after some time we received a lot of `java.io.IOException`s. Turns out that there is a [known problem](https://github.com/aws/aws-sdk-java-v2/issues/1380) where CloudWatch asks the client to close the connection and for some reason the Java SDK ignores this request and tries to keep reusing it.

The second problem is related to the implementation of step timers. The [`StepTimer`](https://github.com/micrometer-metrics/micrometer/blob/49162a881c4c80976980d6ea0ef45d2d59c4ca14/micrometer-core/src/main/java/io/micrometer/core/instrument/step/StepTimer.java) class is used by step registries to pre-aggregate timer data. Step timers store the maximum duration in a [`TimeWindowMax`](https://github.com/micrometer-metrics/micrometer/blob/49162a881c4c80976980d6ea0ef45d2d59c4ca14/micrometer-core/src/main/java/io/micrometer/core/instrument/distribution/TimeWindowMax.java) which implements a decaying maximum value based on a ring buffer. After a configurable amount of time it will forget old maximum values such that you avoid a monotonic behaviour of your maximum metric.

The problem is however that the time after which the `TimeWindowMax` forgets a value is not synced with the step time of the registry. If you configure a step time of 100 seconds but your maximum decays after 10 seconds you essentially lose 90% of your data. This also means if you have very few durations recorded the maximum might even show as 0 although there were durations recorded.

This is especially weird because the other metrics such as the average duration is computed based on all recorded durations between two steps. Maybe we are not using the API correctly but it looks like a design flaw to us. If anyone has a suggestion how to deal with this problem, please let us know in the comments below!

In addition to the concepts presented in this post, Micrometer offers more advanced functionality such as meter filters, custom meters and meter registries as well as integrations with different libraries and frameworks. Feel free to check out other resources for more information on those topics.
