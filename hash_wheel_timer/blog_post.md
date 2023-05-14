---
title: Hashed Wheel Timers
published: true
description: Hashed wheel timers are great for handling a large number of timer events with high efficiency and low overhead.
tags: datastructures, algorithms, java
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/9688olptuaqd1vx2co6z.jpg
---

## Introduction

A **Hashed Wheel Timer** is a data structure that manages time-based events efficiently. It's often used in networking applications where numerous events must be handled concurrently, and each event has a distinct timeout period. Hashed wheel timers are great for handling a large number of timer events with high efficiency and low overhead.

The concept behind a hashed wheel timer is relatively simple: imagine a rotating wheel with multiple buckets (or slots), where each bucket corresponds to a time slot. Timer tasks are hashed into these buckets according to their timeout values. As the wheel rotates (with the passage of time), the tasks in the current bucket are executed.

## Implementation

Let's dive into an example implementation in Java:

```java
package de.frosner;

import java.util.*;
import java.util.concurrent.*;
import java.time.Duration;

public class HashedWheelTimer {
    private final Duration tickDuration;
    private final List<ConcurrentLinkedQueue<Timeout>> wheel;
    private volatile int wheelCursor = 0;

    public HashedWheelTimer(int wheelSize, Duration tickDuration) {
        this.tickDuration = tickDuration;
        this.wheel = new ArrayList<>(wheelSize);
        for (int i = 0; i < wheelSize; i++) {
            wheel.add(new ConcurrentLinkedQueue<>());
        }
        start();
    }

    public void newTimeout(Runnable task, Duration delay) {
        long ticks = delay.isZero() ? 0 : delay.plus(tickDuration).dividedBy(tickDuration);
        int stopIndex = (wheelCursor + (int)(ticks % wheel.size())) % wheel.size();
        wheel.get(stopIndex).add(new Timeout(task, ticks / wheel.size()));
    }

    private void start() {
        Executors.newSingleThreadScheduledExecutor().scheduleAtFixedRate(() -> {
            System.out.println("Tick " + wheelCursor);
            ConcurrentLinkedQueue<Timeout> bucket = wheel.get(wheelCursor);
            List<Timeout> pendingTimeouts = new ArrayList<>();
            Timeout timeout;
            while ((timeout = bucket.poll()) != null) {
                System.out.println("Processing task " + timeout.task + " with " + timeout.remainingRounds + " remaining rounds");
                if (timeout.remainingRounds <= 0) {
                    timeout.task.run();
                } else {
                    timeout.remainingRounds--;
                    pendingTimeouts.add(timeout);
                }
            }
            bucket.addAll(pendingTimeouts);
            wheelCursor = (wheelCursor + 1) % wheel.size();
        }, tickDuration.toMillis(), tickDuration.toMillis(), TimeUnit.MILLISECONDS);
    }

    private static class Timeout {
        final Runnable task;
        long remainingRounds;

        Timeout(Runnable task, long remainingRounds) {
            this.task = task;
            this.remainingRounds = remainingRounds;
        }
    }
}
```

This is a basic implementation of a hashed wheel timer. It consists of a `HashedWheelTimer` class that manages an array of buckets (implemented as concurrent queues), each representing a time slot. In the constructor, we initialize the timer, create the wheel, and start the rotation.

The `newTimeout` method is used to add a new task to the timer. The task is scheduled to run after a specified delay. The method calculates the number of ticks for the delay and decides which bucket the task should be placed in.

Finally, the `start` method is used to start the timer. It creates a single-threaded executor that ticks at a fixed rate. On every tick, it retrieves the current bucket and processes all tasks in it. If a task's remaining rounds are zero, it runs the task; otherwise, it reduces the remaining rounds by one and puts the task back into the bucket.

A JUnit test can help verify that the `HashedWheelTimer` is functioning as expected. Let's create a simple test case where we schedule a task to increment a value after a certain delay:

```java
package de.frosner;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicBoolean;

public class HashedWheelTimerTest {
    @Test
    public void testTimer() throws InterruptedException {
        HashedWheelTimer timer = new HashedWheelTimer(10, Duration.ofSeconds(1)); // Wheel size 10, tick duration 1s
        AtomicBoolean value1 = new AtomicBoolean(false);
        AtomicBoolean value2 = new AtomicBoolean(false);

        timer.newTimeout(() -> value1.set(true), Duration.ofSeconds(11));
        timer.newTimeout(() -> value2.set(true), Duration.ofSeconds(5));

        Thread.sleep(2000);
        assertFalse(value1.get());
        assertFalse(value2.get());
        Thread.sleep(2000);
        assertFalse(value1.get());
        assertFalse(value2.get());
        Thread.sleep(2000);
        assertFalse(value1.get());
        assertTrue(value2.get());
        Thread.sleep(2000);
        assertFalse(value1.get());
        assertTrue(value2.get());
        Thread.sleep(2000);
        assertFalse(value1.get());
        assertTrue(value2.get());
        Thread.sleep(2000);
        assertTrue(value1.get());
        assertTrue(value2.get());
    }
}
```

In this test, we create a `HashedWheelTimer` and two `AtomicBoolean`s with an initial value of `false`. We schedule a task to toggle the first boolean after 11 seconds, and another one to toggle the second boolean after 5 seconds. We then resume the test thread every 2 seconds, and checking the integer's value until 11 seconds have passed.

Since we have some debugging statements on each tick, as well as for every processed task, executing the test also gives us a useful trace:

```
Tick 0
Tick 1
Processing task de.frosner.HashedWheelTimerTest$$Lambda$352/0x0000000800cac000@6f1364d9 with 1 remaining rounds
Tick 2
Tick 3
Tick 4
Tick 5
Processing task de.frosner.HashedWheelTimerTest$$Lambda$353/0x0000000800cac408@592d000b with 0 remaining rounds
Tick 6
Tick 7
Tick 8
Tick 9
Tick 0
Tick 1
Processing task de.frosner.HashedWheelTimerTest$$Lambda$352/0x0000000800cac000@6f1364d9 with 0 remaining rounds
```

This test helps verify that tasks are not run before their delay period and that they are run after approximately the right amount of time. Note, however, that due to the nature of threaded execution and system timing, this test could potentially fail if the system is under heavy load or experiencing other issues that cause significant delays.

If you are looking for a more deterministic test, you could rewrite the implementation in a way that enables passing a custom scheduler implementation. In the test, you can then provide a mock scheduler which you can manipulate more deterministically.

## Discussion

### Advantages of Hashed Wheel Timers:

- **Efficiency**: The hashed wheel timer provides O(1) time complexity for insert and delete operations. It's excellent for handling a large number of concurrent timer events.

- **Low Overhead**: The timer only needs to manage a fixed number of buckets, no matter how many timer events are present. This results in lower overhead compared to other timer management mechanisms.

### Disadvantages of Hashed Wheel Timers:

- **Resolution**: The resolution of the timer is determined by the tick duration and the wheel size. If a high-resolution timer is needed, the wheel size may become very large, which increases memory usage.

- **Inaccuracy**: The timer tasks are not executed exactly after their delay. There is an inaccuracy which equals the tick duration. This might not be a problem for many use cases, but it's something to be aware of.

### Alternatives to Hashed Wheel Timers:

- **Heap-based timers**: This type of timers maintains a min-heap of timer events, where the top of the heap is the next timer to expire. While heap-based timers have accurate expiry of timer events, they're not as efficient as hashed wheel timers when dealing with a large number of timer events.

- **List-based timers**: These timers maintain a sorted list of timer events. The insertion of a timer event in this case is O(n), but the removal of the event at the head of the list is O(1). This could be an acceptable trade-off in certain scenarios.

## Summary

Hashed wheel timers are an efficient mechanism for managing large numbers of timer events. They utilize a hash-based approach to distribute timer tasks across a fixed number of buckets or slots, each corresponding to a distinct time period. While hashed wheel timers offer significant advantages in terms of efficiency and lower overhead, they do have limitations, such as timer resolution and slight inaccuracy.

Alternative timer management mechanisms, such as heap-based timers and list-based timers, can be used depending on the specific requirements of the system. As with any technical decision, the choice of timer management mechanism should be made based on a thorough understanding of its characteristics and the requirements of the use case at hand.

## References

- [Hashed and Hierarchical Timing Wheels: Data Structures for the Efficient Implementation of a Timer Facility](http://www.cs.columbia.edu/~nahum/w6998/papers/sosp87-timing-wheels.pdf)
- [Example source code](https://github.com/FRosner/hash-wheel-timer-blogpost)
- Cover image by <a href="https://unsplash.com/@cartega?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Jon Cartagena</a> on <a href="https://unsplash.com/photos/mmf7olkmhfw?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
  