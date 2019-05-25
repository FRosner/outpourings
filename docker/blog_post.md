---
title: Docker Demystified
published: true
description: Since its open source launch in 2013, Docker became one of the most popular pieces of technology out there. In this blog post we want to dive deeper into the internals of Docker to understand how it works.
tags: linux, docker, beginners, devops
cover_image: https://user-images.githubusercontent.com/3427394/58331541-a223c680-7e39-11e9-9d52-c1a061a39a55.png
canonical_url: https://blog.codecentric.de/en/2019/05/docker-demystified/
---

# Introduction

Since its open source launch in 2013, Docker became one of the most popular pieces of technology out there. A lot of companies are contributing and a huge amount of people are using and adopting it. But why is it so popular? What does it offer that was not there before? In this blog post we want to dive deeper into the internals of Docker to understand how it works.

The first part of this post will give a quick overview about the basic architectural concepts. In the second part we will introduce four main functionalities that form the foundation for isolation in Docker containers: 1) cgroups, 2) namespaces, 3) stackable image-layers and copy-on-write, and 4) virtual network bridges. In the third section there will be a discussion about opportunities and challenges when using containers and Docker. We conclude by answering some frequently asked questions about Docker.

# Basic Architecture

> "Docker is an open-source project that automates the deployment of applications inside software containers." - *Wikipedia*

People usually refer to containers when talking about operating-system-level virtualization. Operating-system-level virtualization is a method in which the kernel of an operating system allows the existence of multiple isolated application instances. There are many implementations of containers available, one of which is Docker.

Docker launches containers based off of *images*. An image is like a blue print, defining what should be inside the container when it is being created. The usual way to define an image is through a *Dockerfile*. A Dockerfile contains instructions on how to build your image step by step (don't worry you will understand more about what is going on internally later on). The following Dockerfile, for example, will start from an image containing OpenJDK, install Python 3 there, copy the `requirements.txt` inside the image and then install all Python packages from the requirements file.

```Docker
FROM openjdk:8u212-jdk-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    Python3=3.5.3-1 \
    Python3-pip=9.0.1-2+deb9u1 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade -r requirements.txt
```

Images are usually stored in image repositories called Docker *registries*. Dockerhub is a public Docker registry. In order to download images and start containers you need to have a Docker *host*. The Docker host is a Linux machine which runs the Docker *daemon* (a daemon is a background process that is always running, waiting for work to be done).

In order to launch a container, you can use the Docker client, which submits the necessary instructions to the Docker daemon. The Docker daemon is also talking to the Docker registry if it cannot find the requested image locally. The following picture illustrates the [basic architecture](https://docs.docker.com/engine/docker-overview/) of Docker:

[![docker architecture](https://docs.docker.com/engine/images/architecture.svg)](https://docs.docker.com/engine/docker-overview/)

What is important to note already is that Docker itself does not provide the actual containerization but merely uses what is available in Linux. Let's dive into the technical details.

# Container Isolation

Docker achieves isolation of different containers through the combination of four main concepts: 1) *cgroups*, 2) *namespaces*, 3) stackable *image-layers* and *copy-on-write*, and 4) *virtual network bridges*. In the following sub sections we are going to explain these concepts in detail.

## Control Groups (cgroups)

The Linux operating system manages the available hardware resources (memory, CPU, disk I/O, network I/O, ...) and provides a convenient way for processes to access and utilize them. The CPU scheduler of Linux, for example, takes care that every thread will eventually get some time on a CPU core so that no applications are stuck waiting for CPU time.

Control groups (cgroups) are a way to assign a subset of resources to a specific group of processes. This can be used to, e.g., ensure that even if your CPU is super busy with Python scripts, your PostgreSQL database still gets dedicated CPU and RAM. The following picture illustrates this in an example scenario with 4 CPU cores and 16 GB RAM.

![cgroups](https://thepracticaldev.s3.amazonaws.com/i/49ymdqhhg9eb4cgemflr.png)

All Zeppelin notebooks started in the zeppelin-grp will utilize only core 1 and 2, while the PostgreSQL processes share core 3 and 4. Same applies to the memory. Cgroups are one important building block in container isolation as they allow hardware resource isolation.

## Namespaces

While cgroups isolate hardware resources, namespaces isolate and virtualize system resources. Examples of system resources that can be virtualized include process IDs, hostnames, user IDs, network access, interprocess communication, and filesystems. Let's first dive into an example of process ID (PID) namespaces to make this more clear and then briefly discuss other namespaces as well.

### PID Namespaces

The Linux operating system organizes processes in a so called process tree. The tree root is the first process that gets started after the operating system is booted and it has the PID 1. As only one process tree can exist and all other processes (e.g. Firefox, terminal emulators, SSH servers) need to be (directly or indirectly) started by this process. Due to the fact that this process initializes all other processes it is often referred to as the *init* process.

The following figure illustrates parts of a typical process tree where the init process started a logging service (`syslogd`), a scheduler (`cron`) and a login shell (`bash`):

```
1 /sbin/init
+-- 196 /usr/sbin/syslogd -s
+-- 354 /usr/sbin/cron -s
+-- 391 login
    +-- 400 bash
        +-- 701 /usr/local/bin/pstree
```

Inside this tree, every process can see every other process and send signals (e.g. to request the process to stop) if they wish. Using PID namespaces virtualizes the PIDs for a specific process and all its sub processes, making it think that it has PID 1. It will then also not being able to see any other processes except its own children. The following figure illustrates how different PID namespaces isolate the process sub trees of two Zeppelin processes.

```
1 /sbin/init
|
+ ...
|
+-- 506 /usr/local/zeppelin
    1 /usr/local/zeppelin
    +-- 2 interpreter.sh
    +-- 3 interpreter.sh
+-- 511 /usr/local/zeppelin
    1 /usr/local/zeppelin
    +-- 2 java
```

### Filesystem Namespaces

Another use case for namespaces is the Linux filesystem. Similar to PID namespaces, filesystem namespaces virtualize and isolate parts of a tree - in this case the filesystem tree. The Linux filesystem is organized as a tree and it has a root, typically referred to as `/`.

In order to achieve isolation on a filesystem level, the namespace will map a node in the filesystem tree to a virtual root inside that namespace. Browsing the filesystem inside that namespace, Linux does not allow you to go beyond your virtualized root. The following drawing shows part of a filesystem that contains multiple "virtual" filesystem roots inside the `/drives/xx` folders, each containing different data.

![filesystem namespace example](https://thepracticaldev.s3.amazonaws.com/i/758b8sygjjivyqdp0thz.png)

### Other Namespaces

Besides the PID and the filesystem namespaces there are also [other kinds of namespaces](https://en.wikipedia.org/wiki/Linux_namespaces#Namespace_kinds). Docker allows you to utilize them in order to achieve the amount of isolation you require. The user namespace, e.g., allows you to map a user inside a container to a different user outside. This can be used to map the root user inside the container to a non-root user outside, so the process inside the container acts like an admin inside but outside it has no special privileges.

## Stackable Image Layers and Copy-On-Write

Now that we have a more detailed understanding of how hardware and system resource isolation helps us to build containers, we are going to take a look into the way that Docker stores images. As we saw earlier, a Docker image is like a blueprint for a container. It comes with all dependencies required to start the application that it contains. But how are these dependencies stored?

Docker persists images in *stackable layers*. A layer contains the changes to the previous layer. If you, for example, install first Python and then copy a Python script, your image will have two additional layers: One containing the Python executables and another one containing the script. The following picture shows a Zeppelin, an Spring and a PHP image, all based on Ubuntu.

![stackable image layers](https://thepracticaldev.s3.amazonaws.com/i/ob5jicwj7klqay4avekh.png)

In order not to store Ubuntu three times, layers are immutable and shared. Docker uses *copy-on-write* to only make a copy of a file if there are changes.

When starting a container based on an image, the Docker daemon will provide you with all the layers contained in that image and put it in an isolated filesystem namespace for this container. The combination of stackable layers, copy-on-write, and filesystem namespaces enable you to run a container completely independent of the things "installed" on the Docker host without wasting a lot of space. This is one of the reasons why containers are more lightweight compared to virtual machines.

## Virtual Network Bridge

Now we know ways to isolate hardware resources (cgroups) and system resources (namespaces) and how to provide each container with a predefined set of dependencies to be independent from the host system (image layers). The last building block, the *virtual network bridge*, helps us in isolating the network stack inside a container.

A network bridge is a computer networking device that creates a single aggregate network from multiple communication networks or network segments. Let's look at a typical setup of a physical network bridge connecting two network segments (LAN 1 and LAN 2):

![network bridge](https://thepracticaldev.s3.amazonaws.com/i/qpwxpivuqqz9gir673aj.png)

Usually we only have a limited amount of network interfaces (e.g. physical network cards) on the Docker host and all processes somehow need to share access to it. In order to isolate the networking of containers, Docker allows you to create a virtual network interface for each container. It then connects all the virtual network interfaces to the host network adapter, as shown in the following picture:

![docker virtual network bridge](https://thepracticaldev.s3.amazonaws.com/i/bpn9fs2lvmgigyvya7ot.png)

The two containers in this example have their own `eth0` network interface inside their network namespace. It is mapped to a corresponding virtual network interfaces `veth0` and `veth1` on the Docker host. The virtual network bridge `docker0` connects the host network interface `eth0` to all container network interfaces.

Docker gives you a lot of freedom in configuring the bridge, so that you can expose only specific ports to the outside world or directly wire two containers together (e.g. a database container and an application which needs access to it) without exposing anything to the outside.

## Connecting the Dots

Taking the techniques and features described in the previous sub sections, we are now able to "containerize" our applications. While it is possible to manually create containers using cgroups, namespaces, virtual network adapters, etc., Docker is a tool that makes it convenient and with almost no overhead. It handles all the manual, configuration intensive tasks, making containers accessible to software developers and not only Linux specialists.

In fact there is a [nice talk](https://www.youtube.com/watch?v=sK5i-N34im8) available from one of the Docker engineers where he demonstrates how to manually create a container, also explaining the details we covered in this sub section.

# Opportunities and Challenges of Docker

By now, many people are using Docker on a daily basis. What benefits do containers add? What does Docker offer that was not there before? In the end everything you need for containerizing your applications was already available in Linux for a long time, wasn't it?

Let's look at some opportunities (not an exhaustive list of course) that you have when moving to a container based setup. Of course there are not only opportunities, but also challenges that might give you a hard time when adopting Docker. We are also going to name a few in this section.

## Opportunities

**Docker enables DevOps.** The DevOps philosophy tries to connect development and operations activities, empowering developers to deploy their applications themselves. *You build it, you run it.* Having a Docker based deployment, developers can ship their artifacts together with the required dependencies directly without having to worry about dependency conflicts. Also it allows developers to write more sophisticated tests and execute them faster, e.g., creating a real database in another container and linking it to their application on their laptop in a few seconds (see [Testcontainers](https://www.testcontainers.org/)).

**Containers increase the predictability of your deployment.** No more "runs on my machine". No more failing application deployments because one machine has a different version of Java installed. You build the image once and you can run it anywhere (given there is a Linux Kernel and Docker installed).

**High adoption rate and good integration with many prominent cluster managers.** One big part about using Docker is the software ecosystem around it. If you are planning to operate at scale, you won't get around using one or the other cluster manager. It doesn't matter if you decide to let someone else manage your deployment (e.g. Google Cloud, Docker Cloud, Heroku, AWS, ...) or want to maintain your own cluster manager (e.g. Kubernetes, Nomad, Mesos), there are plenty of solutions out there.

**Lightweight containers enable fast failure recovery or auto-scaling.** Imagine running an online shop. During Christmas time, people will start hitting your web servers and your current setup might not be sufficient in terms of capacity. Given that you have enough free hardware resources, starting a few more containers hosting your web application will take only a few seconds. Also failing machines can be recovered by just migrating the containers to a new machine.

## Challenges

**Containers give a false sense of security.** There are many pitfalls when it comes to securing your applications. It is wrong to assume that one way to secure them is to put them inside containers. Containers do not secure anything, per se. If someone hacks your containerized web application he might be locked into the namespaces but there are several ways to escape this depending on the setup. Be aware of this and put as much effort into security as you would without Docker.

**Docker makes it easy for people to deploy half baked solutions.** Pick your favorite piece of software and enter its name it to the Google search bar, adding "Docker". You will probably find at least one if not dozens of already publicly available images containing your software at Dockerhub. So why not just execute it and give it a shot? What can go wrong? Many things can go wrong. Things happen to look shiny and awesome when put into containers and people stop paying attention to the actual software and configuration inside.

**The fat container anti-pattern results in large, hard-to-manage deployment artifacts.** I have seen Docker images which require you to expose more than 20 ports for different applications inside when a the container. The philosophy of Docker is that one container should do one job and you should rather compose them instead of making them heavier. If you end up putting all your tools together in one container you lose all the advantages, might have different versions of Java or Python inside and end up with a 20 GB, unmanageable image.

**Deep Linux knowledge might still be required to debug certain situations.** You might have heard your colleague saying that XXX does not work with Docker. There are multiple reasons why this could happen. Some applications have issues running inside a bridged network namespace if they do not distinguish properly between the network interface they bind to and the one they advertise. Another issue can be related to cgroups and namespaces where default settings in terms of shared memory are not the same as on your favorite Linux distribution, leading to OOM errors when running inside containers. However, most of the issues are not actually related to Docker but to the application not being designed properly and they are not that frequent. Still they require some deeper understanding of how Linux and Docker works which not every Docker user has.

# Frequently Asked Questions

## Q: What's the difference between a container and a virtual machine?

Without diving too much into details about the architecture of virtual machines (VMs), let us look at the main difference between the two on a conceptual level. Containers run inside an operating system, using kernel features to isolate applications. VMs on the other hand require a hypervisor which runs inside an operating system. The hypervisor then creates virtual hardware which can be accessed by another set of operating systems. The following illustration compares a virtual machine based application setup and a container based setup.

![vm vs container](https://thepracticaldev.s3.amazonaws.com/i/d5sazt7ln80e63qvhz1r.png)

As you can see, the container based setup has less overhead as it does not require an additional operating system for each application. This is possible because the container manager (e.g. Docker) uses operating system functionality directly to isolate applications in a more lightweight fashion.

Does that mean that containers are superior to virtual machines? It depends. Both technologies have their use cases and it sometimes even make sense to combine them, running a container manager inside a VM. There are many blog posts out there discussing the pros and cons of both solutions so we're not going to go into detail right now. It is important to understand the difference and to not see containers as some kind of "lightweight VM", because internally they are different.

## Q: Do containers contain?

Looking at the definition of containers and what we've learned so far, we can safely say that it is possible to use Docker to deploy isolated applications. By combining control groups and namespaces with stackable image layers and virtual network interfaces plus a virtual network bridge, we have all the tools required to completely isolate an application, possibly also locking the process in the container. The reality shows that it's not that easy though. First, it needs to be configured correctly and secondly, you will notice that completely isolated containers don't make a lot of sense most of the time.

In the end your application somehow needs to have some side effect (persisting data to disk, sending packets over the network, ...). So you will end up breaking the isolation by forwarding network traffic or mounting host volumes into your filesystem namespace. Also it is not required to use all available namespace features. While the network, PID and filesystem namespace features are enabled by default, using the user ID namespace requires you to add extra configuration options.

So it is false to assume that just by putting something inside a container makes it secure. AWS, e.g., uses a lightweight VM engine called [Firecracker](https://github.com/firecracker-microvm/firecracker) for secure and multi-tenant execution of short-lived workloads.

## Q: Do containers make my production environment more stable?

Some people argue that containers increase stability because they isolate errors. While this is true to the extent that properly configured namespaces and cgroups will limit side effects of one process going rogue, in practice there are some things to keep in mind.

As mentioned earlier, containers do only contain if configured properly and most of the time you want them to interact with other parts of your system. It is therefore possible to say that containers can help to increase stability in your deployment but you should always keep in mind that it does not protect your applications from failing.

# Conclusion

Docker is a great piece of technology to independently deploy applications in a more or less reproducible and isolated way. As always, there is no one-size-fits-all solution and you should understand your requirements in terms of security, performance, deployability, observability, and so on, before choosing Docker as the tool of your choice.

Luckily there is a great ecosystem of tools around Docker already. Solutions for service discovery, container orchestration, log forwarding, encryption and other use cases can be added as needed. I would like to close the post by quoting one of my favorite tweets:

> "Putting broken software into a Docker container doesn't make it any less broken." - [@sadserver](https://twitter.com/sadserver/status/587840646968250368)
