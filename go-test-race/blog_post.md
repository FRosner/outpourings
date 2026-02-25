# Catching Race Conditions in Go with `go test -race`

## Introduction

Concurrency is one of Go's greatest strengths. Goroutines are cheap, channels are expressive, and the standard library is built with concurrency in mind. But with concurrency comes a classic hazard: race conditions.

A race condition occurs when two or more goroutines access the same memory concurrently, and at least one of them is writing. The result depends on the exact scheduling order, which the Go runtime does not guarantee. This means your program may work correctly nine times out of ten, only to produce corrupted data or crash unpredictably in production under load.

What makes race conditions particularly dangerous is their silence. The compiler won't warn you. Your tests may pass. The bug only surfaces under the right (wrong) timing conditions, often making it hard to reproduce and painful to debug.

Fortunately, Go ships with a built-in race detector. By simply adding the `-race` flag to your `go test`, `go run`, or `go build` commands, Go instruments your code to monitor memory accesses at runtime and report any races it observes, complete with a detailed stack trace pointing you directly to the problem.

In this post, we'll explore how the race detector works, walk through a concrete example, and look at how to make it a standard part of your development workflow.

## What is the Race Detector?

Go's race detector is a dynamic analysis tool built directly into the Go toolchain. You don't need to install anything extra; it's been available since Go 1.1.

Under the hood, it is powered by [ThreadSanitizer (TSan)](https://clang.llvm.org/docs/ThreadSanitizer.html), a battle-tested runtime instrumentation library originally developed at Google and now maintained as part of the LLVM project. It is also used in C/C++ toolchains like Clang and GCC. When you compile with `-race`, the Go compiler inserts instrumentation around every memory read and write. At runtime, TSan tracks which goroutine last accessed each memory location and flags any unsynchronized concurrent accesses.

Because it works at runtime, the race detector can only report races that actually happen during a given execution. It won't find races in code paths that aren't exercised by your tests, but there are no false positives. That said, instrumentation comes with overhead: programs compiled with `-race` typically run 2–20× slower and use 5–10× more memory. This is perfectly acceptable for tests and CI, but means you generally won't ship race-enabled binaries to production.

## A Simple Race Condition Example

Let's look at a concrete example. Here is a simple `Counter` type with an `Increment` method:

```go
type Counter struct {
  value int
}

func (c *Counter) Increment() {
  c.value++
}

func (c *Counter) Value() int {
  return c.value
}
```

And a test that increments it 1000 times concurrently:

```go
func TestCounter(t *testing.T) {
  c := Counter{}
  var wg sync.WaitGroup

  for i := 0; i < 1000; i++ {
    wg.Add(1)
    go func() {
      defer wg.Done()
      c.Increment()
    }()
  }

  wg.Wait()

  if c.Value() != 1000 {
    t.Errorf("expected 1000, got %d", c.Value())
  }
}
```

The problem is in `Increment`: `c.value++` is not a single atomic operation. It compiles to a read, an increment, and a write. If two goroutines interleave those steps, one of the writes gets lost, so the final count ends up lower than 1000.

Running `go test` shows this can fail outright:

```
--- FAIL: TestCounter (0.00s)
    counter_test.go:23: expected 1000, got 939
FAIL
```

But even when the test happens to pass (perhaps on a slower machine or a lucky scheduling order), the race is still there, waiting to bite. Running with `-race` makes it explicit:

```
==================
WARNING: DATA RACE
Read at 0x00c0000a01e8 by goroutine 9:
  github.com/frosner/go-test-race.(*Counter).Increment()
      counter.go:11 +0x84
  github.com/frosner/go-test-race.TestCounter.func1()
      counter_test.go:16 +0x80

Previous write at 0x00c0000a01e8 by goroutine 7:
  github.com/frosner/go-test-race.(*Counter).Increment()
      counter.go:11 +0x98
  github.com/frosner/go-test-race.TestCounter.func1()
      counter_test.go:16 +0x80

Goroutine 9 (running) created at:
  github.com/frosner/go-test-race.TestCounter()
      counter_test.go:14 +0x74
...
==================
```

The output tells you exactly what happened: goroutine 9 read `c.value` at `counter.go:11` while goroutine 7 had just written to the same address. Both goroutines were spawned at `counter_test.go:14`. There's no ambiguity about where to look.

## Running the Race Detector

The `-race` flag works with the three most common Go commands:

```bash
go test -race ./...   # run tests with race detection (most common)
go run -race main.go  # run a program with race detection
go build -race        # build a race-enabled binary
```

For day-to-day development, `go test -race ./...` is the one you'll use most. The `./...` pattern runs all packages in the module recursively, so no race in any package goes undetected. `go build -race` is useful when you want to run a long-lived service manually and observe it under realistic traffic, for example during load testing or manual QA. Just don't forget to swap it back out before shipping.

### Controlling the race detector

The race detector's behaviour can be tuned via the `GORACE` environment variable, which accepts a space-separated list of options:

```bash
GORACE="halt_on_error=1 log_path=/tmp/race" go test -race ./...
```

The most useful options are:

| Option | Default | Description |
|---|---|---|
| `halt_on_error` | `0` | Exit immediately on the first race instead of continuing |
| `log_path` | `stderr` | Write race reports to a file (e.g. `log_path=/tmp/race` produces `/tmp/race.<pid>`) |
| `strip_path_prefix` | `""` | Remove a path prefix from stack frames to reduce noise |

In CI it's often worth setting `halt_on_error=1` so that the first detected race fails the build loudly rather than letting the run continue and produce a wall of interleaved reports.

## Fixing the Race Condition

There are three idiomatic ways to fix a data race in Go: a mutex, an atomic operation, or a channel. The right choice depends on the complexity of the shared state.

### Option 1: sync.Mutex

A mutex is the most general solution. It works for any shared state, including structs with multiple fields that must be updated together:

```go
import "sync"

type Counter struct {
  mu    sync.Mutex
  value int
}

func (c *Counter) Increment() {
  c.mu.Lock()
  defer c.mu.Unlock()
  c.value++
}

func (c *Counter) Value() int {
  c.mu.Lock()
  defer c.mu.Unlock()
  return c.value
}
```

Note that `Value` also needs the lock: reading shared memory concurrently with a write is itself a race.

### Option 2: sync/atomic

For a single integer counter, `sync/atomic` is simpler and faster than a mutex:

```go
import "sync/atomic"

type Counter struct {
  value atomic.Int64
}

func (c *Counter) Increment() {
  c.value.Add(1)
}

func (c *Counter) Value() int {
  return int(c.value.Load())
}
```

`atomic.Int64` (introduced in Go 1.19) provides a clean, type-safe API. Use atomics when you only need to update a single value; reach for a mutex as soon as the operation involves multiple fields.

### Option 3: Channels

Channels express the Go proverb *"share memory by communicating"*. Instead of protecting shared state with a lock, you give exclusive ownership of the value to a single dedicated goroutine and communicate with it via channels:

```go
type Counter struct {
  inc chan struct{}
  val chan int
}

func NewCounter() *Counter {
  c := &Counter{
    inc: make(chan struct{}),
    val: make(chan int),
  }
  go func() {
    value := 0
    for {
      select {
      case <-c.inc:
        value++
      case c.val <- value:
      }
    }
  }()
  return c
}

func (c *Counter) Increment() {
  c.inc <- struct{}{}
}

func (c *Counter) Value() int {
  return <-c.val
}
```

The `value` variable lives exclusively inside the goroutine, so nothing else can touch it. There is no shared memory and therefore no race. `Increment` sends a signal on `inc`, and `Value` receives the current count from `val`.

The downside is lifecycle management: the background goroutine will leak if the `Counter` is abandoned. A production-ready version would need a `Close` method or a `context.Context` to shut it down. For a simple counter, that's more ceremony than a mutex or atomic warrants, and that's exactly the point. But for more complex stateful objects where multiple fields must stay consistent, this pattern can be a clean and expressive alternative.

### Confirming the fix

After applying the mutex fix, `go test -race` passes cleanly:

```
ok    github.com/frosner/go-test-race  1.525s
```

No `WARNING: DATA RACE`. The race detector's silence is your green light.

## Practical Considerations

### It's a runtime tool, so coverage matters

As mentioned earlier, the race detector can only report races it actually observes. If a racy code path isn't exercised during a test run, no warning is produced. This means the race detector is only as good as your test suite.

A test that calls `Increment` once in a single goroutine will never trigger a race, even if the implementation is unsafe. The race in our example was only visible because the test deliberately ran 1000 concurrent goroutines. When writing tests for concurrent code, design them to exercise real concurrency: use multiple goroutines, vary timing with `runtime.Gosched()` or small sleeps where appropriate, and aim for high coverage of concurrent code paths.

### Don't run it in production, but do run it in CI

The 2–20× slowdown and 5–10× memory increase make `-race` unsuitable for production binaries. However, this overhead is almost always acceptable in a test or CI environment, where correctness matters far more than raw speed.

The ideal setup is to run `go test -race ./...` on every pull request. Races caught at review time are cheap to fix. Races caught in production (if they're caught at all) can mean hours of debugging a Heisenbug.

### The race detector doesn't cover all concurrency bugs

The race detector specifically finds data races: unsynchronized concurrent memory accesses. It will not catch deadlocks, livelocks, or logical race conditions where synchronization exists but the logic is still wrong. For those, you still need good tests and careful code review.

## Tips for Effective Use

### Use -count to repeat tests

Because the race detector only catches races that actually occur, a racy test might get lucky and pass on a single run. Passing `-count=N` tells Go to run each test N times in the same process, increasing the chances of hitting the problematic interleaving:

```bash
go test -race -count=10 ./...
```

This is particularly useful for tests that involve tight timing windows. It won't guarantee discovery, but it significantly raises the odds.

### Use t.Parallel() to increase concurrency

Marking tests with `t.Parallel()` allows them to run concurrently with each other. This increases the overall goroutine concurrency during the test run, which gives the race detector more opportunities to observe racy interactions, especially across different test cases that share package-level state:

```go
func TestCounter(t *testing.T) {
  t.Parallel()
  // ...
}
```

### Write tests that explicitly exercise concurrency

For any type or function that is intended to be safe for concurrent use, write a test that actually uses it concurrently. The pattern used in our `TestCounter` (spawning many goroutines, using a `sync.WaitGroup` to wait for them, then asserting on the result) is a reliable template:

```go
func TestConcurrentAccess(t *testing.T) {
  t.Parallel()
  c := Counter{}
  var wg sync.WaitGroup

  for i := 0; i < 1000; i++ {
    wg.Add(1)
    go func() {
      defer wg.Done()
      c.Increment()
    }()
  }

  wg.Wait()
  if c.Value() != 1000 {
    t.Errorf("expected 1000, got %d", c.Value())
  }
}
```

If the type is not meant to be used concurrently, document that explicitly. It's just as important to set the right expectations as it is to protect the ones that need it.

### Add it to your CI pipeline

The simplest way to ensure `-race` is always run is to make it part of your standard test command in CI. In GitHub Actions, for example:

```yaml
- name: Test
  run: go test -race ./...
```

One line. No extra tooling. You'll catch races on every push before they ever reach production.

## Conclusion

Race conditions are among the hardest bugs to debug: non-deterministic, often invisible under normal load, and capable of causing silent data corruption. Go's built-in race detector gives you a powerful, zero-setup tool to catch them before they reach production.

We've seen how `-race` instruments your code at compile time, reports unsynchronized memory accesses with precise stack traces, and leaves no room for false positives. We've also seen that fixing a detected race is usually straightforward, with `sync.Mutex`, `sync/atomic`, or channels all being idiomatic options depending on the situation.

The cost of enabling it is low: one flag, a slower test run, and nothing more. The benefit is a whole class of concurrency bugs caught automatically, on every PR, before anyone is paged at 3am.

If you're not already running `go test -race ./...` in CI, that's the one takeaway from this post. Add it today.
