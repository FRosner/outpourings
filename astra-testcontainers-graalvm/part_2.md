---
title: How We Built a Serverless Backend Using GraalVM, AWS Lambda and Astra DB (Part 2)
published: true
description: In this article, we continue the series of building a serverless backend using GraalVM, AWS Lambda, and Astra DB by completing the last goal of setting up a Lambda function to use the GraalVM native image runtime.
tags: showdev, aws, cloud, lambda
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/qq9pye73g4e26kj79fpm.png
canonical_url: https://medium.com/building-the-open-data-stack/how-we-built-a-serverless-backend-using-graalvm-aws-lambda-and-astra-db-part-2-14a078437020
series: How We Built a Serverless Backend Using GraalVM, AWS Lambda and Astra DB
---

## Introduction

In this two-part blog series, we’re building a serverless order processing API using Astra DB and AWS. As you might recall from the first part, we set ourselves three goals:

- Access Astra DB from within AWS Lambda.
- Write automatic tests for our Astra DB client.
- Set up the Lambda function to use the GraalVM native image runtime.

Let us recall the application architecture and review what’s still missing. So far, we’ve accomplished the first two goals and successfully implemented and tested an Astra Client that we can use inside our AWS Lambda function.

![](https://miro.medium.com/v2/resize:fit:1400/format:webp/1*WgJK4LCY6fNqMlaYep9obw.png)

We can now focus on the third goal: implementing the Lambda function and running it inside a [GraalVM](https://www.graalvm.org/) native image runtime. We’ll also hook it up to API Gateway, so that the end user can call it via an HTTP API. The [complete source code](https://github.com/codecentric/serverless-astra-graalvm) is available on GitHub.

## Implementation

### Lambda handler

In order to process incoming API Gateway requests via [AWS Lambda](https://docs.aws.amazon.com/lambda/index.html), we need to implement a `RequestHandler<APIGatewayV2HTTPEvent, LambdaResponse>` which creates and uses our `AstraClient`.

`APIGatewayV2HTTPEvent` is implemented in the `aws-lambda-java-events` dependency and contains a JSON representation of an HTTP request. `LambdaResponse` is a simple data class we wrote that captures HTTP response fields we want to use: body and status code. You can find more information about the event and response format in the [official documentation](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html).

The following code shows a very simple handler implementation that decodes the incoming payload into an Order object and stores it in [Astra DB](https://dtsx.io/3D10IXd). If the operation was successful, we return the respective order ID. Otherwise, we return an error.

```java
public class LambdaHandler implements RequestHandler<APIGatewayV2HTTPEvent, LambdaResponse> {

  private static final Gson mapper = new Gson();

  private static final AstraClient astraClient = newAstraClientFromEnv();

  private static AstraClient newAstraClientFromEnv() {
    String astraUrl = System.getenv("ASTRA_URL");
    String astraToken = System.getenv("ASTRA_TOKEN");
    String astraNamespace = System.getenv("ASTRA_NAMESPACE");
    return new AstraClient(URI.create(astraUrl), astraToken, astraNamespace);
  }

  @Override
  public LambdaResponse handleRequest(APIGatewayV2HTTPEvent input, Context context) {
    if (input.getRouteKey().startsWith("GET")) {
      String orderIdRaw = input.getPathParameters().get("orderId");
      UUID orderId = UUID.fromString(orderIdRaw);
      Optional<Order> order = astraClient.getOrder(orderId);
      if (order.isEmpty()) {
        return new LambdaResponse();
      }
      return new LambdaResponse(order.get());

    } else if (input.getRouteKey().startsWith("POST")) {
      Order requestOrder = null;
      try {
        byte[] decodedRequest = base64DecodeApiGatewayEvent(input);
        requestOrder = mapper.fromJson(new String(decodedRequest), Order.class);
        Order savedOrder = astraClient.saveOrder(requestOrder);
        LambdaResponse lambdaResponse = new LambdaResponse(savedOrder);
        return lambdaResponse;
      } catch (Exception e) {
        logger.log("Could not save input '" + input + "' as order '" + requestOrder);
        logger.log("Exception was: " + e.getLocalizedMessage());
        return new LambdaResponse(
          "{ \"message\": \"Order could not be saved.\" }",
          SC_BAD_REQUEST);
  	}
    } else {
      return new LambdaResponse(
        "{ \"message\": \"HTTP method is not supported.\" }",
        SC_BAD_REQUEST);
    }
  }

  private byte[] base64DecodeApiGatewayEvent(APIGatewayV2HTTPEvent input) {
    byte[] decodedRequest;
    if (input.getIsBase64Encoded()) {
      decodedRequest = Base64.decodeBase64(input.getBody());
    } else {
      String body = input.getBody();
      decodedRequest = body != null ? body.getBytes(UTF_8) : null;
    }
    return decodedRequest;
  }
}
```

Now that we successfully implemented our Lambda handler, we will look into building and packaging it so it can be executed inside a [GraalVM](https://www.graalvm.org/) native runtime.

### Build steps

The goal of our build pipeline will be to generate a Lambda runtime package since we have to provide the entire runtime to AWS Lambda if we want to use GraalVM native code.

We’re going to use [Maven](https://maven.apache.org/) as our build tool, and we’ll combine the following Maven plugins and dependencies to generate the runtime package:

- `lambda-runtime-graalvm` (dependency) to generate the custom Lambda runtime.
- `native-image-maven-plugin` (plugin) to generate the native GraalVM image.
- `maven-assembly-plugin` (plugin) to package everything into a zip file.
- `git-commit-id-plugin` (plugin) to tag the zip file with the commit hash.

Let’s dive into each component in detail.

### Custom Lambda runtime

By including the dependency `lambda-runtime-graalvm`, we’re adding the class `com.formkiq.lambda.runtime.graalvm.LambdaRuntime`, which is the main class for the native image.

```xml
<dependency>
  <groupId>com.formkiq</groupId>
  <artifactId>lambda-runtime-graalvm</artifactId>
  <version>${lambdaRuntime.version}</version>
</dependency>
```

It does everything a custom runtime needs to do, including the invocation of our Lambda handler function with the event payload. Please consult the [Custom AWS Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html#runtimes-custom-build) documentation for more information on how to build custom runtimes from scratch.

### Building the GraalVM native image

Next, we configure the `native-image-maven-plugin`. The following listing contains the plugin definition. We’ll go over it in more detail in the upcoming paragraphs.

```xml
<plugin>
  <groupId>org.graalvm.nativeimage</groupId>
  <artifactId>native-image-maven-plugin</artifactId>
  <version>${graalvm.version}</version>
  <executions>
    <execution>
      <goals>
        <goal>native-image</goal>
      </goals>
      <phase>package</phase>
    </execution>
  </executions>
  <configuration>
    <skip>false</skip>
    <imageName>serverless-astra-graalvm</imageName>
    <mainClass>com.formkiq.lambda.runtime.graalvm.LambdaRuntime</mainClass>
    <buildArgs>
      <buildArg>--no-fallback</buildArg>
      <buildArg>--enable-url-protocols=http</buildArg>
      <buildArg>-H:ReflectionConfigurationFiles=../src/main/resources/reflect.json</buildArg>
      <buildArg>--no-server</buildArg>
    </buildArgs>
  </configuration>
</plugin>
```

In the `executions` section, we include the `native-image` goal as part of the `package` phase, which will invoke via `./mvnw package`. In terms of plugin configuration, we’ll define an image name and the main class, which we pulled in via `lambda-runtime-graalvm` in the previous section.

Once you build a native image, it only includes code that is reachable from the configured main class, which will break some dynamic features offered by the JVM, such as reflection and URL protocols. To make sure our application works nevertheless, we need to pass a couple of build arguments:

- `--no-fallback` makes sure we get a standalone image, or the build fails.
- `--enable-url-protocols=http` enables HTTP support.
- `-H:ReflectionConfigurationFiles=../src/main/resources/reflect.json` specifies the configuration file which contains all reflective accesses our application might perform.
- `--no-server` tells the builder not to start a dedicated build server but instead build the image in the builder process.

For more information on native-image build arguments, please consult the GraalVM [Native Image Options](https://www.graalvm.org/22.0/reference-manual/native-image/Options/) documentation. The next listing contains the contents of `reflect.json`, which contains a bunch of data classes that we need to serialize and deserialize with [Gson](https://github.com/google/gson), as well as our Lambda handler class which the runtime needs to instantiate based on the qualified class name passed to the Lambda function.

```json
[
  {
    "name": "com.github.codecentric.LambdaHandler",
    "allPublicConstructors": true,
    "allPublicMethods": true
  },
  {
    "name": "com.github.codecentric.Order",
    "allPublicConstructors": true,
    "allDeclaredFields": true
  },
  {
    "name": "com.github.codecentric.LambdaResponse",
    "allPublicConstructors": true,
    "allDeclaredFields": true
  },
  {
    "name": "com.github.codecentric.OrderDocument",
    "allPublicConstructors": true,
    "allDeclaredFields": true
  },
  {
    "name": "com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent",
    "allPublicConstructors": true,
    "allDeclaredFields": true
  },
  {
    "name": "com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent$RequestContext",
    "allPublicConstructors": true,
    "allDeclaredFields": true
  },
  {
    "name": "com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent$RequestContext$Http",
    "allPublicConstructors": true,
    "allDeclaredFields": true
  }
]
```

Now that we can build our Lambda runtime as a GraalVM native image, we only need to package it into an archive which we can upload to AWS Lambda.

### Zipping it up

Packaging the native image in a zip file will be done with the `maven-assembly-plugin`. Analogous to the native-image plugin, we will execute the plugin goal as part of the `package` phase.

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-assembly-plugin</artifactId>
  <version>2.2-beta-5</version>
  <configuration>
    <finalName>${project.artifactId}-${git.commit.id.abbrev}</finalName>
  </configuration>
  <executions>
    <execution>
      <phase>package</phase>
      <goals>
        <goal>single</goal>
      </goals>
      <configuration>
        <appendAssemblyId>false</appendAssemblyId>
        <descriptors>
          <descriptor>assembly.xml</descriptor>
        </descriptors>
      </configuration>
    </execution>
  </executions>
</plugin>
```

The file `assembly.xml` contains the output file format (zip) and defines what we’re zipping.

```xml
<assembly xmlns="http://maven.apache.org/plugins/maven-assembly-plugin/assembly/1.1.2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://maven.apache.org/plugins/maven-assembly-plugin/assembly/1.1.2 http://maven.apache.org/xsd/assembly-1.1.2.xsd">
  <id>zip</id>
  <includeBaseDirectory>false</includeBaseDirectory>

  <formats>
    <format>zip</format>
  </formats>
  <files>
    <file>
      <source>${project.build.directory}/${project.artifactId}</source>
      <outputDirectory>/</outputDirectory>
    </file>
    <file>
      <source>bin/bootstrap</source>
      <outputDirectory>/</outputDirectory>
    </file>
  </files>
</assembly>
```

The zip file name will have the git commit appended to make it easier to distinguish different packages when we update our Lambda function. The variable `${git.commit.id.abbrev}` is defined by the `git-commit-id-plugin`.

```xml
<plugin>
  <groupId>pl.project13.maven</groupId>
  <artifactId>git-commit-id-plugin</artifactId>
  <version>4.0.4</version>
  <executions>
    <execution>
      <goals>
        <goal>revision</goal>
      </goals>
      <phase>validate</phase>
    </execution>
  </executions>
  <configuration>
    <dotGitDirectory>${project.basedir}/.git</dotGitDirectory>
  </configuration>
</plugin>
```

Now running `./mvnw package` generates the Lambda zip file. The next section covers creating the Lambda function and API Gateway resources to deploy and wire everything together.

## Infrastructure

In order to create our infrastructure, we are using [Terraform](https://www.terraform.io/). Terraform is also used to create our Astra DB instance using the [DataStax Astra Provider](https://registry.terraform.io/providers/datastax/astra/latest/docs), but we’ll not discuss it in this post. Please check out the blog post, [Let’s Get Started With Terraform for Astra DB](https://dtsx.io/3QX5las), for more information on the DataStax Astra Provider.

### Lambda

The Lambda function resource and surrounding resources are created through the `terraform-aws-modules/lambda/aws` module. The following snippet contains the `lambda_function` module definition.

```tf
module "lambda_function" {
  source = "terraform-aws-modules/lambda/aws"
  version = "2.1.0"

  function_name = var.project_name
  handler = "com.github.codecentric.LambdaHandler::handleRequest"
  runtime = "provided"

  create_package = false
  local_existing_package = "../target/serverless-astra-graalvm-${local.git-short-sha}.zip"
  timeout = 30

  tags = {
    Name = var.project_name
    Version = local.git-short-sha
  }

  environment_variables = {
    ASTRA_URL = "https://${astra_database.main.id}-${astra_database.main.region}.apps.astra.datastax.com/api/rest"
    ASTRA_TOKEN = var.astra_db_client_token
    ASTRA_NAMESPACE = astra_database.main.keyspace
  }
}
```

The important properties of the module are:

- Our native runtime image zip file.
- The handler function.
- Environment variables holding the credentials.

It’s good practice to manage the credentials in a secret store, such as AWS Secrets Manager. For simplicity’s sake, they are passed as Terraform variables here.

### API Gateway

With the Lambda function in place, let’s create the API Gateway resources to call our function via HTTP. This requires an API (`aws_apigatewayv2_api`), a stage (`aws_apigatewayv2_stage`), an integration (`aws_apigatewayv2_integration`), as well as two routes (`aws_apigatewayv2_route`).

The API defines the protocol type HTTP:

```tf
resource "aws_apigatewayv2_api" "api-gateway" {
  name = "serverless-graal-http-api"
  protocol_type = "HTTP"
}
```

For this pet project, we will only need one stage:

```tf
resource "aws_apigatewayv2_stage" "dev-stage" {
  api_id = aws_apigatewayv2_api.api-gateway.id
  name = "$default"
  auto_deploy = true
}
```

The integration allows our routes to invoke our Lambda function:

```tf
resource "aws_apigatewayv2_integration" "api-gateway" {
  api_id = aws_apigatewayv2_api.api-gateway.id
  integration_uri = module.lambda_function.lambda_function_invoke_arn
  integration_type = "AWS_PROXY"
  integration_method = "POST"
  payload_format_version = "2.0"
}
```

We require two routes, one for order retrieval (`api-gateway-get`) and one for order persistence (`api-gateway-post`):

```tf
resource "aws_apigatewayv2_route" "api-gateway-get" {
  api_id = aws_apigatewayv2_api.api-gateway.id
  route_key = "GET /order/{orderId}"
  target = "integrations/${aws_apigatewayv2_integration.api-gateway.id}"
}

resource "aws_apigatewayv2_route" "api-gateway-post" {
  api_id = aws_apigatewayv2_api.api-gateway.id
  route_key = "POST /order"
  target = "integrations/${aws_apigatewayv2_integration.api-gateway.id}"
}
```

And that’s it! Now, after applying the Terraform plan, we can use our serverless order API.

## Demo

We use the `terraform apply` command to create the entire infrastructure, including the API gateway, the Lambda function, and the Astra database.

```
$ terraform apply --auto-approve
astra_database.main: Creating...
aws_apigatewayv2_api.api-gateway: Creating...
module.lambda_function.aws_iam_role.lambda[0]: Creating...
module.lambda_function.aws_cloudwatch_log_group.lambda[0]: Creating...
module.lambda_function.aws_iam_role.lambda[0]: Creation complete after 1s [id=serverless-astra-graalvm]
module.lambda_function.aws_cloudwatch_log_group.lambda[0]: Creation complete after 2s [id=/aws/lambda/serverless-astra-graalvm]
module.lambda_function.data.aws_iam_policy_document.logs[0]: Reading...
module.lambda_function.data.aws_iam_policy_document.logs[0]: Read complete after 0s [id=3519125711]
module.lambda_function.aws_iam_policy.logs[0]: Creating...
aws_apigatewayv2_api.api-gateway: Creation complete after 2s [id=fkxcduwzd1]
aws_apigatewayv2_stage.dev-stage: Creating...
module.lambda_function.aws_iam_policy.logs[0]: Creation complete after 0s [id=arn:aws:iam::***:policy/serverless-astra-graalvm-logs]
module.lambda_function.aws_iam_policy_attachment.logs[0]: Creating...
module.lambda_function.aws_iam_policy_attachment.logs[0]: Creation complete after 1s [id=serverless-astra-graalvm-logs]
aws_apigatewayv2_stage.dev-stage: Creation complete after 2s [id=$default]
astra_database.main: Still creating... [10s elapsed]
...
astra_database.main: Still creating... [1m10s elapsed]
astra_database.main: Creation complete after 1m19s [id=efae102e-0708-4233-a11f-b7e64422e221]
module.lambda_function.aws_lambda_function.this[0]: Creating...
module.lambda_function.aws_lambda_function.this[0]: Creation complete after 9s [id=serverless-astra-graalvm]
aws_apigatewayv2_integration.api-gateway: Creating...
aws_apigatewayv2_integration.api-gateway: Creation complete after 1s [id=qx9878r]
aws_apigatewayv2_route.api-gateway-get: Creating...
aws_apigatewayv2_route.api-gateway-post: Creating...
aws_apigatewayv2_route.api-gateway-post: Creation complete after 1s [id=x1u1rjm]
aws_apigatewayv2_route.api-gateway-get: Creation complete after 1s [id=3ceq7q3]

Apply complete! Resources: 11 added, 0 changed, 0 destroyed.

Outputs:

aws_api_gateway = "https://flsreywmp1.execute-api.eu-west-1.amazonaws.com"
```

Terraform plans the necessary changes and — due to the `--autoapprove` flag — immediately takes action. After completing the Terraform command, all our components are ready to be used. The Outputs section shows us the URL of our API gateway endpoint. We can invoke our API by sending JSON queries via the curl command.

```bash
$ curl \
  --header 'Content-Type: application/json' \
  --data '{"productName": "googly eyes", "productQuantity": 3, "productPrice": 199}' \
  https://9p8328wdcg.execute-api.eu-west-1.amazonaws.com/order
  
# {"orderId":"15249e2d-57c5-4fdd-a076-be64812b2739","productName":"googly eyes","productQuantity":3,"productPrice":199}
```

Our `/order` endpoint accepts a JSON document containing order details. It persists the order in Astra DB and returns the persisted object, which now contains an `orderId`. Now we can use `curl` to retrieve the order again.

```bash
$ curl https://9p8328wdcg.execute-api.eu-west-1.amazonaws.com/order/15249e2d-57c5-4fdd-a076-be64812b2739

# {"orderId":"15249e2d-57c5-4fdd-a076-be64812b2739","productName":"googly eyes","productQuantity":3,"productPrice":199}
```

## Conclusion

This concludes our two-part series of developing a backend using serverless technologies. In [Part 1](https://dtsx.io/3QUAP0V) we successfully implemented and tested an Astra Client that we can use inside our AWS Lambda function. Part 2 shows how you can implement the Lambda function and run it inside a GraalVM native image runtime.

You can look at the entire project over on [Github](https://github.com/codecentric/serverless-astra-graalvm), and if you have any questions or want to know more about this project, feel free to reach out to us at [@FRosnerd](https://twitter.com/FRosnerd) and [@raffael](https://twitter.com/raffael) on Twitter.

*Follow the [DataStax Tech Blog](https://dtsx.io/3WyXPnb) for more developer stories. Check out our [YouTube](https://dtsx.io/3QYV2m5) channel for tutorials, and follow DataStax Developers on [Twitter](https://dtsx.io/3D7EwKZ) for the latest news about our developer community.*

Resources:
- [Part 1 — How We Built a Serverless Backend Using GraalVM, AWS Lambda and Astra DB](https://dtsx.io/3QUAP0V)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/index.html)
- [Using AWS Lambda with Amazon API Gateway](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html)
- [Astra DB](https://dtsx.io/3D10IXd)
- [GraalVM](https://www.graalvm.org/)
- [Apache Maven](https://maven.apache.org/)
- [Custom AWS Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html#runtimes-custom-build)
- [GraalVM Native Image Options](https://www.graalvm.org/22.0/reference-manual/native-image/Options/)
- [Gson](https://github.com/google/gson)
- [Terraform](https://www.terraform.io/)
- [Let’s Get Started with Terraform for Astra DB](https://dtsx.io/3QX5las)
- [Datastax](https://medium.com/tag/datastax?source=post_page-----14a078437020---------------datastax-----------------)
- [Serverless](https://medium.com/tag/serverless?source=post_page-----14a078437020---------------serverless-----------------)
- [Backend](https://medium.com/tag/backend?source=post_page-----14a078437020---------------backend-----------------)
- [AWS](https://medium.com/tag/aws?source=post_page-----14a078437020---------------aws-----------------)
- [Terraform](https://medium.com/tag/terraform?source=post_page-----14a078437020---------------terraform-----------------)