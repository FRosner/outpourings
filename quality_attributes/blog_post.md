---
title: Quality Attributes in Software
published: true
description: How do quality attributes influence functional requirements? How do you identify the quality attributes that are relevant for the stakeholders and your team?
tags: quality, architecture, soa, microservices
cover_image: https://thepracticaldev.s3.amazonaws.com/i/bwvjhlx2n1bwzyrhpk15.png
---

# Introduction

When designing a system architecture you will have to take decisions. Those decisions will influence how your system is going to behave in different scenarios. The behaviour will impact the functionality of the system or product in one way or the other.

A service oriented architecture (SOA), for example, implements complex functionality as a combination of loosely coupled services. Each service is developed, deployed and operated more or less independently. In contrast to a monolithic architecture the loose coupling is supposed to bring certain benefits to the table.

But how can we discuss, measure, and evaluate the impact of architecture decisions? You probably heard people talking about "A is a scalable, fault-tolerant database" or "B is easier to maintain than C". A commonly used terminology for those concepts are *non-functional requirements* (NFR). NFRs are an important topic for every architect. The name is derived as an addition to *functional requirements* (FR) which are heavily influenced by the business stakeholders.

I personally prefer the term *quality attributes* instead of NFR. The "non" in "non-functional" implies a disconnect between the requirement and the functionality, which is not true in most cases. If your system is not available it is also not functioning.

The connection between FRs and quality attributes can be made by identifying architecturally significant FRs [1]. Architecturally significant requirements need special attention as the wrong decision in terms of architecture might render the requirement unfulfillable.

How do you identify the quality attributes that are relevant for the stakeholders and your team? How do relevant quality attributes differ across your system or service landscape? In this blog post we will introduce a technique called mini-quality attributes workshop that helps to answer those questions. Afterwards we will explain a few common quality attributes in detail.

# Mini-Quality Attributes Workshop

## Overview

Quality attributes are used to evaluate the quality of a system. Wikipedia lists [82](https://en.wikipedia.org/wiki/List_of_system_quality_attributes) different quality attributes. Which attributes matter for you heavily depends on your situation and the different stakeholders of your system.

Michael Keeling describes mini-quality attributes workshops as an alternative to traditional quality attributes [2]. The goal of this workshop is to identify quality attributes that are important to the system stakeholders. Stakeholders typically are representative users, business experts, project managers, IT departments, and the development team.

The outcome of the workshop should be a list of quality attribute scenarios. Those scenarios are potentially refined and there might be some sort of prioritization already. The activity should be time-boxed and open points should be formulated as action items to follow-up with.

The main tool of the workshop is the *system properties web*, or *quality attributes web*. It allows clustering of quality attribute scenarios and is used also for dot-voting on attributes and/or scenarios throughout the workshop.

![quality attribute web example](https://thepracticaldev.s3.amazonaws.com/i/rlsbpnqpl8lkv7epnno4.png)

## Agenda

The workshop has the following points on the agenda:

1. **Introduce format.** This should state the agenda, explain the purpose and methodology of the meeting.
2. **Introduce Quality Attributes.** The second point should introduce the concept of quality attributes. To facilitate the discussion and save time it is useful to prepare a quality attribute taxonomy in advance that can be used as a base-line.
3. **Generate scenarios.** The next step should create as many scenarios as possible either by utilizing brain storming / brain writing techniques or a more structured approach moving along the taxonomy.
4. **Prioritize scenarios and quality attributes.** After generating scenarios they have to be prioritized in order to identify the ones that are important to refine and to tackle. Prioritizing quality attributes as well gives a general overview about priotities that can be used to take architectural decisions aligned with the quality requirements. Prioritization can be done using dot-voting.
5. **Refine scenarios.** The generated scenarios are typically created in an unstructured format. During refinement the goal is to transform raw scenarios into a structured format.
6. **Review.** The refined scenarios are presented to the stakeholders.

During the workshop it is very useful to finish at least the prioritization. The refinement should be time boxed, starting from the top priorities and can be taken offline if more time is required. Review can happen at a later stage in case you are running out of time.

## Scenarios

The quality attribute scenarios represent a core component of the workshop. Raw scenarios are a flexible, informal way to describe requirements with regards to quality. A raw scenario usually consists of a single sentence and gets assigned to a quality attribute by placing it inside the web. Here are a few examples:

- "Adding products to the shopping basket should always work." (Availability)
- "Browsing the portfolio should feel responsive." (Performance)

During the refinement step, raw scenarios are transformed into formal scenarios. A formal scenario has the following properties:

![formal scenario](https://thepracticaldev.s3.amazonaws.com/i/drncqw2gadbu7dcp9wjb.png)

The *source* describes who or what initiates the scenario. The *stimulus* is the event that initiates the scenario. The *artifact* represents the component that receives the stimulus and produces the response. The *response* is thus defined as the noticable result of the stimulus. The *response measure* contains a quantifiable, testable measurement of the response. The *environment* puts all the previous parts in context by describing the state of the system.

Let's refine the second raw scenario example from above:

![formal scenario example](https://thepracticaldev.s3.amazonaws.com/i/i3hs8ld5b7h4wbp0w03k.png)

When a user makes a request to the portfolio service under normal conditions, the portfolio service is supposed to answer with the portfolio within 200 ms in 99% of the cases. Specifying the environment is a crucial part, especially when scenarios are converted to service level objectives later on.

Next let's take a look at an exemplary quality attributes taxonomy you can use to facilitate the workshop.

# Generic Quality Attribute Taxonomy

The following taxonomy is inspired by a technical note from O’Brien et al. published under the Software Architecture Technology Initiative [3]. You can use it for your first workshop as a basis. I'm only going to mention each of the attributes and give a quick definition. Please refer to other sources for an extended explanation.

- **Interoperability** describes the ability of a service to communicate with other services and allow other services to communicate with it. It measures how freely information can be exchanged. Measures like programming language agnostic data formats, content negotiation, backwards compatible APIs, etc. can support interoperability between services.
- **Reliability** reflects the ability of a service to operate correctly. Automation to enable roll-backs and recovery can reduce the mean time between failure (MTBF).
- **Availability** is the ability of a service to answer to requests / be accessible. Uptime can be increased by adding fault-tolerance measures and resilience, e.g. through redundancy.
- **Usability** measures the quality of user experience (UX) a service provides. It can be increased by having a UX focused development workflow. As an unavailable or slow service is also not usable there is a strong dependency between usabiltiy and other attributes.
- **Security** has two major aspects: Confidentiality (access only granted to authorized users) and authenticity (trust the provided information). Helpful techniques are found in the area of cryptography, e.g. encryption and digital signatures. Additionally you should implement secure processes like regularly invalidating or rotating credentials or enforcing two factor authentication. Check how you are doing by executing regular penetration tests.
- **Performance** is a broad topic. In the context of services people often refer to response time or latency as a performance measure. It can be achieved by choosing the right algorithms and data structures for the problem and sizing the system according to the load. Add automated performance or load tests to detect regressions.
- **Scalability** describes the ability to deal with changes. When talking about scalability it is important to define what changes the system is reacting to, e.g. an increased number of users, new products offered in a shop, more requests coming in, or even more developers joining the company. Scalability is most commonly achieved by decoupling and separation of concerns in combination with choosing algorithms and data structures that allow a performance increase by adding more resources.
- **Extensibility** represents the ability to add functionality to a component without touching other components or parts of the system. Architectures that involve loose coupling, communication standards and evolution friendly interfaces and schemas promote extensibility.
- **Adaptability** influences how easy it is to change the system if requirements have changed. Similarly to extensibility this can be achieved by loose coupling, but also through abstraction, e.g. putting a layer between your database and application so you can exchange the database technology. Adaptability is also influenced by configurability.
- **Testability** matters when it comes to building and automating tests of individual components, interactions between components, as well as the system as a whole. In addition to that it is also crucial to know how well these tests can detect errors. Testability is especially hard in distributed systems or service oriented architectures, as components are connected through an unreliable network, different versions of services might exist, and there is no single entity that knows the internal state of all components. Note as well that behaviour of dynamic environments involving auto-scaling and service discovery might be hard to predict.
- **Auditability** captures the ability to perform audits of the system. Audits might be required for legal, security, or financial reasons, for example. Auditability is a tough goal as it requires all services involved in a process to be auditable. Generally, having immutable storage and versioning of events and data already contributes a great deal towards an auditable system.
- **Observability** expresses whether changes in a system are reflected, if possible, in a quantitative manner. Promoting a DevOps culture can increase observability because the team responsible for change is also responsible for operations, which greatly benefits from rich metrics being available.
- **Operability** characterizes the ease at which the system can be deployed and operated during runtime. Besides observability, operations can be supported by automation. Techniques like chaos engineering can put your operability to the test by introducing errors on purpose.

Note that many scenarios might fit to multiple attributes and scenarios can also relate to each other. In my opinion this is not an issue but instead facilitates the discussion about quality. Also keep in mind that there are many more possible quality attributes to include. If during the workshop you feel that others are more important than the ones mentioned here, simply extend, replace, or remove from the selection as necessary.

# Summary

In this post we have seen how your software architecture can influence not only the quality of your application but also functional requirements. There are no right solutions, instead it is always a trade-off between different quality attributes.

The mini-quality attributes workshop is a lightweight format to gather and prioritize quality attribute scenarios by your stake holders. Starting from collecting as many raw scenarios as possible, you will prioritize and refine the most important ones afterwards. The prioritization of quality attributes themselves enable you to pick the architecture and make the choices that facilitate the priorities of your stake holders.

Have you ever had a project where people did not talk about quality at all? Did your team ever take a decision in terms of software architecture that turned out to be a blocker for one of your functional requirements? If you think about your last project, what would you say were the two most important quality attributes and why? Feel free to leave comments!

# References

- [1] Keeling, M., 2018. Design It!. 1st ed.: Pragmatic Bookshelf.
- [2] Chaparro, W., Keeling, M., 2014. Facilitating the Mini-Quality Attributes Workshop ([PDF](https://resources.sei.cmu.edu/asset_files/Presentation/2014_017_101_89563.pdf))
- [3] O’Brien, L. et al., 2005. Quality Attributes and Service-Oriented Architectures. Technical Note: Software Architecture Technology Initiative ([PDF](https://resources.sei.cmu.edu/asset_files/TechnicalNote/2005_004_001_14489.pdf))
