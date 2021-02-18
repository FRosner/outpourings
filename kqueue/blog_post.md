---
title: Writing a Simple TCP Server Using Kqueue
published: true
description: In this blog post we want to take a closer look at kqueue by implementing a synchronous, single threaded kqueue event loop based TCP echo server.
tags: kernel, golang, macos, network
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/dc3yii4p77vffxsf1z4w.jpg
---

# Introduction

In [Explain Non-Blocking I/O Like I'm Five](https://dev.to/frosnerd/explain-non-blocking-i-o-like-i-m-five-2a5f) we discussed how modern web servers are able to handle large amounts of concurrent connections thanks to scalable event notification mechanisms built into modern operating system kernels. FreeBSD invented kqueue [[publication](https://people.freebsd.org/~jlemon/papers/kqueue.pdf), [man page](https://www.freebsd.org/cgi/man.cgi?query=kqueue&sektion=2)], which inspired Linux epoll [[man page](https://man7.org/linux/man-pages/man7/epoll.7.html)].

In this blog post we want to take a closer look at kqueue by implementing a synchronous, single threaded kqueue event loop based TCP echo server. We will use Go and the [source code](https://github.com/FRosner/FrSrv) is accessible on GitHub. To run the code you'll need to have a FreeBSD compatible operating system, such as macOS.

Note that kqueue is not only able to handle socket events but arbitrary file descriptor events, signals, asynchronous I/O events, child process state change events, timers, as well as user defined events. It is indeed generic and powerful.

The remainder of the post is structured as follows. First, we will design the server on a conceptual level. Afterwards we are going to implement the necessary modules. We are closing the post by summarizing and reflecting on the whole experience.

# Design

The basic components of our TCP server will be a listening TCP socket, sockets from accepted client connections, a kernel event queue (kqueue), as well as an event loop that polls the queue. The following diagram illustrates the scenario of accepting incoming connections.

![listen socket](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/ch5it7z0l829f5antdb5.png)

When a client wants to connect to our server, a connection request will be placed on the TCP connection queue. The kernel will then place a new event on the kqueue. The event will be processed by the event loop, which accepts the incoming connection, creating a new client socket. The next diagram illustrates how the newly accepted socket is used to read data from the client.

![accept socket](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/x3mz4y6hgctd40i6j0xd.png)

The client writes data to the newly created connection. The kernel places an event on the kqueue, indicating that there is data to be read on this particular socket. The event loop polls that event and reads from the socket. Note that while there is only socket listening to incoming connections, we are creating a new socket for every accepted client connection.

We can implement the design in the following high level steps, which will be discussed in detail in the following sections.

1. Create, bind, and listen on a new socket
2. Create new kqueue
3. Subscribe to socket events
4. Poll for new events in a loop and handle them
 
# Implementation

To avoid a huge single file full of system calls we will encapsulate functionality in different modules: A `socket` module which holds all functionality around managing sockets, a `kqueue` module which encapsulates the event loop functionality, and a `main` module which ties both modules together and forms the TCP echo server executable. We'll start with the socket module. 

## Socket Type

First, let's create a Go representation of a socket. Unix-like operating systems, such as FreeBSD, represent sockets as files. To interact with a socket from Go, we need to know the [file descriptor](https://www.freebsd.org/cgi/man.cgi?query=fd&sektion=4&manpath=freebsd-release-ports). So we can model a socket as a struct that holds the respective file descriptor.

```golang
type Socket struct {
  FileDescriptor int
}
```

Given a socket we want to perform different actions such as reading from, writing to, or closing the socket. Objects that support these operations implement common interfaces in Go, i.e. `io.Reader`, `io.Writer`, and `io.Closer`, respectively.

First, let's implement `io.Reader` utilizing the [`read`](https://www.freebsd.org/cgi/man.cgi?query=read&sektion=2) system call. We will return the number of bytes read, or an error if something goes wrong. 

```golang
func (socket Socket) Read(bytes []byte) (int, error) {
  if len(bytes) == 0 {
    return 0, nil
  }
  numBytesRead, err := 
    syscall.Read(socket.FileDescriptor, bytes)
  if err != nil {
    numBytesRead = 0
  }
  return numBytesRead, err
}
```

We can implement `io.Writer` in an analogous fashion by calling [`write`](https://www.freebsd.org/cgi/man.cgi?query=write&sektion=2).

```golang
func (socket Socket) Write(bytes []byte) (int, error) {
  numBytesWritten, err := 
    syscall.Write(socket.FileDescriptor, bytes)
  if err != nil {
    numBytesWritten = 0
  }
  return numBytesWritten, err
}
```

Closing a socket is as straightforward as calling [`close`](https://www.freebsd.org/cgi/man.cgi?query=close&apropos=0&sektion=2) on the file descriptor.

```golang
func (socket *Socket) Close() error {
  return syscall.Close(socket.FileDescriptor)
}
```

In order to produce meaningful error and log messages later on, we also implement `fmt.Stringer`. We will represent a socket by the respective file descriptor.

```golang
func (socket *Socket) String() string {
  return strconv.Itoa(socket.FileDescriptor)
}
```

## Listening on a Socket

Having the socket type in place we need to provide a way to construct a new socket object that is listening on a specified IP address and port. Listening on a socket can be accomplished by a series of system calls. Let's look at the implementation of our `Listen` function now and then go through it step by step.

```golang
func Listen(ip string, port int) (*Socket, error) {
  socket := &Socket{}

  socketFileDescriptor, err := 
    syscall.Socket(syscall.AF_INET, syscall.SOCK_STREAM, 0)
  if err != nil {
    return nil, fmt.Errorf("failed to create socket (%v)", err)
  }
  socket.FileDescriptor = socketFileDescriptor

  socketAddress := &syscall.SockaddrInet4{Port: port}
  copy(socketAddress.Addr[:], net.ParseIP(ip))
  if err = syscall.Bind(socket.FileDescriptor, socketAddress);
    err != nil {
    return nil, fmt.Errorf("failed to bind socket (%v)", err)
  }

  if err = syscall.Listen(socket.FileDescriptor, syscall.SOMAXCONN);
    err != nil {
    return nil, fmt.Errorf("failed to listen on socket (%v)", err)
  }

  return socket, nil
}
```

The first call is [`socket`](https://www.freebsd.org/cgi/man.cgi?query=socket&apropos=0&sektion=2), which creates an endpoint for communication and returns the descriptor. It requires three arguments:

- The address family we want to use, in our case `AF_INET` (IPv4).
- The socket type, in our case `SOCK_STREAM`, which represents sequenced, reliable, two-way connection based
  byte streams.
- The protocol we want to use. Protocol `0` in `SOCK_STREAM` sockets corresponds to TCP.

Next, we call [`bind`](https://www.freebsd.org/cgi/man.cgi?query=bind&apropos=0&sektion=2) to assign a protocol address to the newly created socket. The first argument of `bind` is the socket file descriptor. The second argument represents a pointer to a struct that holds the address information. We are going to make use of the predefined `SockaddrInet4` struct type from Go here, passing in the IP address and port we want to bind to.

Finally, we call [`listen`](https://www.freebsd.org/cgi/man.cgi?query=listen&apropos=0&sektion=2) so we are able to accept connections. The second argument defines the maximum length of the pending connections queue. We are going to pass the kernel parameter `SOMAXCONN`, which defaults to 128 on my Mac. You can check the value by executing `sysctl kern.ipc.somaxconn`.

Congratulations! We just finished implementing our socket and are ready to accept incoming connections. But how do we know when there is a new connection to accept? And how do we know when there is data to be read? This is where kqueue comes in so let's take a look at the `kqueue` module next.

## Event Loop Type

Again, we will start by defining a struct type representing a kqueue event loop. This time we have to store the kqueue file descriptor as well as the socket file descriptor. We could of course instead store a pointer to the socket object from the previous section if we wanted.

```golang
type EventLoop struct {
  KqueueFileDescriptor int
  SocketFileDescriptor int
}
```

Next, we need a function to create a new event loop from a given socket. As before, we need to make a series of system calls in order to create and prepare the kqueue. First, let's look at the entire function and then go through it step by step.

```golang
func NewEventLoop(s *socket.Socket) (*EventLoop, error) {
  kQueue, err := syscall.Kqueue()
  if err != nil {
    return nil, 
      fmt.Errorf("failed to create kqueue file descriptor (%v)", err)
  }

  changeEvent := syscall.Kevent_t{
    Ident:  uint64(s.FileDescriptor),
    Filter: syscall.EVFILT_READ,
    Flags:  syscall.EV_ADD | syscall.EV_ENABLE,
    Fflags: 0,
    Data:   0,
    Udata:  nil,
  }

  changeEventRegistered, err := syscall.Kevent(
    kQueue, 
    []syscall.Kevent_t{changeEvent}, 
    nil,
    nil
  )
  if err != nil || changeEventRegistered == -1 {
    return nil,
      fmt.Errorf("failed to register change event (%v)", err)
  }

  return &EventLoop{
    KqueueFileDescriptor: kQueue,
    SocketFileDescriptor: s.FileDescriptor
  }, nil
}
```

The first system call [`kqueue`](https://www.freebsd.org/cgi/man.cgi?query=kqueue&apropos=0&sektion=0&format=html) creates a new kernel event queue and returns the respective file descriptor. We can then interact with this kqueue by using the [`kevent`](https://www.freebsd.org/cgi/man.cgi?query=kqueue&apropos=0&sektion=0&format=html) system call. `kevent` provides two functionalities: Subscribing to new events and polling.

In our case we want to subscribe to incoming connection events. We can implement this subscription by passing a `kevent` struct (represented by `Kevent_t` in Go) to the `kevent` system call. Our event contains the following information:

- The file descriptor `Ident`. Set to our socket file descriptor.
- A `Filter` that processes the event. Set to `EVFILT_READ`, which, when used in combination with a listening socket, indicates that we are interested in incoming connection events.
- `Flags` that indicate what actions to perform with this event. In our case we want to add the event to kqueue (`EV_ADD`), i.e. subscribing to it, and enable it (`EV_ENABLE`). Flags can be combined using bitwise or.

We do not need any of the other parameters for what we are trying to achieve. Having created the event definition, we wrap it in an array and pass it to `kevent`. Finally, we can return an event loop that is ready to poll. Let's implement the polling function next.

## Event Loop Polling

The event loop is a simple for-loop that polls for new kernel events and processes them accordingly. Polling is accomplished using the `kevent` system call from before, but this time passing an empty array of events that will be filled with new events once they are available.

We can then go through the events one by one and process them. New client connections will be transformed to client sockets so that we can transfer data from and to individual clients. Let's look at the code and then go through the different event types in the following paragraphs.

```golang
func (eventLoop *EventLoop) Handle(handler Handler) {
  for {
    newEvents := make([]syscall.Kevent_t, 10)
    numNewEvents, err := syscall.Kevent(
      eventLoop.KqueueFileDescriptor,
      nil,
      newEvents,
      nil
    )
    if err != nil {
      continue
    }

    for i := 0; i < numNewEvents; i++ {
      currentEvent := newEvents[i]
      eventFileDescriptor := int(currentEvent.Ident)

      if currentEvent.Flags&syscall.EV_EOF != 0 {
        // client closing connection
        syscall.Close(eventFileDescriptor)
      } else if eventFileDescriptor == eventLoop.SocketFileDescriptor {
        // new incoming connection
        socketConnection, _, err := 
          syscall.Accept(eventFileDescriptor)
        if err != nil {
          continue
        }
        
        socketEvent := syscall.Kevent_t{
          Ident:  uint64(socketConnection),
          Filter: syscall.EVFILT_READ,
          Flags:  syscall.EV_ADD,
          Fflags: 0,
          Data:   0,
          Udata:  nil,
        }
        socketEventRegistered, err := syscall.Kevent(
          eventLoop.KqueueFileDescriptor,
          []syscall.Kevent_t{socketEvent},
          nil,
          nil
        )
        if err != nil || socketEventRegistered == -1 {
          continue
        }
      } else if currentEvent.Filter&syscall.EVFILT_READ != 0 {
        // data available -> forward to handler
        handler(&socket.Socket{
          FileDescriptor: int(eventFileDescriptor)
        })
      }
      
      // ignore all other events
    }
  }
}
```

The first case we want to handle are `EV_EOF` events. An `EV_EOF` event indicates that a client wants to close its connection. In that case we simply close the respective socket file descriptor.

The second case represents an incoming connection on the listen socket. We can use the [`accept`](https://www.freebsd.org/cgi/man.cgi?query=accept) system call to pop the connection request from the queue of pending TCP connections. It then creates a new socket and a new file descriptor for that socket. Based on that newly created socket we subscribe to a new `EVFILT_READ` event. On accept sockets, `EVFILT_READ` events happen whenever there is data to be read on the socket.

The third case handles the `EVFILT_READ` events from the previous case. These events contain the file descriptor of the client socket. We wrap it inside a `Socket` object and pass it to the handler function.

Note that we omitted proper error handling and simply continue the loop if something goes wrong. Now with the event loop function in place, let's wire everything together in the main module.

## Main Function

Thanks to our `socket` and `kqueue` modules from the previous sections we can easily implement an echo server now. We first create a socket that listens on the specified IP address and port, then create a new event loop based on that socket, and finally start the loop, passing an echo handler.

```golang
func main() {
  s, err := socket.Listen("127.0.0.1", 8080)
  if err != nil {
    log.Println("Failed to create Socket:", err)
    os.Exit(1)
  }

  eventLoop, err := kqueue.NewEventLoop(s)
  if err != nil {
    log.Println("Failed to create event loop:", err)
    os.Exit(1)
  }

  log.Println("Server started. Waiting for incoming connections. ^C to exit.")
  
  eventLoop.Handle(func(s *socket.Socket) {
    reader := bufio.NewReader(s)
    for {
      line, err := reader.ReadString('\n')
      if err != nil || strings.TrimSpace(line) == "" {
        break
      }
      s.Write([]byte(line))
    }
    s.Close()
  })
}
```

The handler will echo newline separated text data to the client until it receives an empty line. It then closes the connection. We can test it out using `curl`, an HTTP client that will send a GET request and print out the echo response, which is the GET request it sent.

![demo using curl](https://dev-to-uploads.s3.amazonaws.com/i/fuq8si8rmz2q4nsxnumz.gif)

# Final Thoughts

We successfully implemented a simple TCP echo server using kqueue. Of course, the code is far from being production ready. We are running on a single thread and use blocking sockets. Additionally, there is no real error handling. In most cases it makes sense to use an existing library rather than interacting with the OS kernel yourself.

I am surprised how difficult it can be to interact with the kernel though. The APIs are very complex, and you have to read many man pages until you figure out what you need to do. Nevertheless, it was an amazing learning experience.

---

<span>Cover image by <a href="https://unsplash.com/@adriendlf?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">Adrien Delforge</a> on <a href="https://unsplash.com/s/photos/queue?utm_source=unsplash&amp;utm_medium=referral&amp;utm_content=creditCopyText">Unsplash</a></span>