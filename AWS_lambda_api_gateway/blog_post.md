---
title: Deploying an HTTP API on AWS using Lambda and API Gateway
published: true
description: In this blog post we want to take a look at how to deploy a simple "serverless" web application on AWS using Lambda, API Gateway, and S3.
tags: aws, devops, serverless, cloud
cover_image: https://thepracticaldev.s3.amazonaws.com/i/cp9w21o1oisumbgtcqsw.png
---

This blog post is part of my AWS series:

- [Infrastructure as Code - Managing AWS With Terraform](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o)
- [**Deploying an HTTP API on AWS using Lambda and API Gateway**](#)
- [Deploying an HTTP API on AWS using Elastic Beanstalk](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-elastic-beanstalk-5dh7)
- [Deploying and Benchmarking an AWS RDS MySQL Instance](https://dev.to/frosnerd/deploying-and-benchmarking-an-aws-rds-mysql-instance-2faf)
- [Event Handling in AWS using SNS, SQS, and Lambda](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng)

# Introduction

With the rise of cloud platforms like [Amazon Web Services](https://aws.amazon.com) (AWS), [Google Cloud Platform](http://cloud.google.com/) (GCP), or [Microsoft Azure](https://azure.microsoft.com/en-en/services/app-service/), it has become increasingly popular to use managed infrastructure and services instead of hosting your own. In my [last blog post](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o) we looked at the concept of *Infrastructure as a Service* (IaaS).

While managing virtual machines instead of bare metal hardware in your own datacenter already provides a lot of benefits, it still implies significant maintenance overhead. In order to run a simple web application you have to take care about operating system updates, managing software packages, and so on.

To this date a higher abstraction called *Platform as a Service* (PaaS) has gained momentum, as it allows you to deploy applications without caring about the machine it is being run on. There are multiple services who accomplish this by offering managed application containers, e.g. [AWS ECS](https://eu-central-1.console.aws.amazon.com/ecs/home?region=eu-central-1#/getStarted), [GCP Kubernetes Engine](https://cloud.google.com/kubernetes-engine/), [Microsoft Azure App Service](https://azure.microsoft.com/en-gb/services/app-service/), or [Heroku](https://www.heroku.com/).

But why stop there? Why do you need to worry about the environment your code is being run on? What if you could simply define your function and deploy it to the cloud? This is where the next buzzword comes in: *Serverless*.

> Serverless architectures are application designs that incorporate third-party “Backend as a Service” (BaaS) services, and/or that include custom code run in managed, ephemeral containers on a “Functions as a Service” (FaaS) platform. [1]

When working on AWS, serverless is often used as a synonym for AWS Lambda. In this blog post we want to take a look at how to deploy a simple "serverless" web application on AWS using Lambda, API Gateway, and S3. We are going to use Terraform to manage our resources.

The post is structured as follows. First we introduce the target architecture, explaining the different components on a conceptual level. The next section discusses the implementation of the different components and how they are wired together. We are closing the post by summarizing and discussing the main findings.

# Architecture

## Overview

The following figure illustrates the target architecture. The client sends an HTTP request to the API Gateway. The gateway will enrich and forward that request to a Lambda function. The function definition is stored on S3 and loaded dynamically. The result of the Lambda function will be processed by the API Gateway, which is returning a corresponding response to the client.

![architecture](https://thepracticaldev.s3.amazonaws.com/i/0lexbp7wacyq34etri3h.png)

In our concrete example we are going to develop the program logic in Scala. The assembled `jar` file will be published to S3 and used to process the requests. We will now briefly introduce the individual components on a conceptual level.

## AWS Lambda

[AWS Lambda](https://aws.amazon.com/lambda) is the FaaS offering from AWS. It runs your predefined functions in response to certain events and automatically manages the platform and resources.

Lambda functions can be used to process requests coming through the API Gateway, or react to changes in your data, e.g. updates in DynamoDB, modifications in an S3 bucket, or data loaded into a Kinesis stream.

Currently the following [runtimes](https://docs.aws.amazon.com/lambda/latest/dg/current-supported-versions.html) are supported:

- Node.js
- Java
- Python
- .NET
- Go

In our case we are going to use the Java runtime to execute our Scala service.

## AWS API Gateway

[AWS API Gateway](https://aws.amazon.com/api-gateway) is an AWS service for managing APIs. It can act as a secure and scalable entry point for your applications, forwarding the requests to the appropriate back-end service. API Gateway can also manage authorization, access control, monitoring, and API version management.

The API interfaces with the backend by means of integration requests and integration responses. It does not act as a simple proxy but requires certain response parameters from the integrated back-ends.

## AWS S3

[AWS S3](https://aws.amazon.com/s3/) is an object storage provided by AWS. Objects themselves can be anything, e.g. an HTML file, a ZIP file, or a picture.

Objects are organized in so called *buckets*, which act as global namespaces. Inside each bucket, your object will be addressed by a hierarchical key. The URL `s3.eu-central-1.amazonaws.com/usa-trip/images/feelsbadman.jpg` would be used to access the object `/images/feelsbadman.jpg` inside the `usa-trip` bucket, stored within the `eu-central-1` region.

Enough architecture, let's look at the implementation.

# Implementation

## Development Tool Stack

To develop the solution we are using the following tools:

- Terraform v0.11.7
- SBT 1.0.4
- Scala 2.12.6
- IntelliJ + Scala Plugin + Terraform Plugin

The [source code](https://github.com/FRosner/lambda-vs-beanstalk) is available on GitHub. Note however that the project contains two modules, one for the AWS Lambda deployment and another one where I am experimenting with [AWS Elastic Beanstalk](https://aws.amazon.com/elasticbeanstalk/).

## Vanilla Lambda Function

A vanilla AWS Lambda function implemented in Scala is just a simple class or object method. As AWS Lambda only knows about Java and not Scala, we have to stick to Java types. Here is what a function returning a list of four names looks like:

```scala
package de.frosner.elbvsl.lambda

import scala.collection.JavaConverters._

object Main {
  def getCustomers: java.util.List[String] =
    List("Frank", "Lars", "Ross", "Paul").asJava
}
```

Next thing we need to do is to package that function and make it available for AWS Lambda. A convenient way to do that is to use the [sbt-assembly](https://github.com/sbt/sbt-assembly) plugin to build a fat `jar` and upload it to S3 using the [fm-sbt-s3-resolver](https://github.com/frugalmechanic/fm-sbt-s3-resolver).

In order to make the `sbt publish` task do what we want, we add the following settings to our `build.sbt` file:

```scala
publishTo := Some("S3" at "s3://s3-eu-central-1.amazonaws.com/lambda-elb-test/lambda")
artifact in (Compile, assembly) := {
  val art = (artifact in (Compile, assembly)).value
  art.withClassifier(Some("assembly"))
}
addArtifact(artifact in (Compile, assembly), assembly)
```

Don't forget to provide [valid credentials](https://github.com/frugalmechanic/fm-sbt-s3-resolver#s3-credentials). This is what we get when running `sbt publish`:

```
...
[info] Packaging /Users/frosner/Documents/projects/lambda_vs_beanstalk/lambda/target/scala-2.12/elastic-beanstalk-vs-lambda-assembly-0.1-SNAPSHOT.jar ...
[info] Done packaging.
[info] S3URLHandler - Looking up AWS Credentials for bucket: lambda-elb-test ...
[info] S3URLHandler - Using AWS Access Key Id: <obfuscated> for bucket: lambda-elb-test
[info] S3URLHandler - Created S3 Client for bucket: lambda-elb-test and region: eu-central-1
...
[info] 	published elastic-beanstalk-vs-lambda_2.12 to s3://s3-eu-central-1.amazonaws.com/lambda-elb-test/lambda/de/frosner/elastic-beanstalk-vs-lambda_2.12/0.1-SNAPSHOT/elastic-beanstalk-vs-lambda_2.12-0.1-SNAPSHOT-assembly.jar
```

Now we can create the Lambda function using Terraform. If you are not familiar with how Terraform works, I recommend to take a look at my previous blog post: [Infrastructure as Code - Managing AWS With Terraform](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o).

In order to create a new Lambda function, we need to provide the following information:

- Location of the `jar` file, i.e. our S3 object
- Runtime to execute the function, i.e. Java 8
- Handler to start, i.e. our `getCustomers` function
- [IAM role](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html) to use for execution

In addition we can also provide memory requirements. Our app shouldn't need more than the default of 128 MB. However AWS Lambda assigns CPU resources proportional to the configured memory and with 128 MB the Lambda function times out as the class loading during JVM startup takes too much time 🤦.

The IAM role we are using does not have any policies attached to it, as our function does not need to access any other AWS services. The following listing shows the Terraform file required to define the Lambda function.

```conf
variable "version" {
  type = "string"
  default = "0.1-SNAPSHOT"
}

resource "aws_lambda_function" "lambda-elb-test-lambda" {
  function_name = "lambda-elb-test"

  s3_bucket = "lambda-elb-test"
  s3_key    = "lambda/de/frosner/elastic-beanstalk-vs-lambda_2.12/${var.version}/elastic-beanstalk-vs-lambda_2.12-${var.version}-assembly.jar"

  handler = "de.frosner.elbvsl.lambda.Main::getCustomers"
  runtime = "java8"

  role = "${aws_iam_role.lambda_exec.arn}"

  memory_size = 1024
}

resource "aws_iam_role" "lambda_exec" {
  name = "lambda-elb-test_lambda"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}
```

We now have an AWS Lambda function defined that can be invoked by certain triggers. In our example we want to invoke it through the API Gateway. In order to do that however, we need to modify the Lambda function to make it return an integration response that is compatible with the [expected format](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-create-api-as-simple-proxy-for-lambda.html#api-gateway-proxy-integration-create-lambda-backend) of the API Gateway.

## API Gateway Lambda Function

In the vanilla Scala function our inputs and outputs were simple Java objects. In order to be invoked by the API Gateway correctly, our handler has to return a JSON string instead. This is how it might look:

```json
{
  "statusCode": 200,
  "isBase64Encoded": false,
  "headers": {
    "my-header-key": "my-header-value"
  },
  "body": "my-response-body"
}
```

In addition to that, the API Gateway will also wrap the original request inside an integration request JSON object, enriching it with metadata. This structure is much more complex than the response JSON. Covering request parsing is beyond the scope of this blog post so please refer to the AWS documentation.

In order to generate the required JSON response we are need to modify our handler. Also we are no longer returning our customers but a way more generic answer, applicable to many other questions as well: `42`. We are using [circe](https://github.com/circe/circe) to generate the JSON string but feel free to use any other library.

```scala
import java.io.{InputStream, OutputStream, PrintStream}
import io.circe.syntax._
import io.circe.generic.auto._
import com.amazonaws.services.lambda.runtime.{Context, RequestStreamHandler}
import scala.io.Source

case class Response(statusCode: Int,
                    isBase64Encoded: Boolean,
                    headers: Map[String, String],
                    body: String)

class Handler extends RequestStreamHandler {
  override def handleRequest(input: InputStream,
                             output: OutputStream,
                             context: Context): Unit = {
    val logger = context.getLogger
    val inputJsonString = Source.fromInputStream(input).mkString
    logger.log(inputJsonString)
    val result = Response(
      statusCode = 200,
      isBase64Encoded = false,
      headers = Map.empty,
      body = "42"
    ).asJson
    val out = new PrintStream(output)
    out.print(result)
    out.close()
  }
}
```

The new handler will now respond to any request with `42`:

```json
{
  "statusCode": 200,
  "isBase64Encoded": false,
  "headers": {},
  "body": "42"
}
```

Our Terraform file needs a slight modification, as we changed the class of the handler:

```conf
resource "aws_lambda_function" "lambda-elb-test-lambda" {
  ...
  handler = "de.frosner.elbvsl.lambda.Handler"
  ...
}
```

The next subsection covers how to set up the API Gateway.

## API Gateway Configuration

In the API Gateway each API includes a set of resources and methods implemented through the HTTP protocol. This corresponds to the concept of representational state transfer (REST) [2].

In our case we will have just one resource called `question` and we will support `ANY` method for convenience reasons. In a well designed REST API, the semantics for posting a question should be properly defined and we would use `POST`, for example.

The following Terraform file is defining a new API `lambda-elb-test-lambda` together with our `question` resource and method.

```conf
resource "aws_api_gateway_rest_api" "lambda-elb-test-lambda" {
  name        = "lambda-elb-test"
  description = "Lambda vs Elastic Beanstalk Lambda Example"
}

resource "aws_api_gateway_resource" "question" {
  rest_api_id = "${aws_api_gateway_rest_api.lambda-elb-test-lambda.id}"
  parent_id   = "${aws_api_gateway_rest_api.lambda-elb-test-lambda.root_resource_id}"
  path_part   = "question"
}

resource "aws_api_gateway_method" "question" {
  rest_api_id   = "${aws_api_gateway_rest_api.lambda-elb-test-lambda.id}"
  resource_id   = "${aws_api_gateway_resource.question.id}"
  http_method   = "ANY"
  authorization = "NONE"
}
```

Now that we have defined the REST API, how do we connect it to our Lambda function? Let's find out.

## Wiring Everything Together

To make the API Gateway work with our Lambda function, we have to create an *integration*. API Gateway supports different [integration types](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html) and integration HTTP methods. For integrating with Lambda, we have to choose the `AWS_PROXY` integration type and the `POST` method for communication between the API Gateway and Lambda. Here's the Terraform resource definition:

```conf
resource "aws_api_gateway_integration" "lambda" {
  rest_api_id = "${aws_api_gateway_rest_api.lambda-elb-test-lambda.id}"
  resource_id = "${aws_api_gateway_method.question.resource_id}"
  http_method = "${aws_api_gateway_method.question.http_method}"

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "${aws_lambda_function.lambda-elb-test-lambda.invoke_arn}"
}
```

In order to make the API accessible to clients, we have to deploy it. A *deployment* has to be associated with a *stage*. Stages empower us to do canary releases, but we are just going to stick with one stage called `test` for now. We add a terraform dependency to the integration to make sure that the integration is created before:

```conf
resource "aws_api_gateway_deployment" "lambda" {
  depends_on = [
    "aws_api_gateway_integration.lambda"
  ]

  rest_api_id = "${aws_api_gateway_rest_api.lambda-elb-test-lambda.id}"
  stage_name  = "test"
}
```

Finally we have to create a permission for our API Gateway deployment to invoke the Lambda function:

```conf
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.lambda-elb-test-lambda.arn}"
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_deployment.lambda.execution_arn}/*/*"
}
```

We can now execute `terraform apply` to start up all the components. We are adding an output field that will give us the final API URL: `${aws_api_gateway_deployment.lambda.invoke_url}/${aws_api_gateway_resource.question.path_part}`. Please find the execution results below. I omitted some details to make it more readable.

```
aws_iam_role.lambda_exec: Creating...
aws_api_gateway_rest_api.lambda-elb-test-lambda: Creating...
aws_api_gateway_rest_api.lambda-elb-test-lambda: Creation complete after 1s (ID: 27xbmjqf24)
aws_api_gateway_resource.question: Creating...
aws_iam_role.lambda_exec: Creation complete after 1s (ID: lambda-elb-test_lambda)
aws_api_gateway_account.lambda-elb-test: Creating...
aws_lambda_function.lambda-elb-test-lambda: Creating...
aws_api_gateway_resource.question: Creation complete after 0s (ID: tce971)
aws_api_gateway_method.question: Creating...
aws_api_gateway_method.question: Creation complete after 0s (ID: agm-27xbmjqf24-tce971-ANY)
aws_api_gateway_account.lambda-elb-test: Still creating... (10s elapsed)
aws_lambda_function.lambda-elb-test-lambda: Still creating... (10s elapsed)
aws_lambda_function.lambda-elb-test-lambda: Creation complete after 14s (ID: lambda-elb-test)
aws_api_gateway_integration.lambda: Creating...
aws_api_gateway_integration.lambda: Creation complete after 0s (ID: agi-27xbmjqf24-tce971-ANY)
aws_api_gateway_deployment.lambda: Creating...
aws_api_gateway_deployment.lambda: Creation complete after 0s (ID: qpzovb)
aws_lambda_permission.apigw: Creating...
aws_lambda_permission.apigw: Creation complete after 1s (ID: AllowAPIGatewayInvoke)

Apply complete!

Outputs:

url = https://27xbmjqf24.execute-api.eu-central-1.amazonaws.com/test/question
```

```
$ curl https://27xbmjqf24.execute-api.eu-central-1.amazonaws.com/test/question
42
```

# Conclusion

We have seen that it is possible to develop RESTful services on AWS without having to deal with virtual machines, operating systems, or containers. AWS API Gateway and AWS Lambda are two important ingredients for "serverless" applications on AWS.

The advantage of such architecture lies in the decoupling of individual functionalities, enabling small distributed teams using different programming languages to develop their services. Most of the maintenance work is offloaded to AWS and services communicate only through well-defined APIs.

The disadvantage lies in the lack of flexibility and the potential to become too fine-granular, leading to a messy, complicated design. When you use AWS Lambda, you are stuck with the runtime environments they support. This is different in a PaaS approach, where you can containerize your runtime and have a higher confidence with regards to reproducibility.

Have you used AWS Lambda in production? Did you run into problems, e.g. with regards to scalability or maintainability? What is your experience with similar concepts of other cloud providers? Let me know in the comments!

# References

- [1] [Serverless Architectures](https://martinfowler.com/articles/serverless.html) by [Mike Roberts](https://www.symphonia.io/bios/#mike-roberts)
- [2] Fielding, Roy T., and Richard N. Taylor. Architectural styles and the design of network-based software architectures. Vol. 7. Doctoral dissertation: University of California, Irvine, 2000.
- Cover image derived from an image created by Sam Johnston using OmniGroup's OmniGraffle and Inkscape (includes Computer.svg by Sasa Stefanovic), CC BY-SA 3.0, https://commons.wikimedia.org/w/index.php?curid=6080417
