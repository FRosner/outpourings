---
title: Hiding Complexity Does Not Make It Go Away, Or Does It?
published: true
description: Managing complexity when developing software is not an easy task. Does hiding complexity make it go away? How do simple solutions look? What's the difference between simple and easy?
tags: frontend, data structures, elm
cover_image: https://thepracticaldev.s3.amazonaws.com/i/i128w258qanuuwge6yt2.PNG
---

## "Why don't you simply use an array?"

Some time ago I was implementing a browser based chat application together with a friend. One of the features we wanted to have is the possibility for the user to select a predefined avatar when joining the chat room. He should be able to cycle through available avatars by clicking on the picture of the current one, until he found the one he liked.

I was taking care about the front-end part (written in [Elm](http://elm-lang.org/)), thinking how to implement this functionality. What I needed was a data structure to store the avatars, a way to know the currently selected one, and a way to move to the next avatar. Which data structure should I use?

I decided to go for a [circular linked list](http://www.geeksforgeeks.org/circular-linked-list/). I needed a function to create a new circular list containing the available avatars, a function to get the currently selected avatar, and a function to cycle to a new avatar. These are the signatures I ended up with:

```elm
type CircularList a

fromList : a -> List a -> CircularList a

get : CircularList a -> a

next : CircularList a -> CircularList a
```

The view can now render the avatar like this:

```elm
img
    [ src ( CircularList.get model.avatar )
    , onClick RotateAvatar
    ]
    []
```

Implementing the on-click handler for rotating is straightforward:

```elm
RotateAvatar ->
    ( { model | avatar = CircularList.next <| model.avatar }
    , Cmd.none
    )
```

When my friend reviewed the code, he was asking me "Why didn't you simply use an array?". I asked him how he would implement it using an array. He replied that he would store the avatars plus the index of the currently selected one. If the user clicks he would increment the index. If the index exceeds the array he would start from the beginning.

While this is a perfectly viable solution, I claim that it is not the simplest one. There is a special case which you have to address, making it harder to understand and giving you the possibility to screw up, getting an exception when stepping out of the index bounds. Using a circular list does exactly what you need. The API is clear and offers only the functionality required for this feature.

"But you can anyway use an array and just hide the complexity behind the API you defined.", he said. And he is right. When reading the code that uses the circular list, you only care about the interface, not the implementation. But does hiding the complexity make it go away? I think in this case it at least helps, and it is actually the strength of encapsulation and programming towards interfaces and not implementations: You can have a clean and simple interface, behind which an efficient but maybe not so simple implementation stands.

Before we look at a few more examples (it will be shorter this time, don't worry), let me quickly elaborate a bit on what I mean by complexity.

## Simplicity vs. Complexity

In the introduction I talked a lot about complexity. But what does it really mean? Why is solution A more complex than solution B? Let's define simple and complex:

**Simple**, from Latin *simplus*, originally referred to a medicine made from one ingredient. Something is simple if it is not compound, not intertwined.

**Complex**, from Latin *complexus*, originally referred to a group of related elements. Something is complex if it consists of many different and connected parts.

What we should aim at as developers is to write simple code. Simple solutions are more maintainable, less error prone, and easier to understand. Now you might say that understanding a circular list is not easy, but everybody knows what an array is. How can this possibly be the better choice?

Let me give you another example. Let's take a look at a tablet computer. Is it easy to use? Yes. Is it simple? I doubt it. I would not be able to fix it if something was broken inside. Compare that to a pencil. Is it easy to use? Yes. Is it simple? Yes. You can explain to everyone how a pencil works. Even if you have never seen a pencil before, after using it a bit you would most likely be able to sharpen it.

Often times the words easy and simple are used interchangeably. The difference between easy and difficult, and simple and complex is that the first two are subjective while the last two are objective. There is a very nice talk about this topic from [Rich Hickey](https://www.infoq.com/presentations/Simple-Made-Easy). I highly recommend to watch it.

Now that the terminology topic is out of the way, let's take a look at a few other examples.

## Hidden Complexity - Good or Bad?

### Example 1: Writing to a File

A function that writes a given character string to a file and has the following signature: `def writeToFile(content: String, file: File): Unit`. Looking at this method it seems fairly simple to write to a file. But what happens if you do not have the required permissions to write to that file? Or if the file system is busy? Or if the path does not exist.

Writing a file is complex, but the API is hiding the complexity. Does it make the API easy to use? Yes. But it does not make the complexity go away. If something goes wrong there will be an exception. This is not encoded in the return type, leaving it up to the developer to think about it or letting the unhandled exception  crash the program.

A more explicit way would be to return something indicating whether the file has been written or, if it didn't work, what is the error. `Either` can be a good candidate, or an optional error.

### Example 2: Null Values

Many programming languages support `null` values. In my opinion, the fact that any method that returns a certain type can also return `null` instead, adds extra complexity to *every* method. If you want to reason about your program, you always have to think about a wild `null` appearing out of nowhere.

If you have a method that might return nothing, e.g. because the argument is invalid, returning `null` hides the complexity from the person looking at the API. You might think "Who is going to pass a negative integer into my square root function?". Instead if your method might return nothing, make it explicit, using an appropriate data type like `Option` (also called `Maybe`) or even complex numbers. This way the complexity is (in case of complex numbers literally) visible and can be addressed.

### Example 3: Sending a Message Over The Network

Let's imagine you want to send a message over the network. You can use [UDP](https://en.wikipedia.org/wiki/User_Datagram_Protocol), a very simple protocol. It is stateless and has low overhead. However, it has no mechanism for error recovery:  *fire and forget*.

As in the two examples above we could hide the complexity by just assuming that nothing goes wrong. If something goes wrong anyway, we won't notice. However, we can also use a different protocol: [TCP](https://en.wikipedia.org/wiki/Transmission_Control_Protocol). The API would look similar or the same, the complexity of the situation stays the same, but the TCP protocol is handling parts of the complexity for us. If a packet could not be delivered properly, it will be resent automatically.

What makes this example different than the first two? Why did I claim that hiding complexity in the first two examples is a bad thing, while hiding it in the third example is good?

### Hiding Complexity The Right Way

In my opinion there are two types of hiding complexity:

1. Hiding complexity by sweeping it under the carpet (the bad way)
2. Hiding complexity by separating it from the actual problem, dealing with it somewhere else (the good way)

Many coding guidelines recommend [explicit code](http://docs.python-guide.org/en/latest/writing/style/#explicit-code). In my opinion, explicitness also includes being explicit about unhandled complexity, not hiding it from the user. Although it looks annoying, it might protect you from the nasty, hidden bug that will cost your company a lot of money.

## Reducing Complexity > Hiding Complexity

After we have discussed a lot about hidden complexity, I would like to say that there is something even better than hiding it: Avoiding it.

When looking at the initial example, I prefer to use the circular linked list implementation over the array + index one, even if they are both behind the same API. Here is the type definition of `CircularList` and the implementation of the `get` and `next` method:

```elm
type CircularList a
    = CircularList a (() -> CircularList a)

get : CircularList a -> a
get (CircularList a n) =
    a


next : CircularList a -> CircularList a
next (CircularList a n) =
    n ()
```

It is incredibly straightforward to verify that the implementation does what it is supposed to do. Even implementing it given the type signature is so straightforward, I wouldn't know how to do it differently.

Imagine there would be an array instead. First, you would have to store an index in addition to the actual array in order to implement `get`. Secondly, next would have to branch depending on whether the new index is going to go out of bounds.

There are other scenarios where you might be able to avoid complexity. Is it really a problem if my message gets lost? For VOIP phone calls it doesn't matter as it will not impact the overall quality if one or two packets get lost. So you can safely use UDP and avoid complexity. Do you really need to use a highly optimized sorting algorithm to sort your list of 100 shopping cart items? In my opinion, for most of the software that is being written code quality, maintainability and understandability is way more important than squeezing the last millisecond out of the implementation.

## Final Thoughts

While simplicity and complexity are objective criteria, judging whether something is easy or difficult is not. Choosing a simple solution however will increase the probability that whoever might be looking at it will have an easy time understanding it.

There are some useful tips I like to follow when solving a problem:

- When implementing something, start with the simplest solution that fulfils the requirements. Premature optimization is the root of all evil (not really *all* evil but you get the point).
- Before you start coding, try to explain the solution to someone else. Maybe even picking someone who is not familiar with the problem domain.
- When writing an `if` statement to handle a special case, think why this case is special. Maybe there is a different data structure or algorithm that does not require you to address this case. Use it, even if it might not be as fast or fancy.
- Be explicit about what can go wrong.
- Show your code to your colleagues and see if they can understand it without you explaining it to them.
- Separate concerns. If there is complexity that needs to be dealt with but it does not concern your current problem, try to move it somewhere else. E.g. separate computation from I/O, error handling from business logic, etc.

## The End

Now I am curious what you guys and girls have to say. Do you agree that the circular list solution is simpler? Have you ever been in a situation where you implemented something in a complex way and later simplified it? Do you have a story where hidden complexity lead to a bug later one that could've been avoided? Let me know your thought in the comments!
