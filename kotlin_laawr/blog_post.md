---
title: Let's Also Apply Run With Kotlin Scope Functions
published: true
description: In Kotlin, scope functions allow to execute a function, i.e. a block of code, in the context of an object. They enable you to structure your code differently, increasing readability.
tags: kotlin, java, functional
cover_image: https://thepracticaldev.s3.amazonaws.com/i/qv2s51d0io4jxijq0nx8.png
canonical_url: https://blog.codecentric.de/en/2019/07/lets-also-apply-run-with-kotlin-scope-functions
---

# Scope Functions

In Kotlin, scope functions allow to execute a function, i.e. a block of code, in the context of an object. The object is then accessible in that temporary scope without using the name. Although whatever you do with scope functions can be done without, they enable you to structure your code differently. Using them can increase readability and make your code more concise.

The Kotlin standard library offers four different types of scope functions which can be categorized by the way they refer to the context object and the value they return. A scope function either refers to the context object as a *function argument* or a *function receiver*. The return value of a scope function is either the *function result* or the *context object*.

The available functions are `let`, `also`, `apply`, `run`, and `with`. The following table summarizes the characteristics of each function based on the way the context object can be accessed and the return type as described above:

| | Context Object As Function Argument | Context Object As Function Receiver |
|--------------------------|-----------------------------------|-----------------------------------|
| Returns: Function Result | `let`                             | `run`, `with`                     |
| Returns: Context Object  | `also`                            | `apply`                           |

The difference between `run` and `with` lies only in the way they are called. While all other scope functions are implemented as extension functions, `with` is a regular function.

Now that I've mentioned concepts such as function receivers and extension functions it makes sense to briefly explain them before we move on into the detailed descriptions of the scope functions. If you are already familiar with function receivers and extension functions in Kotlin you can skip the next section.

# Function Arguments, Extension Functions, Receivers

Kotlin allows treating functions as values. This means you can pass *functions as arguments* to other functions. Using the `::` operator you can convert a method to a function value. To increase readability, the last function argument can be placed outside of the argument list.

The following example illustrates how to do that by defining a higher order function `combine`, which takes a function argument `f`. We're invoking it with the `plus` method from the `Int` class and with an anonymous function literal both within the and outside of the argument list:

```kotlin
// Apply function argument f to integers a and b
fun combine(a: Int, b: Int, f: (Int, Int) -> Int): Int = f(a, b)

// Using the plus method as a function value
combine(1, 2, Int::plus)

// Passing a function literal
combine(1, 2, { a, b ->
    val x = a + b
    x + 100
})

// Passing it outside of the argument list
combine(1, 2) { a, b ->
    val x = a + b
    x + 100
}
```

*Extension functions* are a way to extend existing classes or interfaces you do not necessarily have under your control. Defining an extension function on a class lets you call this method on instances of that class as if it was part of the original class definition.

The following example defines an extension function on `Int` to return the absolute value:

```kotlin
fun Int.abs() = if (this < 0) -this else this

(-5).abs() // 5
```

Function literals with *receiver* are similar to extension functions as the receiver object is accessible within the function through `this`. The following code snippet defines the extension function from before but this time as a function literal with receiver:

```kotlin
val abs: Int.() -> Int = { if (this < 0) -this else this }

(-5).abs() // 5
```

A common use case for function literals with receivers are [type-safe builders](https://kotlinlang.org/docs/reference/type-safe-builders.html). Now that we have covered the basics let's look at the five scope functions individually.

# Let, Also, Apply, Run, With

## Let

The `let` scope function makes the context object available as a function argument and returns the function result. A typical use case is applying null-safe transformations to values.

```kotlin
val x: Int? = null

// null-safe transformation without let
val y1 = if (x != null) x + 1 else null
val y2 = if (y1 != null) y1 / 2 else null

// null-safe transformation with let
val z1 = x?.let { it + 1 }
val z2 = z1?.let { it / 2 }
```

## Also

The `apply` scope function makes the context object available as a function argument and returns the context object. This can be used when you are computing a return value inside a function and then want to apply some side effect to it before you return it.

```kotlin
// assign, print, return
fun computeNormal(): String {
    val result = "result"
    println(result)
    return result
}

// return and also print
fun computeAlso(): String =
    "result".also(::println)
```

## Apply

The `apply` scope function makes the context object available as a receiver and returns the context object. This makes it very useful for "ad-hoc builders" of mutable objects, such as Java Beans.

```java
// Java Bean representing a person
public class PersonBean {
    private String firstName;
    private String lastName;
    public void setFirstName(String firstName) {
        this.firstName = firstName;
    }
    public String getFirstName() {
        return firstName;
    }
    public void setLastName(String lastName) {
        this.lastName = lastName;
    }
    public String getLastName() {
        return lastName;
    }
}
```

```kotlin
// Initialization the traditional way
val p1 = PersonBean()
p1.firstName = "Frank"
p1.lastName = "Rosner"

// Initialization using apply
val p2 = PersonBean().apply {
    firstName = "Frank"
    lastName = "Rosner"
}
```

## Run and With

The `run` scope function makes the context object available as a receiver and returns the function result. It can be used with or without a receiver. When using it without a receiver you can compute an expression using locally scoped variables. By using a receiver, `run` can be called on any object, e.g. a connection object.

```kotlin
// compute result as block result
val result = run {
    val x = 5
    val y = x + 3
    y - 4
}

// compute result with receiver
val result2 = "text".run {
    val tail = substring(1)
    tail.toUpperCase()
}
```

The `with` function works exactly as `run` but is implemented as a regular function and not an extension function.

```kotlin
val result3 = with("text") {
    val tail = substring(1)
    tail.toUpperCase()
}
```

# Summary

In this post we learned about the scope functions `let`, `also`, `apply`, `run`, and `with`. They differ in the way they refer to the context object and the value they return. Combined with the concepts of function arguments, extension functions and receivers, scope functions are a useful tool to produce more readable code.

What do you think about scope functions? Have you ever used them in one of your projects? Can you remember which one to use when? Let me know your thoughts in the comments!

# References

- [Scope functions documentation](https://kotlinlang.org/docs/reference/scope-functions.html)
- [Functions with receiver documentation](https://kotlinlang.org/docs/reference/lambdas.html?_ga=2.65237611.45512856.1561714615-1060180565.1544467616#higher-order-functions-and-lambdas)
- [Extension functions documentation](https://kotlinlang.org/docs/reference/extensions.html)
