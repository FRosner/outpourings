---
title: Making The Invalid Impossible - Choosing The Right Data Model
published: true
description: How to manage state complexity by making invalid state impossible.
tags: scala, domain model, complexity
cover_image: https://thepracticaldev.s3.amazonaws.com/i/2rzsd1x2dwyfmu5zd8eh.png
---

## Introduction

In my [previous post](https://dev.to/frosnerd/hiding-complexity-does-not-make-it-go-away-or-does-it-51i) I talked about complexity in software design. We discussed an example on how picking a simple data structure can make your code easier to understand and maintain.

When it comes to applications dealing with data, complexity is also hugely influenced by the amount of different states your applications can be in. The more combinations of values are allowed, the higher are the chances that some of them are invalid. Invalid state might, if you are lucky, raise an error message. If you are unlucky it might lead to undetected and/or unexpected behaviour.

In this blog post we are going to take a look at how to make invalid state impossible by choosing the right data model. The examples will be written in [Scala](https://www.scala-lang.org/) but they can easily be ported to any other programming language.

## State Complexity

Building stateless applications is a good practice. However there will always be state somewhere, even if it is only in your message queue connecting your stateless services. State is usually implemented based on your domain specific representation of the real world, i.e. as domain objects. These domain objects are typically stored in some data structure and represented as a type.

The more domain objects you have and the more complex they get, the more possible value combinations exist. If you are storing a set of customers with their name, address, and gender, you already have an almost unlimited amount of possible combinations. And here we only have three fields in one object. Think about a domain model that you have worked with in the past. How many different combinations of possible values exist? How many of them are valid? If you think about the combinations that are invalid, did you take them into account when interacting with your data? Are you sure that you caught all of the possible invalid combinations?

Managing state is not an easy task. If your domain is complex you will have a complex domain model. There is no way around this state explosion most of the time. However there is something you can do to decrease the chance of running into an invalid state: Avoiding it!

## Modeling Your State

Let's look at an example. Imagine that you are a professor developing an application to store the course results of your students. Each student will have a student ID and a name. Students enrolled into the course should take the exam in the end where they will receive a grade. A grade can be anything from `A` to `F`. Each exam will have an ID. Students who participated in the course do not necessarily have to take the exam.

A first model you might come up with could be:

```scala
case class Student(
  id: String,
  name: String
)

case class CourseResult(
  id: String,
  students: Seq[Student],
  grades: Seq[String]
)
```

Looks usable. We can store all the information we need. Both students taking the exam as well as their grades are stored in a list, connected by the index. The grade of the first student is the first grade in the grade sequence.

## Avoiding Invalid State

Looking at the first implementation above can you already tell what might go wrong? What are possible instances of our exam result type? Let's create an exam taken by two students:

```scala
CourseResult(
  id = "2017-CS101",
  students = Seq(Student("1", "Frank"), Student("2", "Ralph")),
  grades = Seq("B", "A")
)
```

Alright. What about the following example:

```scala
CourseResult(
  id = "2017-CS101",
  students = Seq(Student("1", "Frank"), Student("2", "Ralph")),
  grades = Seq("B")
)
```

It appears that Ralph does not have a grade. Is this because he enrolled but did not participate in the exam? Or is it because there was a programming error and a grade got lost?

Maybe we need to add a requirement when constructing the exam result instance, throwing an exception if the size of the students and grades list differ:

```scala
case class CourseResult(
  id: String,
  students: Seq[Student],
  grades: Seq[String]
) {
  require(students.size == grades.size,
    "There need to be as many grades as there are students.")
}
```

Trying again to construct an invalid instance would give the following error:

```
java.lang.IllegalArgumentException: requirement failed:
There need to be as many grades as there are students.
```

This is nice but wouldn't it be better if trying to create the invalid state would not even compile? How could we change the implementation such that we don't need to rely on the runtime exception? A good way to do it is to have a list of student and grade pairs, or a dictionary to look up grades for each student. Choosing a dictionary also makes sure that each student can enroll into the course only once. If you used a sequence of pairs you would have to check for duplicates.

```scala
case class CourseResult(
  id: String,
  participations: Map[Student, String]
)
```

Problem solved, you cannot have grades without any students or the other way around. But wait, we had the situation that some students enrolled into the course but did not take the exam. What we can do is to simply store them anyway and just set the grade to `null`. But who prevents you from also setting the exam ID to `null`. Or the student name?

This is a common problem with languages which permit `null` values. It adds more possible state that most of the time does not make sense in the domain. A better way to deal with optional grading is to use the [`Option`](https://en.wikipedia.org/wiki/Option_type) type (also called `Maybe` in other languages). An `Option` is just a container for another value that might also be empty. I recommend to avoid using `null` values or switching to a programming language which does not have `null`.

```scala
case class CourseResult(
  id: String,
  participations: Map[Student, Option[String]]
)
```

Now we can allow Ralph to not take the exam but still enroll:

```scala
CourseResult(
  id = "2017-CS101",
  participations = Map(
    Student("1", "Frank") -> Some("B"),
    Student("2", "Ralph") -> None
  )
)
```

Now let's look at the grades. Grades can be from `A` to `F`. However it is anyway possible to construct a participation like this:

```scala
Student("1", "Frank") -> Some("X")
```

How can we avoid that? My preferred way over adding preconditions and requirements is to make the compiler help you. As there is a finite (and reasonably small) number of possible grades, we can simply enumerate them.

```scala
sealed trait Grade
case object A extends Grade
case object B extends Grade
case object C extends Grade
case object D extends Grade
case object E extends Grade
case object F extends Grade

case class CourseResult(
  id: String,
  grades: Map[Student, Option[Grade]]
)
```

Now we can write a function to calculate whether a student has passed the course using pattern matching:

```scala
def passed(g: Grade): Boolean = g match {
  case F => false
  case _ => true
}
```

If we now removed the `case _ => true` branch (or forgot to implement it in the first place) the compiler will even warn us:

```
warning: match may not be exhaustive.
It would fail on the following inputs: A, B, C, D, E
       def passed(g: Grade): Boolean = g match {
```

When implementing enumerations in Scala I recommend to take a look at [Enumeratum](https://github.com/lloydmeta/enumeratum), a very powerful enumeration implementation that integrates with many serialization libraries.

After a couple of changes to our initial draft we ended up with the following first final version:

```scala
case class Student(
  id: String
  name: String
)

sealed trait Grade
case object A extends Grade
case object B extends Grade
case object C extends Grade
case object D extends Grade
case object E extends Grade
case object F extends Grade

case class CourseResult(
  id: String,
  grades: Map[Student, Option[Grade]]
)
```

Of course this might not be the perfect solution. If your requirements change you might also have to change your model. Changing the model is always associated with refactoring work. Depending on the usage scope you might have to touch many other services when making a change to the `CourseResult` definition. While in this example we only focused on changes to avoid invalid state it is of course important to also think about extensibility.

## Conclusion

In this post we discussed the problem of state complexity. We saw a few examples on how adjusting only a few details like variable types can already reduce the complexity a lot. Making invalid state impossible leads to less errors at runtime because the compiler has your back.

Of course the problem we were looking at was simplified and you might already do many of the things I mentioned automatically. Nevertheless I believe that it is important to be aware of situations where your model makes invalid state possible. Even if it is only a small detail as choosing `Set` over `List` if you don't want to have duplicates.

Most of the time there are no perfect solutions. Choosing a model to represent the real world will always be an approximation. There will be trade-offs in terms of usability, maintainability, and extensibility. It is important to find the right balance based on your functional and non-functional requirements.

Now I am curious about your opinion. Which implementation would you choose if you were the professor? Would you implement it yourself or give it to a working student ;)? Let me know in the comments!
