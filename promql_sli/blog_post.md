---
title: Using PromQL Subqueries to Calculate Service Level Indicators
published: true
description: In this blog post we want to understand how you can use PromQL subqueries to calculate a reliability service level indicator (SLI).
tags: prometheus, monitoring, devops, sre
---

The Prometheus stack is a widely adopted, open-source monitoring and alerting solution. PromQL is a query language that lets you select, filter, and aggregate time series data stored in Prometheus. PromQL is fairly powerful, but the available functionality can be overwhelming at times.

In this blog post we want to understand how you can use subqueries, a feature that has been [added to Prometheus in 2019](https://prometheus.io/blog/2019/01/28/subquery-support/), to calculate a reliability service level indicator (SLI). We will start with a simple query and gradually evolve it.

In our fictive company we have a fictive service, that exposes its functionality via an HTTP API. The goal is to calculate the reliability SLI in two different ways:

1. The relative request success rate per day
2. The relative number of 5-minute windows per day that didn't have any request errors

The service exposes two relevant metrics:

1. `requests_total`, which is a counter representing the total number of requests processed by the service.
2. `requests_errors_total`, which is a counter representing the total number of failed requests.

For example, if you were looking at two service replicas from which we scrape `requests_errors_total` every minute over a few minutes, the values might look like this:

![request errors counter](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/e241qguz20pvwenx7zfk.png)

Note that Prometheus counters are [monotonic](https://prometheus.io/docs/concepts/metric_types/#counter). To calculate the request and error rate (per second), we can use the [`rate`](https://prometheus.io/docs/prometheus/2.38/querying/functions/#rate) function: `rate(requests_total)` and `rate(requests_errors_total)`. We can customize the time duration used for the rate calculation using [range vector selectors](https://prometheus.io/docs/prometheus/2.38/querying/basics/#range-vector-selectors). The following diagram shows the request error rates of our two services, aggregated over 1 minute windows.

![request error rate](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/s0o0rrdtuf93gyvczcjo.png)

When looking at the `rate` graph, you notice that the rate is only positive if there are actual changes to the counter. Since `rate` calculates the counter value change per second, the y-axis has been adjusted. Using `rate` over one day, we can now calculate the daily relative error rate:

```promql
# relative error rate
rate(requests_errors_total[1d]) / rate(requests_total[1d])
```

If our service has multiple replicas, and we want to calculate the relative error rate of all replicas combined, we can use the [`sum`](https://prometheus.io/docs/prometheus/2.38/querying/functions/#sum) aggregation operator.

![summed request error rate](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/k6lmji8bwtloubu3elry.png)

```promql
# relative error rate (summed over all replicas)
sum(rate(requests_errors_total[1d])) 
/
sum(rate(requests_total[1d]))
```

We now simply subtract the relative error rate from 1 to obtain the relative request success rate over a period of one day. Next, how can we calculate the relative number of 5-minute windows that didn't have any request failures over a day?

To accomplish this task, we can utilize [subqueries](https://prometheus.io/blog/2019/01/28/subquery-support/). Specifically, the `count_over_time` subquery which counts the number of time series existing in the specified time window. The following diagram illustrates a query that counts the number of times our error rate (aggregated over 1 minute) is positive, over a 6 minutes window, evaluated every minute. If evaluated at t=6, the result is 3, since we have 3 occurrences where the rate is positive. 

![count over time visualization](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/pda9m0745kyvhjskl341.png)

```promql
# absolute number of 5-minute windows with failed requests in 1 day
count_over_time(
  (
    sum(rate(requests_errors_total[5m])) > 0
  )[1d:5m]
)
```

The subquery range vector selector `[1d:5m]` takes two arguments. The first argument specifies the entire time window the subquery is taking into account, while the second argument represents the evaluation interval.

Next, let's divide the number of 5 minute windows with errors by the total number of 5 minute windows in a day, and subtract that number from 1 to get the percentage of error-free 5 minute windows over the entire day.

```promql
# relative number of 5-minute windows without failures per day
1
-
count_over_time(
  (
    sum(rate(requests_errors_total[5m])) > 0
  )[1d:5m]
) / (1 * 24 * 60 / 5)
```

This query concludes the post. If you want to explore the full potential of PromQL, please check out the [official documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/).