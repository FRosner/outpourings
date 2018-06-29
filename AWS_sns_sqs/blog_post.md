---
title: Event Handling in AWS using SNS, SQS, and Lambda
published: true
description: In this post we will develop an event pipeline which sends a message to a Slack channel whenever someone uploads a picture to an S3 bucket. We will use AWS SNS, SQS, and Lambda.
tags: aws, cloud, lambda, showdev
cover_image: https://thepracticaldev.s3.amazonaws.com/i/7aspcgbyc4wgp2iykwmp.png
---

This blog post is part of my AWS series:

- [Infrastructure as Code - Managing AWS With Terraform](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o)
- [Deploying an HTTP API on AWS using Lambda and API Gateway](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61)
- [Deploying an HTTP API on AWS using Elastic Beanstalk](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-elastic-beanstalk-5dh7)
- [Deploying and Benchmarking an AWS RDS MySQL Instance](https://dev.to/frosnerd/deploying-and-benchmarking-an-aws-rds-mysql-instance-2faf)
- [**Event Handling in AWS using SNS, SQS, and Lambda**](#)

# Introduction

In reactive, message-driven applications it is crucial to decouple producers and consumers of messages. Combining publish/subscribe (pub/sub) and queueing components we are able to build resilient, scalable and fault-tolerant application architectures. AWS offers a variety of components which implement pub/sub or queueing.

In this post we want to get to know two simple but powerful components for event and message processing on AWS: The [Simple Notification Service](https://aws.amazon.com/sns/) (SNS) and the [Simple Queue Service](https://aws.amazon.com/sqs/) (SQS).

The goal is to develop an event pipeline which sends a message to a Slack channel whenever someone uploads a picture to an S3 bucket. For demonstration purposes we will also store the events in a queue for asynchronous processing. The architecture involves S3 event notifications, an SNS topic, an SQS queue, and a Lambda function sending a message to the Slack channel. Here is an animation of the final result.

![notification](https://user-images.githubusercontent.com/3427394/41991790-023da6e6-7a47-11e8-957b-9990c3683eed.gif)

The remainder of this post is structured as follows. First there will be an overview of the architecture. Then - as usual - we will go into details about how to set things up using Terraform step by step. We are closing the post by discussing the main findings.

# Architecture

Let's look at the high level architecture. When a client uploads an image to the configured S3 bucket, an S3 event notification will fire towards SNS, publishing the event inside the respective topic. There will be two subscribers for that topic: An SQS queue and a Lambda function.

The SQS queue stores the event for asynchronous processing, e.g. thumbnail generation or image classification. The Lambda function parses the event and sends a notification message to a Slack channel. Within the scope of this blog post we are not going to discuss the asynchronous processing part. Due to the decoupling of publishing and subscribing with SNS we are free to add more consumers for the events later.

![architecture overview](https://thepracticaldev.s3.amazonaws.com/i/7aspcgbyc4wgp2iykwmp.png)

Let's look at the individual components in detail. S3 organizes objects in buckets. Within a bucket you can reference individual objects by key. Uploading a file to S3 can either be done via the [AWS Console](https://s3.console.aws.amazon.com/s3/), the [AWS CLI](https://docs.aws.amazon.com/cli/latest/reference/s3/), or directly through the [S3 API](https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html).

In this post we are going to use the CLI for uploading. Both the Console as well as the CLI work pretty smoothly, as they handle all the low level communication with S3 for you. If you are using the S3 API and your bucket is not publicly writable, you have to manually authenticate your requests using the [AWS Signature Version 4](https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-authenticating-requests.html).

S3 allows to configure [event notifications](https://docs.aws.amazon.com/AmazonS3/latest/dev/NotificationHowTo.html). Events can be created based on object creation or deletion, as well as notification in case of object loss for objects with reduced redundancy. You can choose to either send the event towards an SNS topic, an SQS queue, or a Lambda function.

In our case we are going to send the events to SNS and then allow interested applications to subscribe. This is referred to as the messaging [fanout pattern](https://aws.amazon.com/blogs/compute/messaging-fanout-pattern-for-serverless-architectures-using-amazon-sns/). Instead of sending events directly to all parties, by using SNS as an intermediate broker we decouple publishing and subscription.

SNS is a simple pub/sub service which organizes around *topics*. A topic groups together messages of the same type which might be of interest to a set of subscribers. In case of a new message being published to a topic, SNS will notify all subscribers. You can configure delivery policies including configuration of maximum receive rates and retry delays.

The goal is to send a Slack message on object creation within our S3 bucket. We achieve that by subscribing a Lambda function to the SNS topic. On invocation the Lambda function will parse and inspect the event notification, extract relevant information, and forward it to a preconfigured Slack webhook.

We will also subscribe an SQS queue to the topic, storing the events for asynchronous processing by, e.g., another Lambda function or a long running polling service. The next section explains how to implement the architecture.

# Implementation

## Development Tool Stack

To develop the solution we are using the following tools:

- Terraform v0.11.7
- SBT 1.0.4
- Scala 2.12.6
- IntelliJ + Scala Plugin + Terraform Plugin

The [source code](https://github.com/FRosner/sns-sqs-test) is available on GitHub. Now let's look into the implementation details of each component.

## S3 Bucket

![s3 bucket architecture](https://thepracticaldev.s3.amazonaws.com/i/mbt8wqcja0cjrzs2oj7n.png)

First we will create the S3 bucket where we can upload pictures to. We need to provide a bucket name and an ACL. The ACL will be `public-read` this time as we want to enable people to make their images publicly readable but require authentication for uploads. The `force-destroy` option allows Terraform to destroy the bucket even if it is not empty.

```conf
variable "aws_s3_bucket_upload_name" {
  default = "sns-sqs-upload-bucket"
}

resource "aws_s3_bucket" "upload" {
  bucket = "${var.aws_s3_bucket_upload_name}"
  acl    = "public-read"
  force_destroy = true
}
```

## SNS Topic

![SNS topic architecture](https://thepracticaldev.s3.amazonaws.com/i/wpa8wom8vit6rmnoqp4o.png)

Next let's create the SNS topic. To create an SNS topic we only need to provide a name.

```conf
resource "aws_sns_topic" "upload" {
  name = "sns-sqs-upload-topic"
}
```

The topic alone is not going to be useful if we do not allow anyone to publish messages. In order to do that we attach a policy to the topic which allows our bucket resource to perform the `SNS:Publish` action on the topic.

```conf
resource "aws_sns_topic_policy" "upload" {
  arn = "${aws_sns_topic.upload.arn}"

  policy = "${data.aws_iam_policy_document.sns_upload.json}"
}

data "aws_iam_policy_document" "sns_upload" {
  policy_id = "snssqssns"
  statement {
    actions = [
      "SNS:Publish",
    ]
    condition {
      test = "ArnLike"
      variable = "aws:SourceArn"

      values = [
        "arn:aws:s3:::${var.aws_s3_bucket_upload_name}",
      ]
    }
    effect = "Allow"
    principals {
      type = "AWS"
      identifiers = [
        "*"]
    }
    resources = [
      "${aws_sns_topic.upload.arn}",
    ]
    sid = "snssqssnss3upload"
  }
}
```

## S3 Event Notification

![S3 event notification architecture](https://thepracticaldev.s3.amazonaws.com/i/muj2bboalqwlr7p7tmny.png)

With our SNS topic and S3 bucket resource defined we can combine them by creating an S3 bucket notification which will publish to the topic. We can control the [events](https://docs.aws.amazon.com/AmazonS3/latest/dev/NotificationHowTo.html#notification-how-to-event-types-and-destinations) we want to be notified about. In our case we are interested in all object creation events. We can also specify optional filters, e.g. only notifications for `*.jpeg` files in this case.

```conf
resource "aws_s3_bucket_notification" "upload" {
  bucket = "${aws_s3_bucket.upload.id}"

  topic {
    topic_arn     = "${aws_sns_topic.upload.arn}"
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".jpeg"
  }
}
```

## SQS Queue

![SQS queue architecture](https://thepracticaldev.s3.amazonaws.com/i/lr04pqwsaqmtgkcql05p.png)

The creation of the SQS queue works in a similar fashion. We have to provide a name for the queue and a policy which allows SNS to send messages to the queue.

```conf
resource "aws_sqs_queue" "upload" {
  name = "sns-sqs-upload"
}
```

```conf
resource "aws_sqs_queue_policy" "test" {
  queue_url = "${aws_sqs_queue.upload.id}"
  policy = "${data.aws_iam_policy_document.sqs_upload.json}"
}

data "aws_iam_policy_document" "sqs_upload" {
  policy_id = "snssqssqs"
  statement {
    actions = [
      "sqs:SendMessage",
    ]
    condition {
      test = "ArnEquals"
      variable = "aws:SourceArn"

      values = [
        "${aws_sns_topic.upload.arn}",
      ]
    }
    effect = "Allow"
    principals {
      type = "AWS"
      identifiers = [
        "*"]
    }
    resources = [
      "${aws_sqs_queue.upload.arn}",
    ]
    sid = "snssqssqssns"
  }
}
```

## SQS Subscription

![SQS subscription architecture](https://thepracticaldev.s3.amazonaws.com/i/ggqipqjgq460w7j0klsx.png)

Next we need to subscribe the queue to the topic. SNS topic subscriptions support [multiple protocols](https://docs.aws.amazon.com/sns/latest/api/API_Subscribe.html): `http`, `https`, `email`, `email-json`, `sms`, `sqs`, `application`, `lambda`. In this case we will use the `sqs` protocol and provide both the topic and the queue endpoint.

```conf
resource "aws_sns_topic_subscription" "sqs" {
  topic_arn = "${aws_sns_topic.upload.arn}"
  protocol  = "sqs"
  endpoint  = "${aws_sqs_queue.upload.arn}"
}
```

## Slack Webhook

![slack webhook architecture](https://thepracticaldev.s3.amazonaws.com/i/xpxn3s06q1frpcyxaiww.png)

Before we can write our Lambda function and subscribe it to the SNS topic as well, we will create the Slack webhook. Working with incoming webhooks in Slack is done in [four steps](https://api.slack.com/incoming-webhooks#getting-started):

1. Create a Slack app. A Slack app behaves like a technical user within your workspace.
2. Enable incoming webhooks in your app.
3. Create a new incoming webhook. You will receive the webhook URL.
4. Use the webhook URL to send messages via HTTP POST.

After you completed the steps you will see your app and the configured webhook in the [Slack app overview page](https://api.slack.com/apps). It might look like this.

![slack app](https://thepracticaldev.s3.amazonaws.com/i/758gv2dii97hq6l2761n.png)

![slack webhook](https://thepracticaldev.s3.amazonaws.com/i/9ke3j9qdmabujyz65igx.png)

## Lambda Function

![lambda architecture](https://thepracticaldev.s3.amazonaws.com/i/m5fmm2vfx2l5aameupy6.png)

### Message Format

We can use the webhook URL to create our Lambda function. The function will receive S3 notifications wrapped inside SNS notifications. Both are sent in JSON format, but the S3 notification is stored in the `.Records.Sns.Message` field as a JSON string and has to be parsed as well. This is an example of an SNS notification wrapper message.

```json
{
    "Records": [
        {
            "EventSource": "aws:sns",
            "EventVersion": "1.0",
            "EventSubscriptionArn": "arn:aws:sns:eu-central-1:195499643157:sns-sqs-upload-topic:c7173bbb-8dda-47f6-9f54-a6aa81f65aac",
            "Sns": {
                "Type": "Notification",
                "MessageId": "10a7c00e-af4b-5d93-9459-93a0604d93f5",
                "TopicArn": "arn:aws:sns:eu-central-1:195499643157:sns-sqs-upload-topic",
                "Subject": "Amazon S3 Notification",
                "Message": "<inner_message>",
                "Timestamp": "2018-06-28T11:55:50.578Z",
                "SignatureVersion": "1",
                "Signature": "sTuBzzioojbez0zGFzdk1DLiCmeby0VuSdBvg0yS6xU+dKOk3U8iFUzbS1ZaNI6oZp+LHhehDziaMkTHQ7qcLBebu9uTI++mGcEhlgz+Ns0Dx3mKXyMTZwEcNtwfHEblJPjHXRsuCQ36RuZjByfI0pc0rsISxdJDr9WElen4U0ltmbzUJVpB22x3ELqciEDRipcpVjZo+V2J8GjdCvKu4uFV6RW3cKDOb91jcPc1vUnv/L6Q1gARIUFTbeUYvLbbIAmOe5PiAT2ZYaAmzHKvGOep/RT+OZOA4F6Ro7pjY0ysFpvvaAp8QKp4Ikj40N9lVKtk24pW+/7OsQMUBGOGoQ==",
                "SigningCertUrl": "https://sns.eu-central-1.amazonaws.com/SimpleNotificationService-ac565b8b1a6c5d002d285f9598aa1d9b.pem",
                "UnsubscribeUrl": "https://sns.eu-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:eu-central-1:195499643157:sns-sqs-upload-topic:c7173bbb-8dda-47f6-9f54-a6aa81f65aac",
                "MessageAttributes": {}
            }
        }
    ]
}
```

Inside the `<inner_message>` part you will find the actual S3 notification, which might look like this:

```json
{
    "Records": [
        {
            "eventVersion": "2.0",
            "eventSource": "aws:s3",
            "awsRegion": "eu-central-1",
            "eventTime": "2018-06-28T11:55:50.528Z",
            "eventName": "ObjectCreated:Put",
            "userIdentity": {
                "principalId": "AWS:AIDAI3EXAMPLEEXAMP"
            },
            "requestParameters": {
                "sourceIPAddress": "xxx.yyy.zzz.qqq"
            },
            "responseElements": {
                "x-amz-request-id": "0A8A0DA78EF73966",
                "x-amz-id-2": "/SD3sDpP1mcDc6pC61573e4DAFSCnYoesZxeETb4MV3PpVgT4ud8sw0dMrnWI9whB3RYhwGo+8A="
            },
            "s3": {
                "s3SchemaVersion": "1.0",
                "configurationId": "tf-s3-topic-20180628113348955100000002",
                "bucket": {
                    "name": "sns-sqs-upload-bucket",
                    "ownerIdentity": {
                        "principalId": "A2OMJ1OL5PYOLU"
                    },
                    "arn": "arn:aws:s3:::sns-sqs-upload-bucket"
                },
                "object": {
                    "key": "3427394.jpeg",
                    "size": 25044,
                    "eTag": "a3cf1dabef657a65a63a270e27312ddc",
                    "sequencer": "005B34CCC64D9E046E"
                }
            }
        }
    ]
}
```

The most interesting part is within the `s3` object which holds information about the S3 bucket and the object that has been uploaded. I'm sure that the [AWS Java SDK](https://aws.amazon.com/sdk-for-java/) has some classes which represent this information but for this blog post I decided to decode the parts that I am interested in manually using [circe](https://circe.github.io/circe/).

### Source Code

The Lambda function will use the same [`RequestStreamHandler`](https://github.com/aws/aws-lambda-java-libs/blob/master/aws-lambda-java-core/src/main/java/com/amazonaws/services/lambda/runtime/RequestStreamHandler.java) that we used [before](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61). This class is part of the [`aws-lambda-java-libs`](https://github.com/aws/aws-lambda-java-libs) and provides only raw input and output streams, leaving the serialization and deserialization to us. Here's the source code:

```scala
class Handler extends RequestStreamHandler {
  override def handleRequest(input: InputStream,
                             output: OutputStream,
                             context: Context): Unit = {
    val hookUrl = System.getenv("hook_url")
    val inputJsonString = Source.fromInputStream(input).mkString
    val processingResult = for {
      notification <- decodeNotification(inputJsonString)
      message <- decodeMessage(notification)
    } yield {
      implicit val backend = HttpURLConnectionBackend()
      sttp
        .post(Uri(java.net.URI.create(hookUrl)))
        .contentType("application/json")
        .body(SlackMessage(messageText(notification, message)).asJson.noSpaces)
        .send()
    }

    val out = new PrintStream(output)
    processingResult match {
      case Right(response) => out.print(s"Response from hook: ${response.code}")
      case Left(error)     => out.print(s"Failed: $error")
    }
    out.close()
  }
}
```

First we are extracting the hook URL from the `$hook_url` environment variable. Error handling and logging is omitted for readability reasons at this moment. Then we are reading the notification JSON string from the input stream and parsing it in two steps because I was too lazy to provide a custom deserialization format.

If parsing was successful we are sending an HTTP POST request to the hook URL. Slack expects the body to be a JSON having at least a `text` field. `SlackMessage` is a case class that captures this. In our case we will construct a message text based on the S3 bucket and object key. To send our message to the channel we would have to use the following body:

```scala
s"""
{
  "text": "Someone uploaded ${s3.`object`.key} to ${s3.bucket.name}."
}
"""
```

The Lambda function does not really have to return anything but we are going to return a readable string message indicating whether the hook responded or if parsing of the SNS message failed.

Now we only have to package the Lambda handler in a fat `jar` file using the [`sbt-assembly`](https://github.com/sbt/sbt-assembly) plugin again. After running `sbt assembly` the artifact can be uploaded to AWS Lambda using Terraform.

### Terraform

Before we can create the Lambda function we have to create an IAM role for the execution. Then we can create the Lambda function itself and also setup the permissions for the SNS notification to be able to invoke our Lambda function. First the IAM role:

```conf
resource "aws_iam_role" "lambda_exec" {
  name = "sns-sqs-slack-lambda"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}
```

To make the Terraform code a bit more reusable we will introduce two variables: The artifact version and the Slack webhook URL. I will pass the webhook URL through my local [`terraform.tfvars`](https://www.terraform.io/intro/getting-started/variables.html#from-a-file) file.

```conf
variable "slack_lambda_version" {
  type = "string"
  default = "0.1-SNAPSHOT"
}

locals {
  slack_lambda_artifact = "../slack/target/scala-2.12/sns-sqs-chat-assembly-${var.slack_lambda_version}.jar"
}

variable "slack_hook_url" {
  type = "string"
}
```

Now we can define the Lambda function resource. This time we will not choose an S3 artifact but upload our assembled archive directly. It is useful to also specify the `source_code_hash` in order to trigger updates if the file has changed although the name did not. You might think about including the commit SHA and whether the repository was clean inside the filename to have more transparency though.

We will also assign 1 GB of RAM just because AWS Lambda assigns CPU corresponding to memory and JVM class loading takes a lot of CPU for the initial request so we need that computing power 🔥. At this moment we are also passing the Slack URL as an environment variable.

```conf
resource "aws_lambda_function" "slack" {
  function_name = "sns-sqs-upload-slack"
  filename = "${local.slack_lambda_artifact}"
  source_code_hash = "${base64sha256(file(local.slack_lambda_artifact))}"
  handler = "de.frosner.aws.slack.Handler"
  runtime = "java8"
  role = "${aws_iam_role.lambda_exec.arn}"
  memory_size = 1024
  timeout = 5

  environment {
    variables {
      hook_url = "${var.slack_hook_url}"
    }
  }
}
```

Finally we have to create a permission which allows SNS messages to trigger the Lambda function.

```conf
resource "aws_lambda_permission" "sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.slack.function_name}"
  principal     = "sns.amazonaws.com"
  source_arn = "${aws_sns_topic.upload.arn}"
}
```

## Lambda Subscription

![lambda sns subscription architecture](https://thepracticaldev.s3.amazonaws.com/i/h4p2qrbppnn2232y10t5.png)

The only link that is missing to complete our pipeline is the subscription of the Lambda function to the SNS topic. This is basically the same as the SQS subscription but with the `lambda` protocol this time.

```conf
resource "aws_sns_topic_subscription" "lambda" {
  topic_arn = "${aws_sns_topic.upload.arn}"
  protocol  = "lambda"
  endpoint  = "${aws_lambda_function.slack.arn}"
}
```

## Deployment

Now we can run `terraform apply`. Make sure you executed `sbt assembly` before to have the artifact available for Terraform to upload.

![terraform deployment](https://thepracticaldev.s3.amazonaws.com/i/liuf26qdnav048itbmzj.gif)

# Conclusion

Finally, we are done! That was quite some work. We could have simplified the architecture by sending S3 notifications to our Lambda function directly. But I wanted to demonstrate the fanout pattern, which is also why we introduced the SQS queue which is not used at the moment.

We have seen how it is possible to implement an event processing pipeline with potentially multiple consumers and producers using fully managed building blocks like SNS, SQS, and Lambda. SNS provides pub/sub functionality to decouple producers and consumers, while SQS gives us the ability to process events asynchronously.

Did you ever use SNS or SQS? What is your experience with Amazon MQ or Kinesis and in which cases do you think SQS is suitable? Let me know what you think in the comments.
