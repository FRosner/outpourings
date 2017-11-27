---
title: What I Did Not Know About Scala And Its Standard Library
published: true
description: I am working with Scala as my main programming language for about three years now. I recently went through some basic Scala language exercises for fun and discovered a few things I did not know about.
tags: scala
cover_image: https://thepracticaldev.s3.amazonaws.com/i/fysjv717nuafm295gegv.png
---

## Introduction

I am working with Scala as my main programming language for about three years now. I recently went through some basic [Scala language exercises](https://www.scala-exercises.org/std_lib) for fun and discovered some features and possibilities I did not know about.

Some of the things I find really useful. Others I am not sure whether I like them. In this blog posts we will talk about

1. Removing tuples from a map
2. Never-ending traversables
3. Partial function domains
4. Different usages of back-ticks
5. Infix types
6. Extractors

Let's take a look at them one by one. I did not put them in a particular order, so feel free to skip one or browse through until you find something that interests you!

## 1. Removing Tuples from a Map

"Removing tuples from a map? Sounds easy, how come you didn't know how to do that?" I agree. Sounds easy. In Scala you remove elements from a map by key using the `-` method.

```scala
Map(1 -> "a", 2 -> "b") - 1 == Map(2 -> "b")
```

Now let's consider a map where the key is a pair.

```scala
Map((1, 2) -> "a", (2, 3) -> "b") - (1, 2) == Map((2, 3) -> "b")
```

```
error: type mismatch;
 found   : Int(1)
 required: (Int, Int)
       Map((1, 2) -> 2, (2, 3) -> 3) - (1, 2)
                                        ^
error: type mismatch;
 found   : Int(2)
 required: (Int, Int)
       Map((1, 2) -> 2, (2, 3) -> 3) - (1, 2)     
                                           ^
```

Whoops! What is going on? Turns out that there is not only one `-` method, but two:

```scala
def -(elem: A) = ???

def -(elem1: A, elem2: A, elems: A*) =
  this - elem1 - elem2 -- elems
```

This method allows you to remove multiple keys at once, similar to [`--`](http://www.scala-lang.org/api/2.12.3/scala/collection/Map.html#--(xs:scala.collection.GenTraversableOnce[A]):Repr), but with [varargs](http://daily-scala.blogspot.de/2009/11/varargs.html). To make our above example work, we need to add an extra pair of parenthesis.

```scala
Map((1, 2) -> "a", (2, 3) -> "b") - ((1, 2)) == Map((2, 3) -> "b")
```

I don't know why this method exists and why it is called `-` and not `--` as it clearly removes multiple elements at once. But I am certain that it can lead to confusion when working with tuples as keys.

## 2. Never-Ending Traversables

In Scala, every collection is a [`Traversable`](http://docs.scala-lang.org/overviews/collections/trait-traversable.html). Traverables have different operations, e.g. to add them (`++`), to transform their elements (`map`, `flatMap`, `collect`), and so on. They also give you ways to get information about their size (`isEmpty`, `nonEmpty`, `size`).

When asking about the size of a traversable, you expect an answer that corresponds to the number of elements in the collection, right? `List(1, 2, 3).size` should be `3` as there are three elements in the list. But what about `Stream.from(1).size`? A stream is a traversable that might not have a definite size. Actually this method will never return. It will keep traversing forever.

Luckily there is a method called `hasDefiniteSize` which tells you whether it is safe to call `size` on your traversable, e.g. `Stream.from(1).hasDefiniteSize` will return `false`. Keep in mind though that if this method returns `true`, the collection will certainly be finite, but the other way around is not guaranteed:

- `Stream.from(1, 2).take(5).hasDefiniteSize` returns `false`, but
- `Stream.from(1).take(5).size` is `5`.

I did not use the built-in `Stream` type that often and if I did I was aware what was inside, not calling `size` if it would not be appropriate. But if you want to offer an API that accepts any `Traversable`, make sure to check if it has a definite size before attempting to traverse to the end.

## 3. Partial Function Domains

In functional programming you treat your program as a composition of mathematical functions. Functions are pure, side-effect free transformations from input to output.

However given the standard types available in most programming languages (e.g. integers, floats, lists, etc.) not every method is a function. If you are dividing two integers it is actually not defined if the divisor is 0.

Scala gives you a way to express this by using a [`PartialFunction`](http://www.scala-lang.org/api/2.12.3/scala/PartialFunction.html), indicating that the function is not [total](https://en.wikipedia.org/wiki/Total_relation) (which mathematically speaking makes it not a function but just a relation, as a function needs to be total by definition). Note that Scala does not really tell you that methods like `Int./` and `List.head` are partial functions.

You can define a `PartialFunction` either directly or using a case statement:

```scala
val devide2 = new PartialFunction[Int, Int] {
  override def isDefinedAt(x: Int): Boolean = x != 0
  override def apply(x: Int): Int = 2 / x
}

val divide5: PartialFunction[Int, Int] = { case i if i != 0 => 5 / i }
```

What I did not know before is that there is this `isDefinedAt` method which you need to use and check whether the function can be applied to your input argument.

```scala
devide2.isDefinedAt(3) == true
devide5.isDefinedAt(0) == false
```

How can we deal with the situation in which our function is not defined for the input?

- First of all, try fixing your domain. If you are working with a list and you want to call `head` safely because you want to be sure to receive a non-empty list, accept only inputs of [type non-empty lists](https://typelevel.org/cats/datatypes/oneand.html). This relates very much to what I was discussing in my previous blog post about [choosing the right data model to make invalid state impossible](https://dev.to/frosnerd/making-the-invalid-impossible---choosing-the-right-data-model-9e6). Let the compiler work for you!
- If you cannot fix your domain, you can try to fix your partial function. Instead of defining division as `(Int, Int) -> Int`, define it as `(Int, Int) -> Option[Int]` and return `None` in case the divisor is 0. Now you no longer have a partial function. In case of `head` you can use `headOption` instead.
- If don't want to touch your partial function, you can combine it with other partial functions to cover the full domain. You can combine two partial functions using `orElse`. If the first partial function cannot be applied, Scala will attempt to use the second one.

## 4. Different Usages of Back-ticks

So far I utilized back-ticks only if I needed to use a reserved keyword as a variable name, e.g. when working with Java methods like `Thread.yield`. But there is another use case for it when working with `case` statements.

When pattern matching inside a `case` statement, cases starting with small letters are locally bound variable names. Cases starting with a capital letter are used to match the variable name directly.

```scala
val A = "a"
val b = "b"

"a" match {
  case A => println("A")
  case b => println("b")
}
// prints 'A'

"b" match {
  case A => println("A")
  case b => println("b")
}
// prints 'b'

"c" match {
  case A => println("A")
  case b => println("b")
}
// prints 'b'
```

In the examples above we can see that in the last example `case b` matches also `"c"`, because `b` is a locally bound variable and not the `val b` defined before. If you want to match on `val b` you can either rename it to `val B`, or what I didn't know before, put it in back-ticks inside the case.

```scala
val A = "a"
val b = "b"

"b" match {
  case A => println("A")
  case `b` => println("b")
}
// prints 'b'

"c" match {
  case A => println("A")
  case `b` => println("b")
  case _ => println("_")
}
// prints '_'
```

## 5. Infix Types

In Scala, type parameters can be used to express [parametric polymorphism](https://en.wikipedia.org/wiki/Parametric_polymorphism), e.g. in [generic classes](https://docs.scala-lang.org/tour/generic-classes.html). This provides a way of abstraction, allowing us to implement functionality once that will work on different input types.

If your class has multiple type parameters you can separate them with a comma. Let's say we want to implement a class holding a pair of arbitrary values.

```scala
case class Pair[A, B](a: A, b: B)
```

Now we can create new pairs like so:

```scala
val p: Pair[String, Int] = Pair("Frank", 28)
```

With infix type notation however, you can also write:

```scala
val p: String Pair Int = Pair("Frank", 28)
```

I know that Scala wants to be a scalable, flexible, and extensible language. But in my opinion, giving the developer too many ways to do or express the same thing can make it very hard to read other peoples' code.

If you are lucky, different styles mean that you have to get used to the style when looking at the source code of a new project. If you are not, then different ways of expressing the same thing are mixed within one project, making it hard to read and understand what is going on.

I see that there are [use cases](https://stackoverflow.com/questions/33347955/real-life-examples-of-scala-infix-types) where the infix type notation comes in handy but it is also very easy to make the code completely unreadable. Who would think that [`String ==>> Double`](https://oss.sonatype.org/service/local/repositories/releases/archive/org/scalaz/scalaz_2.11/7.1.4/scalaz_2.11-7.1.4-javadoc.jar/!/index.html#scalaz.$eq$eq$greater$greater) is the type of an immutable map of key/value pairs implemented as a balanced binary tree?

## 6. Extractors

In order to pattern match an object it needs to have an `unapply` method. Objects with this method are called [extractor objects](https://docs.scala-lang.org/tour/extractor-objects.html).

When you define a case class the compiler automatically generates an extractor object for you so you can utilize pattern matching. However, it also possible to define `unapply` directly:

```scala
object Person {
  def apply(internalId: String, name: String) = s"$internalId/$name"

  def unapply(idAndName: String): Option[String] =
    idAndName.split("/").lastOption
}

val p = Person(java.util.UUID.randomUUID.toString, "Carl")
p match {
  case Person("Carl") => println("Hi Carl!")
  case _ => println("Who are you?")
}
// prints 'Hi Carl!'
```

So far so good. What I did not know is that also instances of classes can be used to extract:

```scala
class NameExtractor(prefix: String) {
  def unapply(name: String): Option[String] =
    if (name.startsWith(prefix)) Some(name) else None
}

val e = new NameExtractor("Alex")
"Alexa" match {
  case e(name) => println(s"Hi $name!")
  case _ => println("I prefer other names!")
}
```

This allows you to customize the extractor objects.

## Conclusion

Going through the [Scala exercises](https://www.scala-exercises.org/std_lib) was a lot of fun and although I already knew most of the topics, it was exciting to discover some new things as well. I think that even if you consider yourself to be a senior, expert, guru, rock star or whatever, there are always things you do not know and it never hurts to revisit the basics from time to time.

What do you think about the things we discussed in this post? Do you think that the `-` method with varargs is useful? Have you ever tried to compute the size of an infinite traversable because you did not check whether it has a definite size? Were you aware that before calling a partial function you need to check whether it is actually defined? Do you use back-ticks frequently in your code? Have you ever defined your own type which was supposed to be used in infix notation? Or did you use types in infix notation without realizing it? Can you think of a real world use case for extractor classes instead of objects?

Let me know your thoughts in the comments below!
