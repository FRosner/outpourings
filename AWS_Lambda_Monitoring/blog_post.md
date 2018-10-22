---
title: Monitoring AWS Lambda Functions With CloudWatch
published: true
description: In this blog post we want to take a look into how to monitor your AWS Lambda functions using Amazon CloudWatch.
tags: aws, devops, serverless, cloud
cover_image: https://thepracticaldev.s3.amazonaws.com/i/d2b4o0wdthz4282a2kox.jpg
---

This blog post is part of my AWS series:

- [Infrastructure as Code - Managing AWS With Terraform](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o)
- [Deploying an HTTP API on AWS using Lambda and API Gateway](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61)
- [Deploying an HTTP API on AWS using Elastic Beanstalk](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-elastic-beanstalk-5dh7)
- [Deploying and Benchmarking an AWS RDS MySQL Instance](https://dev.to/frosnerd/deploying-and-benchmarking-an-aws-rds-mysql-instance-2faf)
- [Event Handling in AWS using SNS, SQS, and Lambda](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng)
- [Continuous Delivery on AWS With Terraform and Travis CI](https://dev.to/frosnerd/continuous-delivery-on-aws-with-terraform-and-travis-ci-3914)
- [Sensor Data Processing on AWS using IoT Core, Kinesis and ElastiCache](https://dev.to/frosnerd/sensor-data-processing-on-aws-using-iot-core-kinesis-and-elasticache-26j1)
- [**Monitoring AWS Lambda Functions With CloudWatch**](#)

# Introduction

Functions as a Service products like AWS Lambda provide a great deal of convenience compared to bare metal, virtual machines, and also containerized deployments. You only have to manage the actual code you want to run and the rest is taken care of by the cloud provider. But are they also convenient to operate?

In this blog post we want to take a look into how to assist Lambda operations through monitoring and alerting using Amazon CloudWatch. We will use existing metrics but also create a custom metric filter to parse the memory consumption from CloudWatch logs.

The metrics are visualized in a CloudWatch dashboard and alarms are configured to push a notification towards an AWS SNS topic in case a threshold is breached. As usual everything will be deployed with HashiCorp Terraform. Below you find a screenshot of the resulting dashboard that we will have at the end of the post.

![dashboard overview](https://thepracticaldev.s3.amazonaws.com/i/gzreve3r515g5ogpgfsw.png)

The [source code](https://github.com/FRosner/aws-lambda-monitoring-alerting-example) is available on GitHub. Please note that we are not going to discuss the topics of [managing multiple Lambda functions](https://dev.to/frosnerd/yarnception-starting-yarn-within-yarn-through-gulp-and-when-it-is-useful-og3) within a single repository or how to show the [alarm notifications inside a Slack channel](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng) as this has been discussed in previous blog posts already.

# Metrics

In CloudWatch metrics are organized in so called *namespaces*. A namespace is like a folder for metrics and can be used to group together metrics of the same application. A *metric* is a time-ordered set of data points, also known as a time series. Examples are CPU usage of an EC2 instance or number of requests made towards your API.

Most AWS services send predefined metrics to CloudWatch out of the box but it is also possible to send custom metrics. As of today AWS Lambda exposes the following metrics to CloudWatch out of the box:

- **Invocations.** The invocations metric measures the number of times a function is invoked. Invocations can happen either through an event or an invocation API call. It includes both failed and successful invocations but not failed invocation requests, e.g. if throttling occurs.
- **Errors.** This metric measures the number of times an invocation failed due to an error in the function, a function timeout, out of memory error, or permission error. It does not include failures due to exceeding concurrency limits or internal service errors.
- **Dead letter errors.** If you configured a dead letter queue, AWS Lambda is going to write the event payload of failed invocations into this queue. The dead letter error metric captures failed deliveries of dead letters.
- **Duration.** The duration measures the elapsed wall clock time from when the function code starts to when it stops executing. Watch out as the clock is not monotonic you might get negative values.
- **Throttles.** Throttled invocations are counted whenever an invocation attempt fails due to exceeded concurrency limits.
- **Iterator age (stream only).** The iterator age metric is only available when the Lambda function is invoked by an AWS streaming service such as Kinesis. It represents the time difference between an event being written to the stream and the time it gets picked up by the Lambda function.
- **Concurrent executions.** This metric is an account-wide aggregate metric indicating the sum of concurrent executions for a given function. It is applicable for functions with a custom concurrency limit.
- **Unreserved concurrent executions.** Similar to the concurrent execution metric the unreserved concurrent executions metric is also an account-wide metric. It indicates the sum of concurrency of all functions that do not have a custom concurrency limit specified.

Every metric can have up to ten dimensions assigned. A *dimension* is a key-value pair that describes a metric and can be used to uniquely identify a metric in addition to the metric name. Metrics emitted by AWS Lambda have the following dimensions:

- **Function name.** The function name can be used to select a metric based on the name of the Lambda function.
- **Resource.** The resource dimension is useful to filter based on function version or alias.
- **Executed version.** You can use the executed version dimension to filter based on the function version when using alias invocations.

Metrics can be aggregated through so called *statistics*. CloudWatch offers the following statistics: Minimum, maximum, sum, average, count, and percentiles. The statistics are computed within the specified *period*. As far as I understand it uses a tumbling window to do that but I am not entirely sure. Please refer to my previous post about [Window Functions in Stream Analytics](https://dev.to/frosnerd/window-functions-in-stream-analytics-1m6c) for more information on tumbling windows.

# Metric Filters

As mentioned earlier it is also possible to generate custom metrics in addition to the ones that AWS services provide out of the box. When looking at AWS Lambda a metric of common interest is the maximum memory consumption.

Custom metrics can be written directly through the CloudWatch API, or using the AWS SDK. However the Lambda function itself does not have any information about its memory consumption. How can we solve this problem? Luckily metric filters are to the rescue! After every function execution AWS writes a report into the CloudWatch logs that looks like this:

```
REPORT RequestId: f420d819-d07e-11e8-9ef2-4d8f649fd167	Duration: 158.15 ms	Billed Duration: 200 ms Memory Size: 128 MB	Max Memory Used: 38 MB
```

This report contains the information we are looking for: `Max Memory Used: 38 MB`. CloudWatch provides a convenient functionality to convert logs into metrics called a *metric filter*.

A filter consists of a *pattern*, a *name*, a *namespace*, a *value*, and an optional *default value*. It applies the pattern to each log line and if it matches, emits the specified value inside a metric of the given name in the given namespace. The default value will be emitted if no log events occur.

To extract the maximum memory from the log line we can use the pattern below and emit the value `$max_memory_used_value`. For more information on the pattern syntax please refer to the [official documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html).

```
[
  report_label=\"REPORT\",
  request_id_label=\"RequestId:\", request_id_value,
  duration_label=\"Duration:\", duration_value, duration_unit=\"ms\",
  billed_duration_label1=\"Billed\", bill_duration_label2=\"Duration:\", billed_duration_value, billed_duration_unit=\"ms\",
  memory_size_label1=\"Memory\", memory_size_label2=\"Size:\", memory_size_value, memory_size_unit=\"MB\",
  max_memory_used_label1=\"Max\", max_memory_used_label2=\"Memory\", max_memory_used_label3=\"Used:\", max_memory_used_value, max_memory_used_unit=\"MB\"
]
```

I noticed that the maximum memory being written to the log is already aggregated across some previous invocations. My suspicion is that it refers to the maximum memory of one running instance behind the scenes which gets reset every time the function is starting up again, e.g. after a break or redeployment. If you have more information on that matter please leave a comment!

# Alarms

Metrics are an important building block to support your operations. In order to make them truly useful we need to define a process including either automated or manual actions based how metric values change over time.

CloudWatch allows you to define *alarms*, which are rules that trigger *actions* based on a threshold over a number of time periods for one metric. Each alarm is associated with one or more actions. This can be an EC2 action, an EC2 autoscaling action, or an SNS notification. If you send an SNS event you can implement many different consumers like a Lambda function sending a [Slack message](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng).

For our Lambda function we will implement the following three basic alarms:

- **Execution Time.** Every Lambda function has a configurable timeout. If your code runs longer than the timeout specified the invocation will be aborted. You can create an alarm if the execution time exceeds a certain percentage of the configured timeout. This way CloudWatch will notify you in case you might need to adjust the threshold or improve the performance of your code.
- **Maximum Memory.** Similar to the execution time there is also a configurable maximum amount of memory available. Thanks to our previously defined metric filter for the maximum used memory we can trigger an alarm if a certain threshold is exceeded.
- **Execution Errors.** Sometimes code breaks. It might happen because some downstream service is not available, the input format changed or your code contains a bug. By triggering an alarm for execution errors you can receive notifications and act accordingly. Note however that this will include all errors even if the invocation succeeded after a retry. If you are only interested in events that could not be processed even after retrying you need to configure a dead letter queue.

If you are using Terraform you can directly interpolate the execution timeout and maximum memory and pick a percentage for the threshold. The following listing illustrates creating an alarm resource with Terraform that gets triggered if your execution time exceeds 75% of the timeout.

```conf
resource "aws_cloudwatch_metric_alarm" "calculator-time" {
  alarm_name          = "${local.project-name}-calculator-execution-time"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Maximum"
  threshold           = "${aws_lambda_function.calculator.timeout * 1000 * 0.75}"
  alarm_description   = "Calculator Execution Time"
  treat_missing_data  = "ignore"

  insufficient_data_actions = [
    "${aws_sns_topic.alarms.arn}",
  ]

  alarm_actions = [
    "${aws_sns_topic.alarms.arn}",
  ]

  ok_actions = [
    "${aws_sns_topic.alarms.arn}",
  ]

  dimensions {
    FunctionName = "${aws_lambda_function.calculator.function_name}"
    Resource     = "${aws_lambda_function.calculator.function_name}"
  }
}
```

If you login to the AWS Console CloudWatch shows you an overview of all your current alarms. The table below illustrates the three alarms for our example function. I generated some test events and one of it was generating an error inside the function which triggered the corresponding alarm.

![failing alarm table](https://thepracticaldev.s3.amazonaws.com/i/ubsrxru4ekgtf5l9tq72.png)

In addition to the table you also have a very simple graph view of each alarm which is independent of CloudWatch dashboards. The next figure depicts the three graphs for our alarms.

![failing alarm chart](https://thepracticaldev.s3.amazonaws.com/i/9dnwrytamnh7h8cxsgwu.png)

# Dashboard

I am a big fan of automation. I believe that nobody should have to look at dashboards 24/7 trying to spot errors. Nevertheless dashboards are very useful to get a quick overview of the system. They also allow humans to spot new patterns which lead to implementing new types of alarms.

In CloudWatch a *dashboard* consists of multiple *widgets*. A widget can be a graph of metrics or text in Markdown syntax. For our example function we want to plot the four metrics execution time, max memory used, execution errors, and invocations.

Dashboards are internally stored as JSON objects and can also be managed by Terraform. The dashboard object consists of an array of widget objects. The source code of the complete dashboard ([`cloudwatch_dashboard.tf`](https://github.com/FRosner/aws-lambda-monitoring-alerting-example/blob/master/terraform/cloudwatch_dashboard.tf)) is too large to be displayed here so we will only look at two widgets to illustrate the point. The following listing shows the invocation sum widget.

```json
{
  "type": "metric",
  "x": 12,
  "y": 7,
  "width": 12,
  "height": 6,
  "properties": {
    "metrics": [
      [
        "AWS/Lambda", "Invocations",
        "FunctionName", "${aws_lambda_function.calculator.function_name}",
        "Resource", "${aws_lambda_function.calculator.function_name}",
        {
          "color": "${local.dashboard-calculator-invocation-color}",
          "stat": "Sum",
          "period": 10
        }
      ]
    ],
    "view": "timeSeries",
    "stacked": false,
    "region": "${data.aws_region.current.name}",
    "title": "Invocations"
  }
}
```

And here is what it looks like in the browser:

![invocations detail view](https://thepracticaldev.s3.amazonaws.com/i/2b8ar1al6bd352g3kt2y.png)

We can also add horizontal annotations to indicate our alarm threshold. Additionally it can be useful to display different statistics. For the execution time widget we added a horizontal annotation as well as two statistics: Maximum and average execution time. Please find the code and a screenshot of the result below.

```json
{
  "type": "metric",
  "x": 0,
  "y": 1,
  "width": 12,
  "height": 6,
  "properties": {
    "metrics": [
      [
        "AWS/Lambda", "Duration",
        "FunctionName", "${aws_lambda_function.calculator.function_name}",
        "Resource", "${aws_lambda_function.calculator.function_name}",
        {
          "stat": "Maximum",
          "yAxis": "left",
          "label": "Maximum Execution Time",
          "color": "${local.dashboard-calculator-max-time-color}",
          "period": 10
        }
      ],
      [
        "AWS/Lambda", "Duration",
        "FunctionName", "${aws_lambda_function.calculator.function_name}",
        "Resource", "${aws_lambda_function.calculator.function_name}",
        {
          "stat": "Average",
          "yAxis": "left",
          "label": "Average Execution Time",
          "color": "${local.dashboard-calculator-avg-time-color}",
          "period": 10
        }
      ]
    ],
    "view": "timeSeries",
    "stacked": false,
    "region": "${data.aws_region.current.name}",
    "yAxis": {
      "left": {
        "min": 0,
        "max": ${aws_lambda_function.calculator.timeout}000,
        "label": "ms",
        "showUnits": false
      }
    },
    "title": "Execution Time",
    "period": 300,
    "annotations": {
      "horizontal": [{
          "color": "${local.dashboard-calculator-max-time-color}",
          "label": "Alarm Threshold",
          "value": ${aws_cloudwatch_metric_alarm.calculator-time.threshold}
        }
      ]
    }
  }
}
```

![execution time detail view](https://thepracticaldev.s3.amazonaws.com/i/961wxj6tvnx1tk22nxpj.png)

# Conclusion

In this post we have seen how to create CloudWatch metric filters, alarms, and dashboards. We looked at the different metrics that are provided for Lambda functions out of the box and how to parse the maximum memory consumption from CloudWatch logs using a metric filter.

You can add automated alerting or even precautious actions based on alarms in order to react to dangerous situations in your system. A dashboard helps humans to get a glimpse on what is going on from time to time.

Did you ever use CloudWatch to manage metrics and alarms? I personally find it much more convenient to work with than using an external solution like ElasticSearch when working on Lambda functions. What is your opinion? Please let me know in the comments below.

---

Cover image by [Roger Schultz](https://flic.kr/p/bEEdn3)
