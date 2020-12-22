---
title: Vert.x Kotlin Coroutines
published: true
description: Vert.x is an event-driven application framework. Coroutines are a nice way to compose asynchronous computations. How do these two work together?
tags: kotlin, vertx, concurrency, webdev
cover_image: https://thepracticaldev.s3.amazonaws.com/i/wc4h0bqttknxgi6jjqab.png
canonical_url: https://blog.codecentric.de/en/2019/02/vert-x-kotlin-coroutines/
---

# Vert.x

[Eclipse Vert.x](https://vertx.io/) is an event-driven application framework that runs on the JVM. Architecturally it is very similar to Node.js, having a single-threaded event loop at its core and it heavily relies on non-blocking operations in order to be scalable. All functions of the Vert.x APIs are asynchronous and you can compose them based on callback handlers.

The following code snippet creates an HTTP server and as soon as it listens on a random port we are sending a request, printing the response after it arrives.

```kotlin
vertx.createHttpServer().listen {
    if (it.succeeded()) {
        val server = it.result()
        WebClient.create(vertx).get(server.actualPort(), "localhost", "").send {
            if (it.succeeded()) {
                val response = it.result()
                println(response.bodyAsString())
            }
        }
    }
}
```

Callback composition however can be very tedious (aka callback hell). Java developers are often utilizing [Vert.x RxJava](https://vertx.io/docs/vertx-rx/java/) to compose asynchronous and event based programs using observable sequences. When using Vert.x with Kotlin we have another alternative for asynchronous composition: Kotlin coroutines. Below you will find the same code as before but written with coroutines rather than callback handlers:

```kotlin
val server = vertx.createHttpServer().listenAwait()
val response = WebClient.create(vertx)
    .get(server.actualPort(), "localhost", "").sendAwait()
println(response.bodyAsString())
```

The next section is going to give a quick introduction into Kotlin coroutines, independently of Vert.x. Afterwards we will see how coroutines integrate into the Vert.x APIs and how we can use that. We will close the post by summarizing the main findings.

# Coroutines

## Coroutine Basics

Concurrent programs are hard to reason about. Coroutines are a powerful tool for writing concurrent code. Although other models like promises or callbacks exist they can be quite difficult to understand if they are nested deeply. With coroutines you can write your asynchronous code as if it was synchronous and abstract away parts of the concurrency. Let's look at the "Hello World" example in Kotlin provided by the [official documentation](https://kotlinlang.org/docs/reference/coroutines/basics.html):

```kotlin
import kotlinx.coroutines.*

fun main() {
    GlobalScope.launch { // launch new coroutine in background and continue
        delay(1000L) // non-blocking delay for 1 second (default time unit is ms)
        println("World!") // print after delay
    }
    println("Hello,") // main thread continues while coroutine is delayed
    Thread.sleep(2000L) // block main thread for 2 seconds to keep JVM alive
}
```

This program will first print `Hello,` and then `World!`. The coroutine is launched asynchronously but then delayed for 1 second. The main function continues and immediately prints `Hello,`. It then puts the main thread to sleep so we give the coroutine some time to finish.

That seems nice but how is that different or better than using good old threads? And how does that help to avoid callback hell? First, let's do a quick dive into the anatomy of a coroutine and how they are executed.

## The Anatomy of a Coroutine

Coroutines behave similar to threads logically but they are implemented differently. In fact a single thread can potentially run thousands of coroutines. This is possible because coroutines can *suspend* their execution, allowing the running thread to move to another coroutine and come back later. This is useful for operations that are waiting for I/O, e.g. network or file access.

Coroutines are implemented as a library rather than a language feature of Kotlin. Only the `suspend` keyword which is used to define suspending functions is part of the language. This enables us to switch to a different implementation for execution if required.

Coroutines can only be launched when there is a [`CoroutineScope`](https://kotlin.github.io/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/coroutine-scope.html) available. The scope provides methods for launching coroutines, as well as an instance of a coroutine context. Coroutines always execute within a [`CoroutineContext`](https://kotlinlang.org/api/latest/jvm/stdlib/kotlin.coroutines/-coroutine-context/), which contains a [`CoroutineDispatcher`](https://kotlin.github.io/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-coroutine-dispatcher/index.html). The dispatcher is managing the thread or thread pool which executes the coroutines. By default a coroutine will use the context available within the current scope.

## Why Coroutines Are Great

Since the rise of concurrent applications programmers are looking for abstractions that enable you to write concurrent code in a concise and understandable way. Common approaches are threads, callbacks, and futures.

Threads are expensive to create and context switching costs a lot of overhead. Callbacks might produce a Christmas tree of curly braces in your code if chained together. Futures are a nice abstraction in my opinion but require good language support (which also heavily depends on the language or library you are using) and can be difficult to grasp if you are not familiar with functional programming.

In the beginning I mentioned that coroutines allow you to write asynchronous code that is as easy to read as synchronous code. What does that mean? Let's look at a simple example:

```kotlin
fun placeOrder(userData: UserData, orderData: OrderData): Order {
    val user = createUser(userData) // synchronous call to user service
    val order = createOrder(user, orderData) // synchronous call to order service
    return order
}

fun createUser(userData: UserData): User { ... }
fun createOrder(user: User, orderData: OrderData): Order { ... }
```

This code places an order of a new shop user by first creating a user by calling the user service and then placing an order for the user. `createUser` and `createOrder` are blocking operations and will block the executing thread until they are complete. Most likely they will involve some sort of I/O.

Now if we use a non-blocking library to perform the I/O we can suspend the computation until the I/O is finished and work on something else in the meantime:

```kotlin
suspend fun placeOrder(userData: UserData, orderData: OrderData): Order {
    val user = createUser(userData) // asynchronous call to user service
    val order = createOrder(user, orderData) // asynchronous call to order service
    return order
}

suspend fun createUser(userData: UserData): User { ... }
suspend fun createOrder(user: User, orderData: OrderData): Order { ... }
```

At some point we have to provide a coroutine context, e.g. by wrapping the `placeOrder` function inside a coroutine scope. However we did not have to actually modify the structure of the code. We only add `suspend` keywords or wrap a function inside `launch` or similar functions and that's it.

It is important to note the difference between blocking (e.g. `Thread.sleep`) and non-blocking (e.g. `delay`) operations. If your underlying functions are blocking, the coroutine will not suspend but instead block the thread it is currently executed in. But what if your non-blocking library is not written with coroutines in mind? Vert.x core API is non-blocking but heavily relies on callback handlers. In the next section we will look at how we can convert the callback API into a coroutine friendly one with just a thin layer on top.

# Vert.x Kotlin Coroutines

The [`vertx-lang-kotlin-coroutines`](https://mvnrepository.com/artifact/io.vertx/vertx-lang-kotlin-coroutines) package mostly consists of automatically generated code that wraps the callback handler based Vert.x core API inside `suspend` functions so they are easy to use within coroutines.

The `HttpServer` class from the HTTP module provides a `listen` method to start the server. In Vert.x all operations are non-blocking so you will have to provide a callback handler to make sure you get the server once it is started. This is the signature of the method:

```kotlin
fun listen(port: Int, host: String, listenHandler: Handler<AsyncResult<HttpServer>>): HttpServer
```

What we would like to have, however, is a function like this:

```kotlin
suspend fun HttpServer.listenAwait(port: Int, host: String): HttpServer
```

And this is where the Vert.x coroutines package comes into play. It converts any function that requires a handler (e.g. `listen`) into a suspending function (e.g. `listenAwait`) using this helper method:

```kotlin
suspend fun <T> awaitEvent(block: (h: Handler<T>) -> Unit): T {
  return suspendCancellableCoroutine { cont: CancellableContinuation<T> ->
    try {
      block.invoke(Handler { t ->
        cont.resume(t)
      })
    } catch (e: Exception) {
      cont.resumeWithException(e)
    }
  }
}
```

It takes the `block` of code that requires a handler and turns it into a coroutine. The [`suspendCancellableCoroutine`](https://kotlin.github.io/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/suspend-cancellable-coroutine.html) function is provided by the core library of Kotlin coroutines. It wraps the given code into a coroutine and suspends it immediately. You can then resume or cancel it manually by accessing the `cont: CancellableContinuation<T>` object. We then simply resume as soon as the handler has returned a value and return this value from the function. In case the handler fails we resume with an exception.

The following animation illustrates how a Vert.x web server would handle multiple requests using coroutine handlers that use a non-blocking database connection. On every method involving database access the handler function suspends and allows other handlers to occupy the thread.

![Coroutine animation](https://thepracticaldev.s3.amazonaws.com/i/0hdemifde04qnzaodtoi.gif)

# Summary

In this post I showed you how to compose asynchronous functions using coroutines. Coroutines are a nice alternative to callback based composition that are available out of the box in Kotlin. Thanks to the Vert.x Kotlin coroutines integration you can use coroutines in Vert.x as well.

Have you used coroutines before, maybe in another language? Have you used Vert.x and if so, which composition style do you prefer? Let me know your thoughts in the comments.
