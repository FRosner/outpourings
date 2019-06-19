---
title: Resilience Design Patterns: Retry, Fallback, Timeout, Circuit Breaker
published: true
description: The main goal of resilient software is tolerating faults but also failures. Retry, fallback, timeout, and circuit breaker are popular resilience design patterns.
tags: architecture, resilience, microservices, patterns
cover_image: https://thepracticaldev.s3.amazonaws.com/i/43ty7806f1p9i1k1o79s.png
canonical_url: https://blog.codecentric.de/en/2019/06/resilience-design-patterns-retry-fallback-timeout-circuit-breaker/
---

# What is Resilience?

Software is not an end in itself: It supports your business processes and makes customers happy. If software is not running in production it cannot generate value. Productive software however, also has to be correct, reliable, and available.

When it comes to resilience in software design the main goal is build robust components that can tolerate faults within their scope, but also failures of other components they depend on. While techniques such as automatic fail-over or redundancy can make components fault-tolerant, almost every system is distributed nowadays. Even a simple web application can contain a web server, a database, firewalls, proxies, load balancers, and cache servers. Additionally, the network infrastructure on its own consists of many components that there are always failures happening somewhere.

Besides the total failure scenario, services might also take a longer time to respond. In reality it might also happen that they even answer semantically in a wrong way, although their response format is correct. And again, the more components a system has, the more likely it is that something will fail.

Availability is often considered an important quality attribute. It expresses the amount of time a component is actually available, compared to the amount of time the component is supposed to be available. It can be expressed with the following formula:

<img src="https://thepracticaldev.s3.amazonaws.com/i/m9297nxz6snzkhevm09u.png" width="50%">

Traditional approaches aim at increasing the uptime, while modern approaches aim for reduced recovery times and thus downtimes. This is useful because it allows us to deal with failures rather than trying to prevent them at all costs and being unavailable for a long time in case they do happen. Uwe Friedrichsen categorizes [resilience design patterns](https://www.slideshare.net/ufried/patterns-of-resilience) into four categories: *Loose coupling*, *isolation*, *latency control*, and *supervision*.

![](https://thepracticaldev.s3.amazonaws.com/i/qstzssj2v491i412pkss.png)

In this blog post we want to take a look at four patterns from the latency control category: *Retry*, *fallback*, *timeout*, and *circuit breaker*. After a theoretical introduction we will see how these patterns can be applied in practice using Eclipse Vert.x. We are closing the post by discussing alternative implementations and summarizing the findings.

# The Patterns

## Example Scenario

To illustrate the functionality of the patterns we will utilize a very simple example use case. Imagine a payment service as part of a shopping platform. When a client wants to make a payment, the payment service should make sure there is no fraudulent intention. To do that it asks a fraud check service.

In this case our services offer HTTP based interfaces. To check the transaction, and the payment service sends an HTTP request to the fraud check service. If everything works well, there will be a 200 response with the boolean indicating whether the transaction is fraudulent or not. But what if the fraud check service is not answering? What if it returns an internal server error (500)?

![](https://thepracticaldev.s3.amazonaws.com/i/43ty7806f1p9i1k1o79s.png)

Let’s take a look at the four concrete patterns to address possible communication issues now. While this is a concrete example, you can imagine any other constellation that involves communication with an unreliable service over an unreliable channel.

## Retry

Whenever we assume that an unexpected response - or no response for that matter - can be fixed by sending the request again, using the retry pattern can help. It is a very simple pattern where failed requests are retried a configurable number of times in case of a failure, before the operation is marked as a failure.

The following animation illustrates the payment service attempting to issue a fraud check. The first request fails due to an internal server error in the fraud check service. The payment service retries the request and receives the answer that the transaction is not fraudulent.

![](https://thepracticaldev.s3.amazonaws.com/i/o00e224x9qf4g100kcax.gif)

Retries can be useful in case of

- Temporary network problems such as packet loss
- Internal errors of the target service, e.g. caused by an outage of a database
- No or slow responses due to a large number of requests towards the target service

Keep in mind however that if the problems are caused by the target service being overloaded, retrying might make those problems even worse. To avoid turning your resilience pattern into a denial of service attack, retry can be combined with other techniques such as exponential backoff or a circuit breaker (see below).

## Fallback

The fallback pattern enables your service to continue the execution in case of a failed request to another service. Instead of aborting the computation because of a missing response, we fill in a fallback value.

The following animation again depicts the payment service issuing a request to the fraud check service. Again, the fraud check service returns an internal server error. This time however we have a fallback in place which assumes that the transaction is not fraudulent.

![](https://thepracticaldev.s3.amazonaws.com/i/7oxihrr3n5k67h5h4szb.gif)

Fallback values are not always possible but can greatly increase your overall resilience if used carefully. In the example above it can be dangerous to fallback to treating the transaction as not fraudulent in case the fraud check service is not available. It even opens up an attack surface for fraudulent transactions attempting to first spam the service and then place the fraudulent transaction.

On the other hand if the fallback is to assume that every transaction is fraudulent, no payment will go through and the fallback is essentially useless. A good compromise might be to fallback to a simple business rule, e.g. simply letting transactions with a reasonable small amount through to have a good balance between risk and not losing customers.

## Timeout

The timeout pattern is pretty straightforward and many HTTP clients have a default timeout configured. The goal is to avoid unbounded waiting times for responses and thus treating every request as failed where no response was received within the timeout.

The animation below shows the payment service waiting for the response from the fraud check service and aborting the operation after the timeout exceeded.

![](https://thepracticaldev.s3.amazonaws.com/i/e0eetjip5m311u9ofpzr.gif)

Timeouts are used in almost every application to avoid requests getting stuck forever. Dealing with timeouts is not trivial however. Imagine an order placement timing out in an online shop. You cannot be sure if the order was placed successfully but the response timed out, if the order creation was still in progress, or the request was never processed. If you combine the timeout with a retry, you might end up with a duplicate order. If you mark the order as failed the customer might think the order didn’t succeed but maybe it did and they will get charged.

Also you want your timeouts to be high enough to allow slower responses to arrive but low enough to stop waiting for a response that is never going to arrive.

## Circuit Breaker

In electronics a circuit breaker is a switch that protects your components from damage through overload. In software, a circuit breaker protects your services from being spammed while already being partly unavailable due to high load.

The [circuit breaker](https://martinfowler.com/bliki/CircuitBreaker.html) pattern was described by Martin Fowler. It can be implemented as a stateful software component that switches between three states: closed (requests can flow freely), open (requests are rejected without being submitted to the remote resource), and half-open (one probe request is allowed to decide whether to close the circuit again). The animation below illustrates a circuit breaker in action.

![](https://thepracticaldev.s3.amazonaws.com/i/u3f6z484i74k0osz5r6z.gif)

The request from the payment service to the fraud check service is passed through the circuit breaker. After two internal server errors the circuit opens and subsequent requests are blocked. After some waiting time the circuit goes to the half-open state. In this state it will allow one request to pass and change back to the open state in case it fails, or to closed in case of success. The next request succeeds so the circuit is closed again.

Circuit breakers are a useful tool, especially when combined with retries, timeouts and fallbacks. Fallbacks can be used not only in case of failures but also if the circuit is open. In the next section we will take a look at a code example with Vert.x written in Kotlin.

# Implementation In Vert.x

In the last section we took a look at different resilience patterns from a theoretical point of view. Now let’s see how you can implement them. The [source code](https://github.com/FRosner/vertx-kotlin-resilience-example) of the example is available on GitHub. We will use Vert.x with Kotlin for this showcase. Other alternatives are discussed in the next section.

Vert.x offers [`CircuitBreaker`](https://vertx.io/docs/vertx-circuit-breaker/java/), a powerful decorator class which supports arbitrary combinations of retry, fallback, timeout, and circuit breaker configurations. You can configure the circuit breaker using the `CircuitBreakerOptions` class as shown below.

```kotlin
val vertx = Vertx.vertx()
val options = circuitBreakerOptionsOf(
    fallbackOnFailure = false,
    maxFailures = 1,
    maxRetries = 2,
    resetTimeout = 5000,
    timeout = 2000
)
val circuitBreaker = CircuitBreaker.create("my-circuit-breaker", vertx, options)
```

In this example we are creating a circuit breaker that retries the operation two times before treating it as failed. After one failure we are opening the circuit which will be half-open again after 5000 ms. Operations time out after 2000 ms. If a fallback is specified it will be called only in case of an open circuit. It is also possible to configure the circuit breaker to call the fallback in case of a failure even if the circuit is closed.

In order to execute a command we need to provide an asynchronous piece of code to execute of type `Handler<Future<T>>` as well as a handler of type `Handler<AsyncResult<T>>` that processes the result. A minimal example that returns `OK` and prints it afterwards looks like this:

```kotlin
circuitBreaker.executeCommand(
    Handler<Future<String>> {
        it.complete("OK")
    },
    Handler {
        println(it)
    }
)
```

When working with [Vert.x in Kotlin](https://blog.codecentric.de/en/2019/02/vert-x-kotlin-coroutines/) you can also pass suspend functions as arguments instead of working with handlers. Please refer to the [`CoroutineHandlerFactory`](https://github.com/FRosner/vertx-kotlin-resilience-example/blob/master/src/main/kotlin/de/frosner/vkre/CoroutineHandlerFactory.kt) class and its usages for more details. In addition to these basic features, the Vert.x circuit breaker module offers the following advanced features:

- **Event bus notifications.** The circuit breaker can publish an event to the event bus on every state change. This is useful if you want to react to those events in some way.
- **Metrics.** The circuit breaker can publish metrics to be consumed by the Hystrix dashboard to visualize the state of your circuit breakers.
- **State change callbacks.** You can configure custom handlers to be invoked when the circuit opens or closes.

# Alternative Implementation Approaches

Not every framework supports resilience design patterns out of the box. Also Vert.x does not support all possible patterns. There are designated projects addressing resilience topics directly, such as [Hystrix](https://github.com/Netflix/Hystrix), [resilience4j](https://github.com/resilience4j/resilience4j), [failsafe](https://github.com/jhalterman/failsafe), and the resilience features of [Istio](https://github.com/istio/istio).

Hystrix has been used in many applications but is no longer under active development. Hystrix, resilience4j, as well as failsafe are directly called from within the application source code. You can integrate it either by implementing interfaces or using annotations, for example.

Istio on the other hand is a service mesh and thus part of the infrastructure rather than the application code. It is used to orchestrate a distributed system of services and implements the concept of a [sidecar](https://docs.microsoft.com/en-us/azure/architecture/patterns/sidecar). Service communication happens through that sidecar, which is a dedicated process alongside the service process. The sidecar can then handle mechanisms such as retry.

The advantage of a sidecar approach is that you do not mix business logic with resilience logic. You can replace the sidecar technology without touching too much of the application code. Additionally, you can easily modify and adapt the sidecar configuration without redeploying the service. The disadvantage lies in the disability to use implement specific patterns such the [bulkhead](https://docs.microsoft.com/en-us/azure/architecture/patterns/bulkhead) pattern for thread pool isolation. Additionally, patterns like fallback values heavily depend on your business logic. It might also be easier to extend your existing code base rather than adding a new infrastructure component.

# Summary

In this post we have seen how loose coupling, isolation, latency control and supervision can positively affect system resilience. The retry pattern enables dealing with communication errors that can be corrected by attempting them multiple times. The fallback pattern helps resolving communication failures locally. The timeout pattern provides an upper bound to latency. The circuit breaker addresses the problem of accidental denial of service attacks due to retries and fast fallbacks in case of persisting communication errors.

Frameworks like Vert.x provide some resilience patterns out of the box. There are also dedicated resilience libraries which can be used with any framework. Services meshes on the other hand exist as an option to introduce resilience patterns on an infrastructure level. As always there is no one-size-fits-all solution and your team should figure out what works best for them.
