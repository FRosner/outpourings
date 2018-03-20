---
title: Microbenchmarking your Scala Code
published: false
description: ???
tags: ???
cover_image: ???
---

# Motivation

![spinner](https://inlviv.in.ua/wp-content/themes/inlviv/images/loading_spinner.gif)

I am sure you recognize this loading spinner icon. I do not know anyone who likes to wait for the computer. However, when writing software I usually favour readability, maintainability, and extensibility over speed. I agree with Donald Knuth that premature optimization usually causes more problems than it solves.

Nevertheless at some point you are going to write code where performance matters, or at least bad performance hurts. In this situation it might be useful to look at the performance characteristics of your code. I personally like to combine two approaches:

- Complexity analysis
- Runtime benchmarks

In this blog post I want to focus on runtime benchmarks only, specifically microbenchmarking. The next section is going to set a few theoretical foundations. Afterwards we are going to look at [ScalaMeter](https://github.com/scalameter/scalameter), a tool for automated performance testing in Scala. The last section will contain a few examples, comparing the runtime performance of different implementations. The examples will be written in Scala and related to the Scala programming language but should be understandable for anyone with a bit of functional programming knowledge.

If you want to learn more about how to analyze the complexity of your algorithms, I can recommend the amazing book "Introduction to Algorithms" [1].

# What is Microbenchmarking

In computing, a benchmark is the act of running a computer program, a set of programs, or other operations, in order to assess the relative performance of an object, normally by running a number of standard tests and trials against it. [2]

In bechmarking there are different granularity levels, similar to system tests, integration tests, and unit tests in functional testing. *Microbenchmarking* typically refers to isolated benchmarks of individual methods, e.g. API calls.

Similar to unit tests, having automated microbenchmarks cannot give you any guarantees. The results heavily depend on the selected input and interaction effects between different components of your architecture are not taken into consideration. Nevertheless they are a useful tool to compare the relative performance of different implementations. They can also be used for regression testing.

# ScalaMeter

"ScalaMeter is a microbenchmarking and performance regression testing framework for the JVM platform that allows expressing performance tests in a way which is both simple and concise." [3]

A simple benchmark looks like this: [4]

```scala
import org.scalameter.api._

object RangeBenchmark
extends Bench.LocalTime {
  val sizes = Gen.range("size")(300000, 1500000, 300000)

  val ranges = for {
    size <- sizes
  } yield 0 until size

  performance of "Range" in {
    measure method "map" in {
      using(ranges) in {
        r => r.map(_ + 1)
      }
    }
  }
}
```

It generates integer ranges from 0 to 300.000, 600.000, 900.000, 1.200.000, and 1.500.000 respectively. It then measures the run time of the map operation on these ranges and generates the following output:

```
Parameters(size -> 300000):  1.653809 ms
Parameters(size -> 600000):  3.282649 ms
Parameters(size -> 900000):  4.939347 ms
Parameters(size -> 1200000): 6.492767 ms
Parameters(size -> 1500000): 8.148826 ms
```

ScalaMeter provides a highly configurable testing framework with default configuration for different standard use cases from quick console reporting all the way to sophisticated regression testing with HTML reporting. I find the following features especially useful:

- Concise and readable DSL for data generation and test specification
- Configurable execution (e.g. separate JVM, warm-up runs, measured runs)
- Configurable measurements and aggregations (ignoring GC, outlier elimination, mean, median, ...)
- Configurable reporting (text, HTML, logging, charts, DSV, ...)
- Configurable persistence (Java or JSON serialization)

In the next section we are going to look at some experiments where I used ScalaMeter to perform the measurements.

# Example Experiments

In this section we are going to look at three experiments:

1. How do chained map operations perform compared to a single combined map operation?
2. How do different collections perform when being sorted? How does the Scala sort implementation perform compared to the native Java one?
3. When building up a collection, how does the performance differ when using a builder vs. concatenating?

All experiments are performed using ScalaMeter 0.9 and Scala 2.12.4. My computer has a 2016 3,3 GHz Intel Core i7 with 16 GB of RAM. I am using the `Bench.OfflineReport`, which executes the code in a separate JVM and applies an appropriate number of warm-up runs.

## Chained Map Operations

### Motivation

When working with collections in Scala, the `map` operation is quite common. `xs.map(f)` applies the function `f` to every element `x` in `xs` and returns the result. If you have two composable functions `f` and `g` and you want to apply both, you express that either as

- `xs.map(g compose f)`, or
- `xs.map(f).map(g)`

In terms of the result, both operations are equivalent. The memory footprint and runtime however might differ, depending on the implementation of `xs` and `map`. If you are using a strictly evaluated collection, on every `map` call the result will be computed. If the collection is immutable, a new collection will be created with the resulting values.

In this experiment we want to look at the relative runtime performance of both expressions comparing a `List` (strict) and a `SeqView` (lazy).

### Variables

```scala
val strictList = List.iterate(0, 1000000)(_ + 1)
val lazyList = strict.view
val f: Int => Int = _ + 1
val fs = List.fill(10)(f)
val fsAndThen = fs.reduce(_ andThen _)
```

### Experiments

Given both the `strictList` and the `lazyList` as `l`, we perform the following two experiments for both of them. Note that we omit the `force` command here, which is needed to actually trigger the computation of the view.

- `l.map(fsAndThen)`, which applies `f` 10 times in a single `map` operation
- `fs.foldLeft(l)((l, f) => l.map(f))`, which applies `f` one time in each of the 10 `map` operations

### Results

![runtime comparison](https://thepracticaldev.s3.amazonaws.com/i/ynsjgkpj3tr9ct7bvy41.png)
![legend](https://thepracticaldev.s3.amazonaws.com/i/xoyhrcu7267n0jkph5zh.png)

Looking at these results I find three notable observations:

1. On the strict list, the chained map operations took more than three times longer on average than using the single map operation.
2. This effect is not present when using the list view.
3. The performance of the chained map on the list view is comparable to the strict list single map results.

Given these results, we can draw the following conclusions. Using chained map operations on strictly evaluated, immutable collections can have a significant performance impact. If performance matters, you should aim to combine your map operations. If you cannot combine the map operations yourself (maybe you are just providing a library, like [Apache Spark](https://spark.apache.org/)), using a lazy evaluated collection can help reducing the run time significantly.

## Sorting Data Structures

### Motivation

Sorting a collection is required in many applications. May it be showing a list of events ordered by their time of occurrence, or preparing a table for being joined with another one using a merge-join algorithm. 20 years ago, developers had to be able to write efficient sorting algorithms themselves, as standard libraries were not as rich and computers not as fast.

Nowadays you will find fast-enough implementations of sorting algorithms in almost any standard library. If you are not dealing with strict performance requirements, this is also fine, as using available standard functions can make the code less buggy and more readable.

Scala offers a method to sort immutable collections called `sorted`, which is available for all standard sequence-like collections. In this experiment we want to compare the relative performance of `sorted` on different Scala data structures, and also compare it to the performance of the `java.util.Arrays.sort` method.

### Variables

```scala
val size = Gen.enumeration("size")(List.iterate(1, 7)(_ * 10): _*)
val list = for { s <- size } yield List.fill(s)(Random.nextInt)
val array = for { l <- list } yield l.toArray
val vector = for { l <- list } yield l.toVector
```

### Experiments

Given the `list`, `array`, and `vector` as `l`, filled with random integers, we sort them using the Scala `sorted` method. For the array, we also apply the Java `sort`, which works in place. In order to make the results comparable to Scala, which gives you a new collection back instead of modifying the existing one, we also copy the array first in another experiment.

- `l.sorted`
- `util.Arrays.sort(l)`
- `val newArray = new Array[Int](l.length)`  
  `Array.copy(l, 0, newArray, 0, l.length)`  
  `util.Arrays.sort(newArray)`

### Results

![lines](https://thepracticaldev.s3.amazonaws.com/i/d6hc7yoyz49yhqcbbfzy.png)
![legend](https://thepracticaldev.s3.amazonaws.com/i/p9268kmqmc6qk200p71w.png)

Looking at the performance for different collection sizes there are no surprises (log scale would've been better I know...). When looking at the difference between the Scala and Java array sort, I was kind of surprised.

![bars](https://thepracticaldev.s3.amazonaws.com/i/zfpgs701lml7ighacldi.png)
![legend](https://thepracticaldev.s3.amazonaws.com/i/p9268kmqmc6qk200p71w.png)

The Scala sorts are *so much slower*. Looking at implementation of `sorted` we can spot two details which might explain the difference in runtime.

```scala
def sorted[B >: A](implicit ord: Ordering[B]): Repr = {
   val len = this.length
   val b = newBuilder
   if (len == 1) b ++= this
   else if (len > 1) {
     b.sizeHint(len)
     val arr = new Array[AnyRef](len)
     var i = 0
     for (x <- this) {
       arr(i) = x.asInstanceOf[AnyRef]
       i += 1
     }
     java.util.Arrays.sort(arr, ord.asInstanceOf[Ordering[Object]])
     i = 0
     while (i < arr.length) {
       b += arr(i).asInstanceOf[A]
       i += 1
     }
   }
   b.result()
 }
```

You can see that it also uses `Arrays.sort` internally. But why is it so much slower? I think the reason for that is that it does not only copy the data to a new array but also has to copy it back to a collection of the original type. When sorting an immutable list you expect to get another immutable list back. This is done using a respective builder `b` (e.g. a `ListBuilder`):

```scala
while (i < arr.length) {
  b += arr(i).asInstanceOf[A]
  i += 1
}
```

But also the creation of the initial array could be a reason for it being slower. For making the copy, I was using `Arrays.copy`, which uses the native method `java.lang.System.arraycopy` under the hood. In the Scala method, the array is created in a loop:

```scala
for (x <- this) {
  arr(i) = x.asInstanceOf[AnyRef]
  i += 1
}
```

Looking at those results, I think it is obvious that when it comes to sorting, you should always check the performance of your implementation if it matters to you. Using a sort algorithm that immediately outputs a new immutable collection instead of relying on an intermediate array would be the better choice. Nevertheless most of the time the benefits you gain from using standard methods outweigh the performance gain of custom solutions.

## Concatenation vs. Builder

### Motivation

### Variables

### Experiments

### Results

# References

- [1] Thomas H. Cormen, Clifford Stein, Ronald L. Rivest, and Charles E. Leiserson. 2001. Introduction to Algorithms (2nd ed.). McGraw-Hill Higher Education.
- [2] Fleming, Philip J.; Wallace, John J. 1986. How not to lie with statistics: the correct way to summarize benchmark results. Communications of the ACM. 29 (3): 218–221.
- [3] [ScalaMeter Homepage](http://scalameter.github.io/)
- [4] [ScalaMeter Getting Started Guide](http://scalameter.github.io/home/gettingstarted/0.7/simplemicrobenchmark/index.html)
