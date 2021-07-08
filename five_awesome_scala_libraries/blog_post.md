---
title: Five Awesome Scala Libraries You Should Check Out
published: false
description:
tags: scala, functional programming, testing
cover_image: ???
---

## Introduction

I was working with procedural and object oriented languages since I started programming. After using Java for 5 years I was curious about the advantages of functional programming. In 2014 I took the course [Functional Programming Principles in Scala](https://www.coursera.org/learn/progfun1) on Coursera. Learning these principles made me a better programmer even if I was not using a functional language. As I was used to the JVM and the course used Scala as the programming language, I switched from Java to Scala a few months later for all of my private and professional projects.

I have been using Scala for more than three years now and I learned a lot during that time. When it comes to using a language there are three things I consider useful (in addition to the actual language specification not being bad): A powerful standard library, an active community, and a rich ecosystem of libraries.

There are many great things about Scala, but also things that I don't like. However I don't want to talk about Scala as a language in this post but rather shed some light on five libraries which I find super useful:

- [ScalaCheck](https://www.scalacheck.org/) (property based testing)
- [Enumeratum](https://github.com/lloydmeta/enumeratum) (enumerations)
- [Shapeless](https://github.com/milessabin/shapeless) (generic programming)
- [Pureconfig](https://github.com/pureconfig/pureconfig) (configuration)
- [Cats](https://github.com/typelevel/cats) (functional programming)

The following sections are going to discuss each of these libraries in more detail. It is not going to be a complete introduction or tutorial to each of those libraries. Instead I will focus on what I like about it personally.

## ScalaCheck

[ScalaCheck](https://www.scalacheck.org/) is a library used for automated property-based testing of Scala or Java programs. Property-based tests, in contrast to example-based tests, make statements about input-output relationships of your functions and verify them generating many different possible inputs. Instead of coming up with useful input examples himself, the developer has to think about properties of their algorithm. ScalaCheck then tries to find input examples that violate the property.

Consider a function to sort a list of integers in ascending order:

```scala
def sort(in: List[Int]): List[Int]
```

What are the properties that this function should fulfill?

1. First of all the result should be sorted. This means while moving through the list from beginning to end, the next number is always greater or equal than the previous.
2. Secondly all numbers in the output list should be the same as in the input.
3. Last but not least the output list should have the same size as the input.

Using ScalaCheck we can now write down these properties:

```scala
import org.scalacheck.Prop._

forAll { input: List[Int] =>
  val output = sort(input)
  output.indices.tail.forall(i => r(i) >= r(i-1)) :| "sorted" &&
  input.forall(output.contains) :| "same numbers" &&
  input.size == output.size :| "same size"
}
```

Property-based testing is a very useful addition to example-based testing. It not only generates many more examples than you manually can but also forces you to think about properties of your implementation more than you usually might.

## Enumeratum

[Enumeratum](https://github.com/lloydmeta/enumeratum)

## Shapeless

[Shapeless](https://github.com/milessabin/shapeless)

## Pureconfig

[Pureconfig](https://github.com/pureconfig/pureconfig)

## Cats

[Cats](https://github.com/typelevel/cats)
