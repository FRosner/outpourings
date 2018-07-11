---
title: Sensor Data Processing on AWS using IoT Core, Kinesis and ElastiCache
published: true
description: In this blog post we want to build a sensor data backend powered by IoT Core, Kinesis, Lambda, ElastiCache, Elastic Beanstalk, and S3. The architecture should be extensible so we can add more functionality later.
tags: aws, cloud, iot, serverless
cover_image: https://thepracticaldev.s3.amazonaws.com/i/mjwcjrz38h5508e6i8so.png
---

This blog post is part of my AWS series:

- [Infrastructure as Code - Managing AWS With Terraform](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o)
- [Deploying an HTTP API on AWS using Lambda and API Gateway](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61)
- [Deploying an HTTP API on AWS using Elastic Beanstalk](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-elastic-beanstalk-5dh7)
- [Deploying and Benchmarking an AWS RDS MySQL Instance](https://dev.to/frosnerd/deploying-and-benchmarking-an-aws-rds-mysql-instance-2faf)
- [Event Handling in AWS using SNS, SQS, and Lambda](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng)
- [Continuous Delivery on AWS With Terraform and Travis CI](https://dev.to/frosnerd/continuous-delivery-on-aws-with-terraform-and-travis-ci-3914)
- [**Sensor Data Processing on AWS using IoT Core, Kinesis and ElastiCache**](#)

# Introduction

Internet of Things (IoT) became a hot topic in the recent years. Companies are [forecasting billions](https://spectrum.ieee.org/tech-talk/telecom/internet/popular-internet-of-things-forecast-of-50-billion-devices-by-2020-is-outdated) of connected devices in the years to come. IoT applications have different characteristics than traditional software projects. Applications operate on constrained hardware, network connections are unreliable, and the data coming from many different sensors need to be available in near real-time.

With the rise of cheap and available microprocessors and microcontrollers like the [Rasperry Pi](https://www.raspberrypi.org/) and [Arduino](https://www.arduino.cc/) products, the barrier of entry for working on IoT products has been lowered significantly. But also the software and development toolstack matured.

In December 2015 AWS IoT became generally available. AWS IoT is a collection of products to manage and connect IoT devices to the cloud. Its [IoT Core](https://aws.amazon.com/iot-core/) product acts as the entry point. IoT Core accepts data via [MQTT](https://en.wikipedia.org/wiki/MQTT) and then processes and forwards it to other AWS services according to preconfigured rules.

In this blog post we want to build an exemplary sensor data backend powered by IoT Core, Kinesis, Lambda, ElastiCache, Elastic Beanstalk, and S3. The goal is to accept sensor data, persist it in an S3 bucket, and at the same time display a live feed on the web. The architecture should be extensible so we can add more functionality like analytics or notifications later.

The remainder of the post is structured as follows. First we will present the architecture overview. Afterwards we are going to deep dive into the implementation. We will omit going into details about the VPC and networking part as well as the Elastic Beanstalk deployment as this has been discussed in previous posts already. We are closing the blog post discussing the main findings.

# Architecture

![architecture overview](https://thepracticaldev.s3.amazonaws.com/i/1zm11u6uwpo9vi3gureo.png)

IoT Core acts as the MQTT message broker. It uses topics to route messages from publishers to subscribers. Whenever a message is published to a topic, all subscribers will be notified about the message. IoT core allows us to send messages to other AWS services efficiently using *rules*. A rule corresponds to a SQL select statement which defines when it should be triggered, e.g. for all messages from a certain topic.

Each rule can have multiple actions associated with it. An action defines what should happen to the selected messages. There are many [different actions](https://docs.aws.amazon.com/iot/latest/developerguide/iot-rule-actions.html) supported but we are only going to use the Firehose and Kinesis actions in the course of this post.

The Firehose action forwards the messages to a [Kinesis Firehose delivery stream](https://aws.amazon.com/kinesis/data-firehose/). Firehose collects messages for a configured amount of time or until a certain batch size is reached and persists it to the specified location. In our case we would like to persist the messages as small batches in an S3 bucket.

A [Kinesis data stream](https://aws.amazon.com/kinesis/data-streams/) is used to decouple the processing logic from the data ingestion. This enables us to asynchronously consume messages from the stream by multiple independent consumers. As the message offset can be managed individually by each consumer we can also decide to replay certain messages in case of downstream failure.

The main data processing is happening within our Lambda function. A convenient way to process a Kinesis data stream with a Lambda function is to configure the stream as an [event source](https://docs.aws.amazon.com/lambda/latest/dg/invocation-options.html). We will use this stream-based model, because Lambda polls the stream for you and when it detects new records, invokes your function, passing the new records as a parameter. It is possible to add more consumers to the data stream, e.g., an [Akka Streams](https://github.com/StreetContxt/kcl-akka-stream) application that allows more granular control of the message digestion.

The Lambda function will update a Redis instance managed by [ElastiCache](https://aws.amazon.com/elasticache). In our example we will increment a message counter for each record, as well as storing the last message received. We are using Redis' [Pub/Sub](https://redis.io/topics/pubsub) functionality to notify our web application, which updates all the clients through a WebSocket connection.

We are going to use the MQTT test client built into IoT core for publishing messages to our topic. As an outlook please find an animation of the final result below. Let's look into the implementation step by step in the next section.

![demo](https://thepracticaldev.s3.amazonaws.com/i/lr6mq7pw22ol3r7enzhw.gif)

# Implementation

## Development Tool Stack

To develop the solution we are using the following tools:

- Terraform v0.11.7
- SBT 1.0.4
- Scala 2.12.6
- IntelliJ + Scala Plugin + Terraform Plugin

The [source code](https://github.com/FRosner/aws-iot-test) is available on GitHub. Now let's look into the implementation details of each component.

## IoT Core

![iot core](https://thepracticaldev.s3.amazonaws.com/i/m38hfkc6svlxssfrt3yf.png)

When working with IoT core there is no setup required. Every AWS account is able to use the MQTT broker as a fully managed service out of the box. So the only thing we need to do is to configure our topic rule and the respective actions forwarding messages to Kinesis and Firehose.

```conf
resource "aws_iot_topic_rule" "rule" {
  name        = "${local.project_name}Kinesis"
  description = "Kinesis Rule"
  enabled     = true
  sql         = "SELECT * FROM 'topic/${local.iot_topic}'"
  sql_version = "2015-10-08"

  kinesis {
    role_arn    = "${aws_iam_role.iot.arn}"
    stream_name = "${aws_kinesis_stream.sensors.name}"
    partition_key = "$${newuuid()}"
  }

  firehose {
    delivery_stream_name = "${aws_kinesis_firehose_delivery_stream.sensors.name}"
    role_arn = "${aws_iam_role.iot.arn}"
  }
}
```

The rule will be triggered for all messages in the `topic/sensors` topic. Using `newuuid()` as a partition key for Kinesis is fine for our demo as we will anyway have only one shard. In a productive scenario you should think about choosing the partition key in a way that fits your requirements.

The execution roles used need to allow the `kinesis:PutRecord` and `firehose:PutRecord` action, respectively. Here we are using the same role twice but I recommend to setup two roles with the least possible permissions.

Now that we have the rule configured, let's create the Firehose delivery stream and the Kinesis data stream next.

## Firehose Delivery Stream

![firehose delivery stream](https://thepracticaldev.s3.amazonaws.com/i/2ekzesfjh5wmpi0zjqr8.png)

To setup the Firehose delivery stream we specify the destination type (`s3`) and configure it accordingly. As we created S3 buckets multiple times throughout this series we will omit the bucket resource here. The two parameters `buffer_size` (MB) and `buffer_interval` (s) control how long we are waiting for new data to arrive before persisting a partition to S3.

```conf
resource "aws_kinesis_firehose_delivery_stream" "sensors" {
  name        = "${local.project_name}-s3"
  destination = "s3"

  s3_configuration {
    role_arn        = "${aws_iam_role.firehose.arn}"
    bucket_arn      = "${aws_s3_bucket.sensor_storage.arn}"
    buffer_size     = 5
    buffer_interval = 60
  }
}
```

The execution role needs to have permissions to access the S3 bucket as well as the Kinesis stream. Please find the policy document used below.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:AbortMultipartUpload",
        "s3:GetBucketLocation",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:ListBucketMultipartUploads",
        "s3:PutObject"
      ],
      "Resource": [
        "${aws_s3_bucket.sensor_storage.arn}",
        "${aws_s3_bucket.sensor_storage.arn}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "kinesis:DescribeStream",
        "kinesis:GetShardIterator",
        "kinesis:GetRecords"
      ],
      "Resource": "${aws_kinesis_stream.sensors.arn}"
    }
  ]
}
```

This should have our raw data persistence layer covered. All incoming messages will be dumped to S3. Let's tend to the Kinesis data stream next which is important for the data processing.

## Kinesis Data Stream

![kinesis data stream](https://thepracticaldev.s3.amazonaws.com/i/36arcez7baeptkfyfmn5.png)

The Kinesis data stream will have only one shard and a retention period of 24 hours. Each shard supports a certain read and write throughput, limited in the number and size of requests per time. You can scale out by adding more shards to your stream and choosing an appropriate partition key. We will keep the data for 24 hours, which is included in the base price.

```conf
resource "aws_kinesis_stream" "sensors" {
  name             = "${local.project_name}"
  shard_count      = 1
  retention_period = 24
}
```

Next, let's take a closer look at our Lambda function.

## Lambda

![lambda](https://thepracticaldev.s3.amazonaws.com/i/3mqzq5puoe1uxyqlizcd.png)

By now you should already be familiar with creating Lambda handlers. This time we will make use of an additional library which will allow AWS to handle the deserialization of the `KinesisEvent` input automatically: [`aws-lambda-java-events`](https://github.com/aws/aws-lambda-java-libs/tree/master/aws-lambda-java-events). We also have to include [`amazon-kinesis-client`](https://github.com/awslabs/amazon-kinesis-client) and [`aws-java-sdk-kinesis`](https://github.com/aws/aws-sdk-java/tree/master/aws-java-sdk-kinesis).

The connection to Redis is done using the [`net.debasishg.redisclient`](https://github.com/debasishg/scala-redis) package. Let's look at the code first and then go through it step by step.

```scala
class Handler extends RequestHandler[KinesisEvent, Void] {

  val port = System.getenv("redis_port").toInt
  val url = System.getenv("redis_url")

  override def handleRequest(input: KinesisEvent, context: Context): Void = {
    val logger = context.getLogger
    val redis = new RedisClient(url, port)
    val recordsWritten = input.getRecords.asScala.map { record =>
      val data = new String(record.getKinesis.getData.array())
      redis.set("sensorLatest", data)
      redis.incr("sensorCount")
    }
    redis.publish(
      channel = "sensors",
      msg = "updated"
    )
    val successAndFailure = recordsWritten.groupBy(_.isDefined).mapValues(_.length)
    logger.log(s"Successfully processed: ${successAndFailure.getOrElse(true, 0)}")
    logger.log(s"Failed: ${successAndFailure.getOrElse(false, 0)}")
    null
  }

}
```

Here's what happens:

- Read `$redis_url` and `$redis_port` environment variables (error handling omitted)
- For each incoming `KinesisEvent`, the Lambda function will be invoked. The event contains a list of records since the last invocation. We will see later how we can control this part.
- Connect to the ElastiCache Redis instance. It might make sense to reuse the connection by setting it up outside of the request handling method. I am not sure about the thread safety and how AWS Lambda handles the object creation.
- For each message update the latest message value and increase the counter. It would be more efficient to aggregate all records locally within the Lambda and update Redis with the results of the whole batch but I was too lazy to do that.
- Publish to the `sensors` channel that new data has arrived so all clients can be notified.

As usual we have to define our Lambda resource. The Redis connection details will be passed via environment variables.

```conf
resource "aws_lambda_function" "kinesis" {
  function_name    = "${local.project_name}"
  filename         = "${local.lambda_artifact}"
  source_code_hash = "${base64sha256(file(local.lambda_artifact))}"
  handler          = "de.frosner.aws.iot.Handler"
  runtime          = "java8"
  role             = "${aws_iam_role.lambda_exec.arn}"
  memory_size      = 1024
  timeout          = 5

  environment {
    variables {
      redis_port = "${aws_elasticache_cluster.sensors.port}"
      redis_url  = "${aws_elasticache_cluster.sensors.cache_nodes.0.address}"
    }
  }
}
```

Last but not least we tell Lambda to listen to Kinesis events, making it poll for new messages. We choose the [`LATEST`](https://docs.aws.amazon.com/kinesis/latest/APIReference/API_GetShardIterator.html#API_GetShardIterator_RequestSyntax) shard iterator, which corresponds to moving the offset always to the latest data, consuming every message only once. We could also decide to consume all records (`TRIM_HORIZON`) or starting from a given timestamp (`AT_TIMESTAMP`).

The batch size controls the maximum amount of messages processed by one Lambda call. Increasing it has a positive effect on the throughput, while on the other hand a small batch size might lead to better latency. Here's the Terraform resource definition for our event source mapping.

```conf
resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  batch_size        = 10
  event_source_arn  = "${aws_kinesis_stream.sensors.arn}"
  enabled           = true
  function_name     = "${aws_lambda_function.kinesis.id}"
  starting_position = "LATEST"
}
```

In order to push data to the web layer, we will create our ElastiCache Redis instance in the following section.

## ElastiCache Redis

![redis](https://thepracticaldev.s3.amazonaws.com/i/ucfuhkcnitkw0gvd4d6h.png)

We will use a single `cache.t2.micro` instance running Redis 4.0. Similar to RDS we can also pass the `apply_immediately` flag to force updates even if outside the maintenance window.

```conf
resource "aws_elasticache_cluster" "sensors" {
  cluster_id           = "${local.project_name}"
  engine               = "redis"
  node_type            = "cache.t2.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis4.0"
  port                 = "${var.redis_port}"
  security_group_ids   = ["${aws_security_group.all.id}"]
  subnet_group_name    = "${aws_elasticache_subnet_group.private.name}"
  apply_immediately    = true
}
```

That's it! What is left is only the Elastic Beanstalk application for the UI.

## Elastic Beanstalk Web UI

![elastic beanstalk web ui](https://thepracticaldev.s3.amazonaws.com/i/a7nsvbk85ro58kcy8l1u.png)

The Elastic Beanstalk application consists of a frontend and a backend. The frontend is in form of a single HTML file with JavaScript and CSS. Nothing fancy going on there. The backend is written in Scala and utilizes the same Redis library we already used in the Lambda function, as well as Akka HTTP for serving the static files and handling the WebSocket connections.

### Frontend

The frontend will feature three outputs: The message count, the last message, and when it received the last update from the server. Below you will find a screenshot of the UI and the HTML code.

![frontend](https://thepracticaldev.s3.amazonaws.com/i/6plgk0br1ii2xacktrbm.png)

```html
<html>
<head>
    <title>Sensor Data Example</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="http://fargo.io/code/jquery-1.9.1.min.js"></script>
    <link href="http://fargo.io/code/ubuntuFont.css" rel="stylesheet" type="text/css">
    <script src="main.js"></script>
</head>
<body>
<div>
    <p>Message count: <span id="messageCount"></span></p>
    <p>Last message: <span id="lastMessage"></span></p>
    <p>Last update: <span id="lastUpdate"></span></p>
</div>
<script>
$(document).ready(WebSocketTest);
</script>
</body>
</html>
```

The JavaScript part is also rather straightforward. We will use the built-in WebSocket support and provide handlers for `onopen`, `onmessage`, and `onclose` events. The `onmessage` event will parse the data received and fill the appropriate text fields. Note that we have to build the WebSocket URL using `window.location`, because it has to be an absolute URL in all the browsers I know.

```javascript
var loc = window.location, protocol;
if (loc.protocol === "https:") {
    protocol = "wss:";
} else {
    protocol = "ws:";
}
var socketUrl = protocol + "//" + loc.host + loc.pathname + "ws";

function WebSocketTest() {
  if ("WebSocket" in window) {
    console.log("Connecting to " + socketUrl);
    var ws = new WebSocket(socketUrl);

    ws.onopen = function() {
      console.log("Connection established");
    };

    ws.onmessage = function (evt) {
      var msg = JSON.parse(evt.data);
      console.log("Message received: " + msg);
      $("#lastUpdate").text(new Date());
      $("#lastMessage").text(msg.latest);
      $("#messageCount").text(msg.count);
    };

    ws.onclose = function() {
      console.log("Connection closed");
    };
  } else {
     console.error("WebSocket not supported by your browser!");
  }
}
```

### Backend

The backend consists of an Akka HTTP web server and two Redis connections. We have to use two connections here because Redis does not allow using the same connection for Pub/Sub and normal key value operations at the same time.

Let's look into the code. As always you need to have an actor system, actor materializer, and execution context if required. We are going to omit this for brevity reasons. Setting up the HTTP server with WebSocket support is illustrated in the following listing. We are routing two paths, one for the WebSocket connection and one for the static HTML file, which contains all JavaScript and CSS inline. We ignore all incoming messages and will forward messages coming from Redis to all clients. Both interface and port will be passed by Elastic Beanstalk.

```scala
val route =
  path("ws") {
    extractUpgradeToWebSocket { upgrade =>
      complete(upgrade.handleMessagesWithSinkSource(Sink.ignore, redisSource))
    }
  } ~ path("") {
    getFromResource("index.html")
  }

val interface = Option(System.getenv("INTERFACE")).getOrElse("0.0.0.0")
val port = System.getenv("PORT").toInt
val bindingFuture = Http().bindAndHandle(route, interface, port)
```

The next task is to define the Redis source. The Redis Pub/Sub API requires a callback function that is invoked for every message in the subscribed channel. This is not compatible with Akka Streams out of the box, so we have to use a little trick to transform our Redis messages to a `Source` object. The following listing illustrates the Redis source creation as well as the channel subscription.

```scala
val redis_port = System.getenv("redis_port").toInt
val redis_url = System.getenv("redis_url")
val redis = new RedisClient(redis_url, redis_port)
val redisPubSub = new RedisClient(redis_url, redis_port)

val (redisActor, redisSource) =
  Source.actorRef[String](1000, OverflowStrategy.dropTail)
    .map(s => TextMessage(s))
    .toMat(BroadcastHub.sink[TextMessage])(Keep.both)
    .run()

redisPubSub.subscribe("sensors") {
  case M(channel, message) =>
    val latest = redis.get("sensorLatest")
    val count = redis.get("sensorCount")
    redisActor ! s"""{ "latest": "${latest.getOrElse("0")}", "count": "${count.getOrElse("0")}" }"""
  case S(channel, noSubscribed) => println(s"Successfully subscribed to channel $channel")
  case other => println(s"Ignoring message from redis: $other")
}
```

Creating the Redis source is done using a combination of `Source.actorRef` and the `BroadcastHub.sink`. The source actor will emit every message it receives to the stream. We configure a buffer size of 1000 messages and discard the youngest element to make room for a new one in case of an overflow. Inside the subscription callback we can query Redis for the latest data and then send a JSON object to the Redis actor.

The broadcast hub sink emits a source we can plug into our WebSocket sink to generate the flow that will handle incoming WebSocket messages. As we need both, the actor and the source, we will keep both materialized values.

Now we can build our fat jar and upload it to S3. As it is basically the same procedure as in the [Elastic Beanstalk post](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-elastic-beanstalk-5dh7) we are not going to go into detail at this point. Let's look at the Terraform resources next.

### Terraform

First, we have to reference the fat jar inside the S3 bucket. Because the bucket has to exist before we can publish the jar using SBT, the Terraform deployment needs to happen in two stages. First we create only the artifact bucket and run `sbt webui/publish`, then we deploy the remaining infrastructure.

```conf
resource "aws_s3_bucket" "webui" {
  bucket        = "${local.project_name}-webui-artifacts"
  acl           = "private"
  force_destroy = true
}

data "aws_s3_bucket_object" "application-jar" {
  bucket = "${aws_s3_bucket.webui.id}"
  key    = "de/frosner/${local.webui_project_name}_2.12/${var.webui_version}/${local.webui_project_name}_2.12-${var.webui_version}-assembly.jar"
}
```

Next we can define the Elastic Beanstalk application, environment, and version. We are omitting all settings related to networking and execution at this point. The Redis connection details will be passed as environment variables. To enable WebSocket communication through the load balancer, we have to switch the protocol from HTTP to TCP using the `LoadBalancerPortProtocol` setting. In a proper setup you would also have to adjust the [nginx configuration](https://github.com/mitchellsimoens/Simple-WebSocket/blob/master/.ebextensions/files.config) because otherwise the connection might be terminated irregularly.

```conf
resource "aws_elastic_beanstalk_application" "webui" {
  name = "${local.project_name}"
}

resource "aws_elastic_beanstalk_environment" "webui" {
  name                = "${local.project_name}"
  application         = "${aws_elastic_beanstalk_application.webui.id}"
  solution_stack_name = "64bit Amazon Linux 2018.03 v2.7.1 running Java 8"

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "redis_url"
    value     = "${aws_elasticache_cluster.sensors.cache_nodes.0.address}"
  }
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "redis_port"
    value     = "${aws_elasticache_cluster.sensors.port}"
  }
  setting {
    namespace = "aws:elb:loadbalancer"
    name      = "LoadBalancerPortProtocol"
    value     = "TCP"
  }
}

resource "aws_elastic_beanstalk_application_version" "default" {
  name        = "${local.webui_assembly_prefix}"
  application = "${aws_elastic_beanstalk_application.webui.name}"
  description = "application version created by terraform"
  bucket      = "${aws_s3_bucket.webui.id}"
  key         = "${data.aws_s3_bucket_object.application-jar.key}"
}

output "aws_command" {
  value = "aws elasticbeanstalk update-environment --application-name ${aws_elastic_beanstalk_application.webui.name} --version-label ${aws_elastic_beanstalk_application_version.default.name} --environment-name ${aws_elastic_beanstalk_environment.webui.name}"
}
```

That's it! Now we have all required resources defined, except for the networking part which we skipped intentionally. Note that you cannot use the default VPC and subnets and security groups as otherwise neither the Lambda nor the Elastic Beanstalk EC2 instances can connect to ElastiCache. Next let's see our baby in action!

## Deployment and Usage

As mentioned before the deployment is done in multiple steps. First we create only the S3 bucket for uploading the Elastic Beanstalk artifact. Then we provision the remaining infrastructure. As Terraform does not support deploying Elastic Beanstalk application versions at this point we will execute the generated AWS CLI command afterwards.

```bash
cd terraform && terraform apply -auto-approve -target=aws_s3_bucket.webui; cd -
sbt kinesis/assembly && sbt webui/publish && cd terraform && terraform apply -auto-approve; cd -
cd terraform && $(terraform output | grep 'aws_command' | cut -d'=' -f2) && cd -
```

After completion we can open the Elastic Beanstalk environment URL to see the UI. If we assigned a DNS name we could use that one. Then we open the AWS IoT Console in another browser tab and navigate to the *Test* page. There we scroll to the *Publish* section, enter `topic/sensors` as the topic and can start publishing MQTT messages.

![demo](https://thepracticaldev.s3.amazonaws.com/i/lr6mq7pw22ol3r7enzhw.gif)

# Conclusion

In this blog post we have seen how to route MQTT messages towards Kinesis streams using IoT Core rules. Kinesis Firehose delivery streams are a convenient way to automatically persist a data stream in batches. Kinesis data streams as Lambda event sources give a more granular control over what to do with the data. With ElastiCache Redis as an intermediate storage layer and notification service we enable clients to get near-real time updates of the sensors.

Looking at the example solution we built there are a few things we could have done differently. Instead of having to pay for the Firehose delivery stream and the Kinesis data stream at the same time we could only use the data stream and add a custom polling consumer that persists the data in batches, potentially performing some basic format conversions like writing in a compressed columnar storage format.

While configuring Kinesis as an event source for Lambda works great it might become a bit costly if the Lambda function is constantly running. In that case it could pay off to use a custom consumer deployed in ECS EC2, for example.

Using Redis as the intermediate storage layer is only one out of many options. Picking the right data store for your problem is not trivial. Redis is fast because it is in-memory. If you need a more durable and scalable database, DynamoDB is also an option. Clients can subscribe to changes in a DynamoDB table through [DynamoDB streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html). Maybe you also want to add [ElasticSearch](https://www.elastic.co/products/elasticsearch) or [Graphite](https://github.com/graphite-project/whisper) as consumers.

What do you think? Did you use AWS IoT already for one of your projects? Did you also manage to automate the device management using Terraform? Please comment below!

---

Cover image by Wilgengebroed on Flickr - Cropped and sign removed from Internet of things signed by the author.jpg, CC BY 2.0, https://commons.wikimedia.org/w/index.php?curid=32745645
