---
title: How We Built a Serverless Backend Using GraalVM, AWS Lambda and Astra DB (Part 1)
published: true
description: How We Built a Serverless Backend Using GraalVM, AWS Lambda and Astra DB
tags: showdev, aws, cloud, lambda
cover_image: https://miro.medium.com/max/1400/0*KntVWFkkYYP5VMJV
canonical_url: https://medium.com/building-the-open-data-stack/how-we-built-a-serverless-backend-using-graalvm-aws-lambda-and-astra-db-part-1-829c4fbddbc
series: How We Built a Serverless Backend Using GraalVM, AWS Lambda and Astra DB
---

## Introduction

When the pandemic started, we set ourselves a learning goal: develop a backend using only serverless technologies. Initially, we set out to make this happen using technologies we were already familiar with, AWS Lambda and Java. But to spice things up, we decided to add some new technologies to the mix — GraalVM to eliminate the [JVM Lambda cold start problem](https://filia-aleks.medium.com/graalvm-aws-lambda-or-solving-java-cold-start-problem-2655eeee98c6), and [DataStax Astra DB](https://dtsx.io/3B5CmeR) as our serverless DBaaS.

So, we spent a couple of hours per week on building a serverless order processing API using Astra DB and AWS. Due to the pandemic, you could call it a distributed “hackathon” of sorts, in which we had three main challenges:

- Access Astra DB from within AWS Lambda
- Write automatic tests for our Astra DB client
- Set up the Lambda function to use the GraalVM native image runtime

In this first post, we will walk through the first two challenges and the technologies that helped us on the way, mainly [Stargate](https://dtsx.io/3aRyK5k) and [Testcontainers](https://www.testcontainers.org/). In the second post, we are going to dive into how we put our serverless API in the cloud using AWS API Gateway, AWS Lambda and [GraalVM](https://www.graalvm.org/). First, let’s take a look at the high level architecture.

## Architecture

To give you a better understanding of what we were going for, here’s a (rather simple) overview of the target architecture.

![Target architecture](https://miro.medium.com/max/1400/1*7vLCJruOsIAagek1CCBcoA.png)

Our end user accesses the API through an AWS API Gateway which is wired to our AWS Lambda function. The Lambda function in turn accesses the Astra DB Document API which is internally provided by Stargate.

[Amazon API Gateway](https://aws.amazon.com/api-gateway/) is a fully managed API service to create, publish, maintain, monitor, and secure APIs at any scale. Those APIs can be connected to a large number of different backend services.

[AWS Lambda](https://aws.amazon.com/lambda/) offers managed functions as a service (FaaS) based on micro virtual machines. To create a Lambda function you provide the code to execute, e.g. a Python script or a Jar file. The function can be invoked on demand based on a variety of triggers.

[Astra DB](https://dtsx.io/3B5CmeR) is a multi-cloud database-as-a-service (DBaaS) based on [Apache Cassandra™](https://cassandra.apache.org/_/index.html) that eliminates the overhead of installing, operating, and scaling your own database installation. Essentially, Astra DB helps developers reduce deployment time, costs, and nightmares. Astra DB also equips you with a few data APIs to build applications faster, which leads us to our next big player — Stargate.

[Stargate](https://dtsx.io/3aRyK5k) is an open source data gateway and the official data API for Astra DB. In short, it allows developers to connect to all their data with the APIs and tools they are used to. You can create tables and schemas and query data without learning Cassandra Query Language (CQL).

Now let’s take a closer look at the two goals we set ourselves for part one of this series.

## Goals

### Access Astra DB from Java

First of all, we had to figure out how to access Astra DB from within AWS Lambda with minimal dependencies. Lambda functions should be able to start as quickly as possible and we wanted to avoid bloating our [JAR file](https://docs.oracle.com/javase/tutorial/deployment/jar/basicsindex.html) with unnecessary dependencies.

Additionally, Lambda functions should be stateless, given that the runtime can be paused/frozen without notice for a longer period of time — or even destroyed completely. Although compared to other runtimes, such as Python, the [Java runtime appears to stay up](https://stackoverflow.com/questions/41850876/cassandra-database-session-reuse-in-aws-lambda-python) even between executions. But this behavior should not be counted on. To keep things simple, we accessed the Document API via an Apache HTTP client.

Another problem with AWS Lambda is you cannot easily perform database migrations. You have limited control over when your function is executed and how many instances are created. Also, if you migrate the schema on start, whenever someone uses your API for the first time they have to wait for your schema migration to finish first. This is why using the Document API, which doesn’t require specifying a schema upfront, was our best bet for accessing Astra DB from AWS Lambda.

### Test Astra DB client locally

Having the Java code to access Astra DB is great, but then how do we test it without spinning up an entire Cassandra cluster along with Stargate? Luckily, Stargate offers a [developer mode](https://dtsx.io/3IQbeCj), where the Stargate node behaves as a regular Cassandra node, joining the ring with tokens assigned to get started quickly without needing additional nodes or an existing cluster.

We can start a local Stargate node for our automated tests using Testcontainers. For the unfamiliar, [Testcontainers](https://www.testcontainers.org/) is a Java library that provides lightweight, throwaway instances of common databases or anything that can run in a Docker container. This essentially makes it easier to run tests for things like data access layer integration, app integration, UI/acceptance, and more.

## Getting into the code

The main functionality of our fictional API is to manage orders for an online shop. We need to save and retrieve orders. The class AstraClient encapsulates this functionality in the methods `saveOrder` and `getOrder`, respectively. Those methods interact with the document API.

To access our orders collection, we need to pass the Astra DB base URL, the access credentials, as well as the [namespace](https://dtsx.io/3yQm1rv) (also known as "keyspace" in the Cassandra realm).

```java

public class AstraClient {

  private final URI astraUrl;
  private final String astraToken;
  private final String astraNamespace;

  public AstraClient(URI astraUrl, String astraToken, String astraNamespace) {
    this.astraUrl = astraUrl;
    this.astraToken = astraToken;
    this.astraNamespace = astraNamespace;
  }

  public Optional<Order> getOrder(UUID orderId) {
    // ...
  }

  public Order saveOrder(Order order) throws IOException {
    // ...
  }
}
```

Next, we implement a simple test case that saves and then retrieves an order. For this, we create a new test class `AstraClientTest` annotated with @Testcontainers for the Testcontainers framework to manage the `@Container` lifecycle. We also implement a small test extension that manages namespace and token creation and provides our test class with an `AstraClient` instance.

```java
@Testcontainers
public class AstraClientTest {

  @Container
  GenericContainer stargate =
      new GenericContainer(DockerImageName.parse("stargateio/stargate-4_0:v1.0.25"))
          .withExposedPorts(8081, 8082)
          .withEnv("CLUSTER_NAME", "stargate")
          .withEnv("CLUSTER_VERSION", "4.0")
          .withEnv("DEVELOPER_MODE", "true")
          .withEnv("SIMPLE_SNITCH", "true");

  @RegisterExtension
  AstraTestExtension testExtension = new AstraTestExtension(stargate,
      "test");

  @Test
  public void shouldPersistAndRetrieveOrder() throws IOException {
    AstraClient astraClient = testExtension.getClient();

    Order order = new Order();
    order.setProductName("Googly Eyes");
    order.setProductQuantity(27);
    order.setProductPrice(99);

    Order savedOrder = astraClient.saveOrder(order);
    Optional<Order> result = astraClient.getOrder(savedOrder.getOrderId());

    assertThat(result).hasValue(order);
  }
}
```

Now, let’s dive into the stargate container definition. We start it in developer mode to act as a DB node. We also use [SimpleSnitch](https://dtsx.io/3PI9Wvv), since we do not need a particularly sophisticated snitch functionality.

By default, Stargate starts a CQL service on port 9042, a REST auth service for generating tokens on 8081, and an HTTP interface on port 8082. Since we used the Document API, we do not need to expose the CQL port.

Next, we implement a test method that persists and subsequently retrieves an order in `shouldPersistAndRetrieveOrder`. Our test extension generates a client that points to our Stargate container and has working credentials. We then use that to call `saveOrder` and `getOrder` in succession, validating that the retrieved order matches the originally stored one.

Before we dig into the details of the test extension, let’s cover the missing `AstraClient` functionality. To save and retrieve orders, we need a data class containing order data (let’s call it `Order`). To persist an order, we submit an HTTP POST request to the orders collection endpoint with the order JSON as payload. The response object contains the newly created document ID which we can use as our order ID.

```java
public Order saveOrder(Order order) throws IOException {
  URI uri = new URIBuilder(astraUrl)
      .appendPathSegments("v2", "namespaces", astraNamespace,
          "collections", "orders")
      .build();

  Response response = Request.post(uri)
      .addHeader("X-Cassandra-Token", astraToken)
      .body(HttpEntities.create(mapper.toJson(order), ContentType.APPLICATION_JSON))
      .execute();

  DocumentId documentId =
      mapper.fromJson(response.returnContent().asString(UTF_8), DocumentId.class);
  order.setOrderId(documentId.documentId);
  return order;
}
```

To retrieve an order, we submit an HTTP GET request to the document ID resource inside the orders collection. Our order will be wrapped inside a JSON object that contains the actual order in the data field. We model this wrapper in the `OrderDocument` class. The `getOrder` method returns an `Optional<Order>` which is empty in case the order doesn’t exist.

```java
public Optional<Order> getOrder(UUID orderId) {
  try {
    URI uri = new URIBuilder(astraUrl)
        .appendPathSegments("v2", "namespaces", astraNamespace,
            "collections", "orders", orderId.toString())
        .build();
    Response response = Request.get(uri)
        .addHeader("X-Cassandra-Token", astraToken)
        .execute();
    OrderDocument orderDoc = mapper.fromJson(
        response.returnContent().asString(UTF_8), OrderDocument.class);
    Order resultOrder = orderDoc.getData();
    resultOrder.setOrderId(orderDoc.getDocumentId());
    return Optional.of(orderDoc.getData());
  } catch (IOException | URISyntaxException e) {
    e.printStackTrace();
    return Optional.empty();
  }
}
```

At this point we can run our test and validate that the implemented functionality meets expectations. Now let’s take a look at the test extension. The following listing presents an outline of the class — it implements the `BeforeEachCallback` interface which tells JUnit to execute the `beforeEach` method before each test execution.

```java
public class AstraTestExtension implements BeforeEachCallback {

  private final Gson mapper = new Gson();
  private final GenericContainer stargate;
  private final String namespace;
  private volatile AstraClient client;
  private volatile URI astraUri;
  private volatile String authToken;

  public AstraTestExtension(GenericContainer stargate, String namespace) {
    this.stargate = stargate;
    this.namespace = namespace;
  }

  @Override
  public void beforeEach(ExtensionContext extensionContext) throws Exception {
    astraUri = new URIBuilder()
       .setScheme("http")
       .setHost(stargate.getContainerIpAddress())
       .setPort(stargate.getMappedPort(8082))
       .build();
    authToken = generateAuthToken();
    client = new AstraClient(astraUri, authToken, namespace);
    ensureNamespaceExists();
  }

  public AstraClient getClient() {
    return client;
  }

  public void ensureNamespaceExists() throws IOException {
    // Will be implemented below
  }

  public String generateAuthToken() throws IOException {
    // Will be implemented below
  }
}
```

In `beforeEach` we first generate an [auth token](https://dtsx.io/3aPv2sM). To do this, we call the Stargate auth endpoint and post the username and password via HTTP which then returns the auth token.

```java
public String generateAuthToken() throws IOException {
  URI uri = new URIBuilder()
      .setScheme("http")
      .setHost(stargate.getContainerIpAddress())
      .setPort(stargate.getMappedPort(8081))
      .setPathSegments("v1", "auth")
      .build();
  Response response = Request.post(uri)
      .body(HttpEntities.create(
          "{\"username\":\"cassandra\", \"password\":\"cassandra\"}",
          ContentType.APPLICATION_JSON))
      .execute();
  AuthToken authResult =
      mapper.fromJson(response.returnContent().asString(UTF_8), AuthToken.class);
  return authResult.authToken;
}
```

After passing the auth token to our `AstraClient`, we ensure the namespace (aka keyspace in Cassandra) exists. The production code assumes that the keyspace exists since we create it as part of our infrastructure provisioning code using the [DataStax Astra Terraform provider](https://dtsx.io/3B8KY42). In the test case we simply create the namespace via HTTP.

```java
public void ensureNamespaceExists() throws IOException {
  URI uri = new URIBuilder(astraUri)
      .setPathSegments("v2", "schemas", "namespaces").build();
  Request.post(uri)
      .body(HttpEntities.create(
          String.format("{\"name\":\"%s\"}", namespace),
          ContentType.APPLICATION_JSON))
      .addHeader("X-Cassandra-Token", authToken)
      .execute();
}
```

With that we conclude the code for this part of the "hackathon". So far we’ve successfully covered our first two goals: we implemented an `AstraClient` that uses the Astra DB Document API to store and retrieve orders. Then we tested our code using a custom JUnit 5 test extension along with the Testcontainers framework.

## What's next?

In the second part of this series we will show you how we implemented an AWS Lambda handler that accepts HTTP requests from AWS API Gateway, transforms them into Astra DB requests using our AstraClient class, and returns a response to the user. The handler is written to run in a GraalVM native runtime which minimizes those pesky cold start issues we always bumped into with the default Java runtime.

Stay tuned for the next post to continue our tour of the technologies, challenges, and workarounds involved in getting our serverless API into production!

In the meantime, you can poke around the [source code](https://github.com/codecentric/serverless-astra-graalvm) for this project in GitHub. If you have any questions or want to know more about this project, head over to the [DataStax Community](https://dtsx.io/3PngYGe) and we’ll meet you there. To reach one of us in particular you can find us on Twitter [@FRosnerd](https://twitter.com/FRosnerd) and [@raffael](https://twitter.com/raffael).
