---
title: Consumer-Driven Contract Testing with Pact
published: true
Description: Consumer-driven contract testing is an alternative to end-to-end tests. In this blog post we want to take a look at the basics of consumer-driven contract testing with Pact.
Tags: pact, tdd, javascript, kotlin
cover_image: https://thepracticaldev.s3.amazonaws.com/i/5d5pp1on3c6yn4c3az0z.jpg
canonical_url: https://blog.codecentric.de/en/2019/10/consumer-driven-contract-testing-with-pact/
series: pact
---

# Introduction

Consumer-driven contract testing is an alternative to end-to-end tests where not all services have to be deployed at the same time. It enables testing a distributed system in a decoupled way by decomposing service interactions into consumer and provider tests that can be executed independently.

[Pact](https://docs.pact.io/) is the de facto standard for consumer-driven contract testing. It is mainly used for testing request-response style interactions, e.g. communication between services via HTTP, but its specification also includes asynchronous interactions. The term consumer refers to a component making use of the data or functionality of another component which is referred to as the provider.

The [Pact specification](https://github.com/pact-foundation/pact-specification) defines a format to specify interactions in a way that they can be understood by consumers and providers independently of the programming language used. The specification is currently implemented in Ruby, JavaScript, Go, Python, Swift, PHP and available for JVM and .NET languages as well.

In this blog post we want to take a look at the basics of consumer-driven contract testing with Pact. The remainder of this post is structured as follows. First we will discuss the Pact workflow on a conceptual level. Afterwards we are going to see how to implement such a workflow, also giving minimal code examples for consumer and provider tests. The next section briefly discusses advantages and disadvantages of Pact. We are closing the post by summarizing the main findings and giving an outlook for the upcoming blog posts of this series.
# Pact Workflow
## Concepts

The consumer-driven contract testing workflow involves different entities and concepts. We want to look at the basic concepts in the following paragraphs, before we jump into the development workflow. We will use a toy example throughout the post for illustration purposes. Imagine a login form in a web application that is implemented as a JavaScript application using React with a Kotlin back-end to verify the credentials. The interactions we want to test are related to login and logout.

- **Consumer.** An application takes the role of a consumer as soon as it makes use of the functionality of another component, e.g. by initiating an HTTP request. In our example the React application would be the consumer of the login and logout functionality.
- **Provider.** The provider role involves offering functionality to other applications, e.g. by offering an HTTP API. In our example the back-end authentication service provides login and logout functionality.
- **Interaction.** An interaction defines what functionality is consumed and how. An HTTP interaction would include the request made from the consumer to the provider, the provider state at that time, as well as the response from the provider. A successful login would be modeled as one interaction.
- **Provider state.**  The provider state captures the state the provider is in during the interaction. States act as a test fixture in your provider tests, allowing you to mock your downstream services or configure your database. In our login example, there might be a state capturing that the user John Doe exists and has a specified password.
- **Contract / Pact file.** The contract, also known as Pact file, contains all interactions between a specific consumer and provider. In our example scenario there would be one contract between the front-end and the back-end containing all interactions with respect to login and logout.
- **Verification.** During the verification of a contract, the interactions defined in the Pact file are replayed against the provider code and the actual responses are compared with the expected ones defined in the contract. The verification result needs to be communicated to the developer of the consumer in some way.

Note that an application can (and most likely will) be both consumer and provider, depending on the interaction you are looking at. Frontends are typically consumers, but they can also be providers when you think about bidirectional communication over WebSocket, for example.

## Consumer Workflow

We are talking about consumer-driven contract testing, so let’s look at the consumer development workflow first. As a consumer you want to use some functionality that is provided by another application. Thus the first step is to specify the interactions you want to perform inside a Pact file.

While it is possible to create and edit your Pact files with a text editor, it is encouraged to write consumer tests instead. Consumer tests will not only verify your code but also generate the Pact file for all the interactions tested.

The next step is to execute the provider tests against your Pact file. If the provider verification is successful it means that the consumer version that generated the contract is compatible with the provider version that verified it. If both are deployed together their interactions should work as expected.

## Provider Workflow

Although Pact is consumer-driven it also adds benefits to the development workflow of providers. If you want to make a change to your API, for example, you can simply verify all existing contracts. If the verification is successful your change should not break any of the consumers and you can safely deploy the provider changes.

This enables providers to not only add new features but also remove deprecated functionality from their API without the fear to break existing functionality.

# Implementation
## Consumer Tests

A consumer test is typically written as follows. First you define your interactions. Then you pass them to the Pact library that will generate the Pact files and create a stub server for you that mimics the provider. Finally you can execute the consumer logic that will invoke the API and check if it works as expected.

We will use a concrete example implemented in JavaScript using [pact-js](https://github.com/pact-foundation/pact-js) and jest to illustrate how we can write a consumer test for our login endpoint.

```js
import { Interaction, Pact } from '@pact-foundation/pact';

const provider = new Pact(providerConfig);

const successfulLogin = new Interaction()
  .given('jane.doe has password baby1234')
  .uponReceiving('username jane.doe and password baby1234')
  .withRequest({
    method: 'POST',
    path: '/login',
    headers: {},
    body: {
      username: "jane.doe",
      password: "baby1234"
    }
  })
  .willRespondWith({
    status: 200
  });

await provider.addInteraction(interaction);

const response = await UserService.login({
  username: "jane.doe",
  password: "baby1234"
});

expect(response.status).toBe(200);
```

First we are setting up the provider. The provider config contains consumer and provider names for this contract as well as some options for the stub server such as the TCP port. Afterwards we are defining the interaction: Given a user with valid credentials, when we send those credentials the provider will respond with 200.

By adding this interaction to the provider we can then invoke the API and will receive a response as expected. How you invoke the API and what you actually test is up to you. In this case we are simply checking that the `UserService` calls the correct endpoint with the correct payload.

In a real world scenario your interactions will most likely look a bit more complex. Not only will you have more complex data but you might also take HTTP headers into account. Additionally it is possible to use matchers instead of exact expectations, i.e. you can pass any password as long as it is a string. This is useful when you want to use the stub server also for manual testing.

## Exchanging Pact Files

After the consumer has generated a new Pact file it needs to be shared with all respective providers for verification. There are different ways this can be achieved:

1. Commit Pact files to provider repository. The simplest variant of this workflow is to manually create a new PR with the changed interactions to the provider. Then your CI pipeline can execute the provider verification tests. Instead of manually creating a merge request you could automate this process, e.g. by letting the consumer build automatically committing the new interactions and creating a merge request.
2. Provider fetches Pact files. Instead of duplicating the Pact files into the provider repository the consumer can publish the interactions to a third party from where the provider can download them before each verification. This third party could be your build server artifact storage (e.g. Gitlab build artifacts), an object storage (e.g. Amazon S3), or the [Pact broker](https://docs.pact.io/getting_started/sharing_pacts).

Introducing the Pact broker as an intermediary has the additional benefit that the provider can also publish the verification results to the broker. Both consumers and providers can then query the broker for verification results to find out which versions are compatible and if it is safe to deploy a particular version to production.

Now that we have seen options to exchange Pact files between consumers and providers, let’s focus on the implementation of the provider verification tests next.
## Provider Tests

In order to verify a consumer contract, providers replay all interactions against their implementation using provider verification tests. They can be implemented in a different language than the consumer and we are going to verify our login interaction using Kotlin, JUnit 5, [pact-jvm](https://github.com/DiUS/pact-jvm) and mockk.

The following code block contains all basic concepts needed to implement a provider test.

```kotlin
@Provider("account-service")
@PactBroker
class ProviderVerificationTest {

  private val authenticationProvider = mockk<AuthenticationProvider>()

  @TestTemplate
  @ExtendWith(PactVerificationInvocationContextProvider::class)
  fun pactVerificationTest(pactContext: PactVerificationContext) {
    val service = AccountService(authenticationProvider)
    try {
      pactContext.verifyInteraction()
    } finally {
      clearAllMocks()
      service.shutdown()
    }
  }

  @State("jane.doe has password baby1234")
  fun `jane doe has password baby1234`() {
    every {
      authenticationProvider.authenticate("jane.doe", "baby1234")
    } returns true
  }

}
```

The class level annotation `@Provider` indicates that this is a provider test and it takes the provider name as an argument. The provider name is used to decide which interactions should be replayed. The `@PactBroker` annotation makes pact-jvm pull the contract from the Pact broker. If you committed the files to the provider repository you can use the `@PactFolder` annotation instead.

By defining a `@TestTemplate` method that is extended with a `PactVerificationInvocationContextProvider`, JUnit 5 will generate a test method for each of your interactions. In our case we are creating a new instance of our account service that will listen for HTTP requests. The `pactContext.verifyInteraction()` call will replay the interaction against your endpoint and check the response according to the contract definition.

Before each interaction is replayed, pact-jvm will execute all `@State` methods that are relevant for this interaction. This allows you to setup your mocks or fill your database based on the expected state before the interaction. In our case we simply tell the mocked authentication provider to accept the credentials that the interaction is going to send.

After all interactions have been verified, pact-jvm will report the verification results. It will also publish them to the Pact broker if configured. In case a verification failed you might want to adjust the interaction or implement new functionality in the provider to fulfill the new consumer contract.
# Discussion
We have learned about the Pact workflow and how to implement it. But should you use it for your new project? Should you include it into your existing codebase? The answer is, as always, it depends.

Pact works great if you feel the need to test your service interactions but do not want the complexity associated with full-blown end-to-end tests. Pact still adds complexity however. If you can get away with a monolithic application and can avoid interactions between distributed services, go for it. It will simplify your testing and development workflow a lot.

Nevertheless if you rely on independently developed distributed services to scale your development efforts across multiple teams, Pact will facilitate discussions between your teams, encourage API first design, and increase the confidence in deploying and evolving your APIs over time.

Contracts can also be used as API documentation by example. Similar to a unit test documenting the behaviour of your code by providing input together with expected output, interactions can be read by others to understand the API behaviour.

It is important to note that consumer-driven does not mean consumer-dictated. I observed situations in which consumers would simply publish new expectations about the providers to the other team and expect them to implement it like this. Of course consumers should drive the discussion and providers should respect contracts previously agreed on to avoid breaking their consumers. But Pact is not a tool to replace inter-team communication.

We do not recommend using Pact for public APIs with an unknown set of consumers. In this case it might be better to rely on a combination of [OpenAPI](https://swagger.io/specification/) and a tool like [Hikaku](https://github.com/codecentric/hikaku).

Independent of which Pact workflow you decide to implement, whether you are manually copying JSON files or using the Pact broker, make sure every developer understands the Pact concepts and is familiar with the workflow. Otherwise you risk frustration or bugs because you merged or deployed in the wrong order and now your integration broke although Pact was supposed to avoid that.

# Summary and Outlook

In this post we have seen how you can utilize Pact to test your distributed service interactions. Consumer tests generate expectations towards the provider in the form of Pact files. Providers have to verify those interactions through provider tests.

As the Pact specification is implemented in many different languages you can use Pact even if your services are written in different languages. Exchanging Pact files can be done in many different ways, ranging from manually committing them to the provider repository or using a third party service such as the Pact broker.

Pact can improve your confidence in evolving your APIs as long as all consumers are known and also following the same workflow. Pact does not work well for public APIs with unknown consumers.

In the upcoming post we will look at how you can use Pact in an asynchronous setup, e.g. in an event driven architecture. Have you used Pact before in any of your projects? How was your experience? Which setup worked and which did not? Please let us know in the comments!

---

Cover image by [Gunnar Wrobel](https://flic.kr/p/qQTMa)

This post was co-authored by [Raffael Stein](https://dev.to/rafaroca)
