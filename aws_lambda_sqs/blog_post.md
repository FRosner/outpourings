---
title: Understanding the AWS Lambda SQS Integration
published: true
description: But how does the Lambda SQS integration work exactly? How do the different configuration parameters impact the behaviour of your integration?
tags: aws, cloud, serverless, devops
cover_image: https://thepracticaldev.s3.amazonaws.com/i/xwm4343gq6vuoxm0z1q0.png
---

# Introduction

AWS offers different components for building scalable, reliable, and secure cloud applications. Lambda is a service to execute code on demand. A Lambda function can be invoked in many different ways, e.g. by an API Gateway as part of a "serverless" back-end. In the scope of event processing, Lambda can be used in combination with event sources such as SQS (queue), SNS (pub/sub), or Kinesis streams. In this post we want to focus on the Lambda SQS integration.

SQS is a managed, distributed message queue. As SQS itself is not a message broker, consumers have to poll proactively in order to receive new messages. Luckily, AWS handles the polling work for you if you configure an SQS event source for your Lambda function.

But how does the Lambda SQS integration work exactly? How do the different configuration parameters such as the polling strategy, visibility timeout, Lambda timeout, and concurrency limits impact the behaviour of your integration? This is what we are going to look at now. The remainder of the post is structured as follows.

First, we will look at the relevant configuration details of Lambda, SQS, and the event source mapping with respect to the Lambda SQS integration. The next section looks at the integration in more detail, discussing how it is implemented and which situations to look out for when using it. We are closing the post by summarizing the main findings.

# Configuration

## Lambda

A [Lambda function](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-lambda-function.html) has many different configuration parameters. We are going to focus on the following three, as they are have significant impact on way the function works as an event processor: dead letter configuration, concurrency limit, and function timeout.

The *dead letter configuration* (`DeadLetterConfig`) is an optional parameter which allows you to setup a dead letter queue or topic for your function. Depending on the invocation type, messages that are failed to be processed will be forwarded to the respective resource.

Lambda scales automatically based on the number of concurrent invocations. If you want to limit the maximum concurrency, you can configure a *concurrency limit* (`ReservedConcurrentExecutions`). It is called reserved executions because it also reserves a respective share from the AWS account wide concurrency limit of Lambda.

Last but not least, the *function timeout* plays an important role. To avoid never-ending functions, AWS terminates every function exceeding its configured timeout. If your function cannot tolerate such terminations easily, make sure to set the timeout reasonably high.

## SQS

The [SQS queue](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-sqs-queues.html) configuration properties relevant for this post are the polling strategy and the visibility timeout. There is also the option to enforce an ordering of the queue items by creating a FIFO queue (`FifoQueue`) but when doing that it is no longer possible to use the queue as an event source for Lambda.

The *polling strategy* can be configured through the `ReceiveMessageWaitTimeSeconds` parameter. Setting the parameter to `0` corresponds to *short polling*, while any value > `0` corresponds to *long polling*. When a client makes a poll request to an SQS queue with short polling, the API will respond without asking all available queue partitions. This might result and an empty response although the queue is not empty. As the set of partitions queried differs with every request you are guaranteed to hit each partition eventually. Long polling on the other hand asks all servers and awaits their answer for the configured amount of time.

If your goal is to have low latency and you do not mind paying for a huge amount of API requests, you can go with short polling. I recommend long polling (e.g. setting `ReceiveMessageWaitTimeSeconds` to `2`) if you can bear the increased latency however, as it saves cost.

The second important parameter is the *visibility timeout* (`VisibilityTimeout`). As SQS does not know if a consumer has finished consuming a message it never deletes messages by itself. Instead, it is within the consumers responsibility to delete the message from the queue once it has been processed successfully. To avoid messages being consumed by multiple consumers need to choose a reasonable value for the visibility timeout.

A visibility timeout of 30 seconds means that whenever a message has been read by a consumer, all subsequent `ReceiveMessage` requests are not going to return that message for 30 seconds. If the consumer did not delete the message within the visibility timeout, it will become visible again to other consumers.

## Event Source Mapping

When setting up the [event source mapping](https://docs.aws.amazon.com/en_us/AWSCloudFormation/latest/UserGuide/aws-resource-lambda-eventsourcemapping.html) there is not much to configure. One property that might be relevant when it comes to retry behaviour is the *batch size* (`BatchSize`). The SQS API allows to retrieve multiple messages in one request and AWS will invoke your Lambda with a batch of one to ten messages depending on the configured batch size.

Now that we set the theoretical foundations of Lambda, SQS, and the event source mapping, let's look at the whole setup in action.

# Lambda SQS Integration Details

## Architecture and Flow

The following diagram illustrates a successful message processing involving all three components as introduced in the previous section: an SQS queue, a Lambda function, and an event source mapping.

![SQS lambda integration architecture](https://thepracticaldev.s3.amazonaws.com/i/xwm4343gq6vuoxm0z1q0.png)

First, the event source mapping polls the queue by calling the [`sqs:ReceiveMessage`](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_ReceiveMessage.html) action with the parameters specified in the event source mapping configuration. SQS will immediately mark all retrieved messages as in-flight until they are either deleted or the visibility timeout is reached.

Next, the event source mapping component invokes the Lambda function synchronously using the [`lambda:InvokeFunction`](https://docs.aws.amazon.com/de_de/lambda/latest/dg/API_Invoke.html) action, wrapping the payload inside an [SQS event](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html). After the call has returned, the event source mapping component sends a [`sqs:DeleteMessageBatch`](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_DeleteMessageBatch.html) request to SQS and the processing flow is finished.

In case of an error within the Lambda function, the event source mapping component will do nothing and SQS makes the message visible again after the visibility timeout is exceeded.

## Idempotency Matters

The above flow is convenient and AWS handles polling and message deletion for you. There are some cases however in which unexpected things can happen. Imagine the following chain of events:

1. A new message arrives on the queue.
2. AWS invokes the Lambda function with the new message and makes it invisible.
3. The Lambda function takes a long time to process the message. In the meantime, the visibility timeout is exceeded.
4. AWS invokes the Lambda function again with the same message.
5. Now the first Lambda execution finishes, processing the message once.
6. Now the second Lambda execution finishes, effectively processing the message a second time.

This can only occur if the Lambda execution time exceeds the visibility timeout. Note that setting the visibility timeout to the same value as the function timeout does not help, as there is a lag between polling the queue and invoking the Lambda. This lag might be increased in case the Lambda invocation gets throttled or times out because Lambda is not available.

To avoid that situation AWS recommends to configure the visibility timeout to be six times the function timeout. This means however, that for a 5 minute Lambda, failed executions will keep the message invisible for half an hour.

Another mitigation strategy is to make all operations idempotent such that you don't mind accidental duplicate messages. This is anyway a good idea because SQS only guarantees at-least-once delivery. One of the SQS partitions holding a replica of your message might be unavailable when you receive or delete a message. In this case that exact replica is not deleted or marked invisible and as soon as this server comes up you might see the message again.

## Scaling and Throttling Behaviour

SQS supports a practically unlimited amount of throughput. Lambda scales automatically up to a certain limit (1000 concurrent executions for standard accounts). The event source mapping component however is neither aware of the SQS, nor the Lambda scaling behaviour. It will start polling the queue with 5 threads in parallel, invoking the Lambda function for each batch.

As soon as your Lambda function reaches its concurrency limit the invocations will be throttled. In a small experiment we submitted 100 messages to a queue, each message taking approximately 20 seconds to be processed, and the Lambda function having a concurrency limit of 5. During that time we observed approximately 200 throttles of the Lambda API.

I believe the integration between SQS and Lambda is done in a very simple manner which doesn't require the event source mapping component to have any internal knowledge of the respective components. It uses only a combination of standard APIs, retries, and timeouts.

# Summary

In this post we have seen how to use an event source mapping to make Lambda consume SQS messages. There are however a few configuration properties to look out for, such as

- the SQS polling strategy and the visibility timeout,
- the Lambda dead letter configuration, function timeout and concurrency limit, as well as
- the batch size of the event source mapping.

Even if configured correctly, SQS only guarantees at-least-once delivery and thus your Lambda function might get invoked multiple times with the same message. You should design your system to be idempotent such that duplicate messages do not matter.
