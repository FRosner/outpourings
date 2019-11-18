---
title: Message Pact - Contract Testing In Event-Driven Applications
published: true
description: In this blog post we are describing how to use Pact to test message passing contracts.
tags: pact, tdd, kotlin, microservices
cover_image: https://thepracticaldev.s3.amazonaws.com/i/t140apybp9obmvlws17b.png
canonical_url: https://blog.codecentric.de/2019/11/message-pact-contract-testing-in-event-driven-applications/
series: Pact
---

# Introduction

In the [previous blog post](https://dev.to/frosnerd/consumer-driven-contract-testing-with-pact-1a57) we introduced contract testing with Pact as an alternative to end-to-end tests when developing distributed applications. Pact works great for interactions between services that follow a request-response pattern, for example when using HTTP. However, not all communication follows the request-response pattern.

Consider event-driven architectures, where communication is typically asynchronous. Events are emitted and services can subscribe to them. Nevertheless every consumer of such an event has an implicit contract with the provider in terms of what information an event contains. Luckily, Pact also provides functionality to implement contract testing in event-driven architectures.

In this blog post we are describing how to use Pact to test message passing contracts. First we are going to look at the message Pact specification and see how interactions differ compared to the known request-response format. Then we are briefly introducing our example scenario that will be used throughout the post. The following section explains how to write consumer tests for message pacts, followed by a section about the respective provider tests. Afterwards we are discussing the importance of backwards compatibility and possible gotchas when relying on Pact to check if you are safe to deploy a new consumer version. The next section discusses the problem that arises when using message Pact if your messages are commands rather than events, and proposes a solution. We are closing the post by summarizing the main findings.

# Message Pact Specification

[Pact Specification 3.0](https://github.com/pact-foundation/pact-specification/tree/version-3#introduces-messages-for-services-that-communicate-via-event-streams-and-message-queues) includes message passing contracts. In contrast to the request-response interactions, a message interaction only contains a single JSON object representing the message.

The provider initiates the interaction by publishing a message. All consumers will read and process the message accordingly. The Pact specification is independent of the transmission medium. Messages could be transmitted using publish-subscribe message brokers, queues, or logs, for example.
# Example Scenario
Our example project describes three services that exist in a web shop. There is a checkout service which publishes an `OrderPlaced` event after a customer completed the checkout. This message is consumed by two independent services: a fulfillment service and a billing service. The following diagram illustrates the interaction between the three services and a message broker.

![example scenario architecture](https://thepracticaldev.s3.amazonaws.com/i/xja5g3ins2ytzjnr4h7e.png)

The `OrderPlaced` events are serialized into JSON and look like this:

```json
{
  "items": [
    {
      "price": 1295,
      "name": "A Teddy Bear"
    }
  ],
  "customerId": "133"
}
```

The fulfillment service is only interested in the customer ID to know where to ship to, as well as the items that need to be included into the package. The billing service on the other hand is only interested in the total price in order to charge the customer.

All code examples are written in Kotlin and you can find the source code of the complete [example project on GitHub](https://github.com/rafaroca/pact-msg/).
# Consumer Tests

As Pact is consumer-driven by design, let’s look at an example of a message consumer test first. The consumer examples make use of the [JVM Consumer DSL](https://github.com/DiUS/pact-jvm/tree/master/consumer/pact-jvm-consumer-java8) to describe the message format and provide example data.

The fulfillment service would define a message format like so

```kotlin
val fulfillmentJsonBody = newJsonBody { o ->
    o.stringType("customerId", "230542")
    o.eachLike("items") { items ->
        items.stringType("name", "Googly Eyes")
    }
}.build()
```

Note that the item price is not part of this contract. The message format of the billing service relies on the price of the items and the customer ID.

```kotlin
val billingJsonBody = newJsonBody { o ->
    o.stringType("customerId", "230542")
    o.eachLike("items") { items ->
        items.numberType("price", 512)
    }
}.build()
```

This leads to two different interactions about the same message, one by each consuming service. The consumer test of the fulfillment service is outlined in the snippet below.

```kotlin
@ExtendWith(PactConsumerTestExt::class)
class FulfillmentServiceConsumerContractTest {

    @Pact(consumer = "fulfillment-service", provider = "checkout-service")
    fun publishOrderPlaced(builder: MessagePactBuilder): MessagePact =
        builder
            .hasPactWith("checkout-service")
            .expectsToReceive("an order to fulfill")
            .withContent(fulfillmentJsonBody)
 	        .toPact()

    @Test
    @PactTestFor(pactMethod = "publishOrderPlaced")
    fun testPublishOrderPlaced(messages: List<Message>) {
        for (message in messages) {
            assertThat {
                fulfillmentHandler.handleRequest(message.contents!!.valueAsString())
            }.isSuccess()            
        }
    }
}
```

The Pact function defines the message payload and the Pact test function calls the fulfillment handler with the message payload. A message Pact interaction may contain multiple messages by invoking `expectsToReceive().withContent()` more than once. This can be useful to test dependencies between messages but we can safely ignore that for our case. In the following test function we loop over all messages, asserting that the handler is able to process them without failure, thus verifying the interaction on the consumer side.

# Provider Tests

In a true consumer-driven fashion we have proven that our consumer adheres to the contract. Now let's switch over to the provider which needs to verify that it is able to produce the expected messages. The consumer defines provider expectations for each interaction.

```kotlin
@PactVerifyProvider("an order to fulfill")
fun anOrderToFulfill(): String? {
    val checkoutService = CheckoutService()
    val order = Order(
        listOf(
            Item("A secret machine", 1559),
            Item("A riddle", 9990),
            Item("A hidden room", 3330)
        ), "customerId"
    )
    val orderPlacedEvent = checkoutService.placeOrder(order)
    return orderPlacedEvent.toJsonString()
}
```

First we are creating an order with three items and a customer ID. We are then passing it to the `checkoutService` instance that will place the order and return the `OrderPlaced` event. We then need to convert the event to a JSON string that matches the expectations of the consumer.

As the consumer test only contains type matchers, the items and customer number do not have to be exact matches. The item names and prices as well as the count of the items in the list may be different from the example in the contract and still verify correctly.

Given correct provider and consumer tests and a working integration into your development workflow you can safely release new versions of your messages to production. Or can you?

# Backwards Compatibility Matters

One big advantage of using Pact is that you can introduce even backwards incompatible changes in your APIs and avoid accidentally breaking consumers. As soon as all your consumers migrated to the new version you can deploy the changes that is not backwards compatible. But does it work the same way with asynchronous messages?

In event driven architectures it is always possible that old messages are still in the system. Just because a new provider version was put into production does not mean that only messages with the new structure exist. Depending on the message passing technology, messages with an old format might be in flight or could be manually replayed even months after they have been deprecated.

This means that even when using Pact to check for breaking changes in your messages you always need to pay attention to backwards compatibility. One way to address this issue could be to never remove or rename fields in messages, and only adding optional fields. The disadvantage of this approach is that your messages will grow and your providers still have to be able to produce those old messages in order to verify the contract.

Another solution could be to extend the Pact specification to allow marking messages as deprecated. They would only be replayed during the consumer tests but would not have to be verified by the provider. When evolving your message format you can add a new message and mark the old one as deprecated. Unfortunately this will make your contracts grow over time.

To address the growing amount of deprecated messages one can imagine an integration with the message broker or event store that can tell you whether deprecated messages can be safely deleted from the contract if they are no longer in flight or already migrated to the new format in the event store.

# Message Pact and the Command Pattern

In the message Pact specification the provider is defined as a service that emits events in the form of messages. Consumers subscribe to certain events and will process the corresponding messages. This works well when messages are events, just like the `OrderPlaced` event from our example shop.

If we consider a distributed [command pattern](https://en.wikipedia.org/wiki/Command_pattern), however, commands are serialized as messages that asynchronously invoke other services. Commands typically target a service that is known by the invoking component. Instead of a message broker, where multiple services can subscribe, the command is placed into a queue which gets polled regularly by the receiver.

In this scenario treating the message creator as the provider seems counter-intuitive. Instead the message creator is consuming functionality of the command receiver. It is just like the request-response pattern but asynchronous and without a response as there is no back-channel through the queue.

Additionally, if you test commands using message pacts and the command receiver is the consumer, the workflow is not really consumer driven. Thinking of a command as a request without a response, the workflow should be driven by the service sending the command.

Unfortunately you cannot simply swap the roles and everything works fine. The way message Pact tests are implemented, consumers have to process the message and providers have to produce it. This implementation does not fit the command pattern use case. However there is a reasonable workaround possible without extending the Pact specification.

Swapping provider and consumer is possible if you adjust the way you write consumer and provider tests. Consumer tests now compare if the generated message corresponds to the one returned by the Pact testing framework, instead of checking if the message can be consumed.

In the provider test we extract the message from the interaction and return it for verification instead of actually producing a message using our service. The test is now a tautology from the perspective of the Pact testing framework. However, before returning the message we can feed it to our command processor and verify that it can be processed with custom test assertions.

# Summary

In this post we have seen how message Pact can be used to test interactions in event-driven architectures. In the consumer tests we verify that we can process incoming events. The providers on the other hand have to prove that they can produce the expected messages.

Backwards compatibility can be an issue, especially when working with event stores and logs or message queues, as messages can still be in-flight or can be replayed at a later point in time. Consumers still need to be able to process those messages, even if the provider does not publish them anymore.

When your message represents an asynchronous command rather than an event, the message Pact workflow no longer feels consumer-driven. We showed that by switching the roles and adapting the way consumer and provider tests are written, you can still use message Pact to test your command interactions.

Have you used message Pact in before? What were your experiences with the workflow? How many consumers did you implement and which message passing technology did you use? Let us know in the comments!

---

This post was co-authored by [Raffael Stein](https://dev.to/rafaroca)
