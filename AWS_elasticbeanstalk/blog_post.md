---
title: Deploying an HTTP API on AWS using Elastic Beanstalk
published: true
description: The scope of this post is to deploy an HTTP API implemented in Akka HTTP using AWS Elastic Beanstalk.
tags: aws, devops, paas, cloud
cover_image: https://thepracticaldev.s3.amazonaws.com/i/lk4zkkbto2hzcxmt6x4g.png
---

This blog post is part of my AWS series:

- [Infrastructure as Code - Managing AWS With Terraform](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o)
- [Deploying an HTTP API on AWS using Lambda and API Gateway](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61)
- [**Deploying an HTTP API on AWS using Elastic Beanstalk**](#)
- [Deploying and Benchmarking an AWS RDS MySQL Instance](https://dev.to/frosnerd/deploying-and-benchmarking-an-aws-rds-mysql-instance-2faf)
- [Event Handling in AWS using SNS, SQS, and Lambda](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng)
- [Continuous Delivery on AWS With Terraform and Travis CI](https://dev.to/frosnerd/continuous-delivery-on-aws-with-terraform-and-travis-ci-3914)
- [Sensor Data Processing on AWS using IoT Core, Kinesis and ElastiCache](https://dev.to/frosnerd/sensor-data-processing-on-aws-using-iot-core-kinesis-and-elasticache-26j1)
- [Monitoring AWS Lambda Functions With CloudWatch](https://dev.to/frosnerd/monitoring-aws-lambda-functions-with-cloudwatch-1nap)

# Introduction

In the previous post we were looking at AWS Lambda together with AWS API Gateway to implement an HTTP API. In this post we want to do the same thing but using a PaaS concept instead of FaaS.

AWS offers a service called [*Elastic Beanstalk*](https://aws.amazon.com/elasticbeanstalk/). Elastic Beanstalk can be used for deploying and scaling web applications. It allows you to upload your code and handles load balancing, logs and metrics management, alerting, application version management, and DNS resolution transparently.

The scope of this post is to recreate the same API as in the last example, this time using Akka HTTP as an embedded web server and deploying the application using Elastic Beanstalk.

The remainder of the post is structured as follows. First we are going to give an overview of the application architecture. As Elastic Beanstalk bundles many different AWS services, we will go into more detail on how they are composed and what is the purpose of each individual one. The next section will guide you through the implementation and deployment of the HTTP API using Elastic Beanstalk and Terraform. We are closing the post by summarizing the main ideas and briefly discussing the advantages and disadvantages of this approach.

# Architecture

The following figure illustrates the target architecture. The client sends an HTTP request to the Elastic Beanstalk application. Elastic Beanstalk will then let the deployed application version handle the request and return a response. Similar to the architecture from the previous post, S3 is used to store different application versions.

![architecture overview](https://thepracticaldev.s3.amazonaws.com/i/xn3rrxz9gc8dpk0os7dn.png)

While this looks simple, there is a lot happening under the hood. Elastic Beanstalk bundles many different components from the AWS ecosystem. The next diagram illustrates the internals of an Elastic Beanstalk application.

![elastic beanstalk architecture](https://thepracticaldev.s3.amazonaws.com/i/lk4zkkbto2hzcxmt6x4g.png)

Elastic Beanstalk starts [EC2](https://aws.amazon.com/ec2) instances within an [Auto Scaling Group](https://aws.amazon.com/autoscaling) and a configurable amount of availability zones. These instances are used to run your application. It places the instances inside [VPC](https://aws.amazon.com/vpc) and configures a [security group](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_SecurityGroups.html) to protect your instances, by default only accepting connections on port 80.

Application versions are persisted in a separate [S3](https://aws.amazon.com/s3) bucket and can be imported either directly or from another S3 bucket, for example.

Elastic Beanstalk supports [different platforms](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/concepts.platforms.html), e.g. Java SE, .NET, Node.js, PHP, or Python. On each platform you can select a predefined solution stack specifying the exact software stack of the execution runtime, e.g. *64bit Amazon Linux 2018.03 v2.7.1 running Java 8*.

The domain name is managed through [Route 53](https://aws.amazon.com/route53). Incoming traffic will be send to an [Elastic Load Balancer](https://aws.amazon.com/elasticloadbalancing), which acts as an entry point to your application. The load balancer will forward the requests to your EC2 instances, allowing for horizontal scalability in combination with the autoscaling group. Note however that autoscaling seems not to be supported in `eu-central-1` as of today.

To support operations, Elastic Beanstalk will also create [Cloud Watch](https://aws.amazon.com/cloudwatch) alarms to based on the load of your EC2 instances. If you have autoscaling enabled, the alarm will trigger the creation of new EC2 instances. CloudWatch can also be used for monitoring and log management.

The whole infrastructure stack and its configuration is internally managed as a [Cloud Formation](https://aws.amazon.com/cloudformation/) template. All the components can be configured through [different settings](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/command-options.html).

In our concrete example we are going to develop the program logic in Scala. The assembled `jar` file will be published to S3 and used to process the requests. The next section will cover the implementation step by step.

# Implementation

## Development Tool Stack

To develop the solution we are using the following tools:

- Terraform v0.11.7
- SBT 1.0.4
- Scala 2.12.6
- IntelliJ + Scala Plugin + Terraform Plugin

The [source code](https://github.com/FRosner/lambda-vs-beanstalk) is available on GitHub. Note however that the project contains two modules, one for the AWS Elastic Beanstalk deployment and another one where I am experimenting with [AWS Lambda](https://aws.amazon.com/lambda/).

## Developing The HTTP API

The HTTP API is implemented on top of [Akka HTTP](https://doc.akka.io/docs/akka-http/current/). To work with Akka, we need to create a new [`ActorSystem`](https://doc.akka.io/api/akka/current/akka/actor/ActorSystem.html) and [`ActorMaterializer`](https://doc.akka.io/api/akka/current/akka/stream/ActorMaterializer.html). This is required for any Akka application and we are not going to go into details about the internals of Akka in this post.

The routing logic of our API is rather simple. We only expose one resource called `question` which returns 42 on any request.

```scala
val route =
    path("question") {
      complete(42.toString)
    }
```

The server listens on interface `0.0.0.0` and binds to a port given by Elastic Beanstalk through the `$PORT` environment variable. It would be cleaner to use a proper configuration file and pass the port argument through the [`Procfile`](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/java-se-procfile.html), but this way I was able to deploy the `jar` without any additional files or directory structure.

```scala
val interface = "0.0.0.0"
val port = Try(System.getenv("PORT").toInt) match {
  case Success(i) => i
  case Failure(t) =>
    println("Failed to read $PORT: " + t)
    println(s"Using default port: 80")
    80
}
val bindingFuture = Http().bindAndHandle(route, interface, port)
println(s"Server online at http://$interface:$port/")
```

In contrast to the Lambda function we developed in the previous post, our `jar` file will be invoked as an application and thus needs a `main` method defined inside the manifest. This can be done inside the `build.sbt` file:

```scala
mainClass in assembly := Some("de.frosner.elbvsl.elb.Main")
```

Next thing we need to do is to package that function and make it available for Elastic Beanstalk. We are going to use the same method as in the [previous post](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61). [sbt-assembly](https://github.com/sbt/sbt-assembly) will build a fat `jar` and the [fm-sbt-s3-resolver](https://github.com/frugalmechanic/fm-sbt-s3-resolver) will upload it to `s3://s3-eu-central-1.amazonaws.com/lambda-elb-test/elb`. Please refer to the previous post for more details on this step.

Now with the artifact available in S3, we can go ahead and create the Elastic Beanstalk application using Terraform.

## Creating The Elastic Beanstalk Application

An Elastic Beanstalk *application* is a collection of *environments* and application *versions*. The application itself is more like a container or folder for the different environments and versions. An environment together with an *environment configuration* defines a set of AWS components and resources, i.e. EC2 instances and so on, that can run a version. A version is a labeled artifact of deployable code stored in S3. Versions are unique across all environments.

An environment can run a single application version at a time, but an application version can be run in several environments simultaneously. When creating a new basic application in Terraform we only have to choose a name:

```conf
resource "aws_elastic_beanstalk_application" "lambda-elb-test" {
  name        = "lambda-elb-test"
}
```

Next we can define an environment and link it to our application.

## Setting Up The Elastic Beanstalk Environment

When creating a new environment we choose a name, the application to create the environment in, as well as a solution stack. Environment settings can be defined by repeating the `setting` stanza within the environment resource definition. As we are going to run a Scala application, we choose the Java 8 solution stack.

```conf
resource "aws_elastic_beanstalk_environment" "lambda-elb-test" {
  name                = "lambda-elb-test"
  application         = "${aws_elastic_beanstalk_application.lambda-elb-test.name}"
  solution_stack_name = "64bit Amazon Linux 2018.03 v2.7.1 running Java 8"
}
```

We are going to leave all settings set to their default values. We need to provide, however, an *instance profile*. An instance profile is a container for a role. In our case we need to associate a role for our EC2 servers to be able to talk to the other services of AWS like S3, CloudWatch, and so on. Luckily there is already a managed policy called [`AWSElasticBeanstalkWebTier`](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/iam-instanceprofile.html) which we can attach to our role and then create the instance profile.

```conf
resource "aws_iam_role" "elb" {
  name = "lambda-elb-test_elb"

  assume_role_policy = <<EOF
{
  "Version": "2008-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
}

data "aws_iam_policy" "AWSElasticBeanstalkWebTier" {
  arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier"
}

resource "aws_iam_role_policy_attachment" "elb-attach" {
  role       = "${aws_iam_role.elb.name}"
  policy_arn = "${data.aws_iam_policy.AWSElasticBeanstalkWebTier.arn}"
}

resource "aws_iam_instance_profile" "elb-profile" {
  name = "elb_profile"
  role = "${aws_iam_role.elb.name}"
}
```

Now we only need to set our newly configured instance profile as the instance profile of our environment:

```conf
resource "aws_elastic_beanstalk_environment" "lambda-elb-test" {
  name                = "lambda-elb-test"
  application         = "${aws_elastic_beanstalk_application.lambda-elb-test.name}"
  solution_stack_name = "64bit Amazon Linux 2018.03 v2.7.1 running Java 8"

  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "IamInstanceProfile"
    value     = "${aws_iam_instance_profile.elb-profile.name}"
  }
}
```

Having the environment created and configured, let's create a new application version containing our HTTP API.

## Managing Application Versions

In order to create a new application version we need to specify a name, the Elastic Beanstalk application, as well as the S3 location of the original artifact. Note that Elastic Beanstalk will then copy the artifact into its own generated S3 bucket. To be more flexible we define the version string as a variable.

```conf
variable "version" {
  type = "string"
  default = "0.1-SNAPSHOT"
}

resource "aws_elastic_beanstalk_application_version" "default" {
  name        = "elastic-beanstalk-vs-lambda_2.12-${var.version}"
  application = "${aws_elastic_beanstalk_application.lambda-elb-test.name}"
  description = "application version created by terraform"
  bucket      = "${data.aws_s3_bucket.lambda-elb-test.id}"
  key         = "${data.aws_s3_bucket_object.application-jar.key}"
}

data "aws_s3_bucket" "lambda-elb-test" {
  bucket = "lambda-elb-test"
}

data "aws_s3_bucket_object" "application-jar" {
  bucket = "${data.aws_s3_bucket.lambda-elb-test.id}"
  key    = "elb/de/frosner/elastic-beanstalk-vs-lambda_2.12/${var.version}/elastic-beanstalk-vs-lambda_2.12-${var.version}-assembly.jar"
}
```

This is everything we need to define for our example Elastic Beanstalk powered HTTP API. We can now run `terraform apply` and it will create the application, the instance profile, the version and the environment. Creating the environment takes a bit longer as it consists of a `t2.micro` EC2 instance and all the other components which need to be booted and configured.

```
aws_elastic_beanstalk_application.lambda-elb-test: Creating...
aws_iam_role.elb: Creating...
aws_elastic_beanstalk_application.lambda-elb-test: Creation complete after 1s (ID: lambda-elb-test)
aws_elastic_beanstalk_application_version.default: Creating...
aws_iam_role.elb: Creation complete after 1s (ID: lambda-elb-test_elb)
aws_iam_role_policy_attachment.elb-attach: Creating...
aws_iam_instance_profile.elb-profile: Creating...
aws_elastic_beanstalk_application_version.default: Creation complete after 0s (ID: elastic-beanstalk-vs-lambda_2.12-0.1-SNAPSHOT)
aws_iam_role_policy_attachment.elb-attach: Creation complete after 2s (ID: lambda-elb-test_elb-20180615071854874500000001)
aws_iam_instance_profile.elb-profile: Creation complete after 2s (ID: elb_profile)
aws_elastic_beanstalk_environment.lambda-elb-test: Creating...
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (10s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (20s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (30s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (40s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (50s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (1m0s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (1m10s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (1m20s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (1m30s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (1m40s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (1m50s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (2m0s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (2m10s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (2m20s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (2m30s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (2m40s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (2m50s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (3m0s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (3m10s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Still creating... (3m20s elapsed)
aws_elastic_beanstalk_environment.lambda-elb-test: Creation complete after 3m28s (ID: e-xkradrhtff)

Apply complete! Resources: 6 added, 0 changed, 0 destroyed.
```

Amazing! But how do we access our HTTP API? Elastic Beanstalk requires you to link a version to an environment. This is called *deployment*. Unfortunately, Terraform does not support version deployments at the moment, so we have to do it outside of Terraform.

## Deploying The HTTP API

To deploy the version we can either use the AWS console, or the AWS CLI. As we potentially want to automate our whole deployment, we are going to use the CLI.

Luckily, we don't have to figure out the command ourselves but can make Terraform fill the parameters for us:

```conf
output "aws_command" {
  value = "aws elasticbeanstalk update-environment --application-name ${aws_elastic_beanstalk_application.lambda-elb-test.name} --version-label ${aws_elastic_beanstalk_application_version.default.name} --environment-name ${aws_elastic_beanstalk_environment.lambda-elb-test.name}"
}
```

Now `terraform apply` will print the AWS CLI command in order to deploy the version and we can execute it right away. If you want a machine readable output format, e.g. to use the command in your build pipeline, you can run `terraform output -json aws_command` to get a JSON representation of the output variable. Here's the result of starting the deployment:

```
$ aws elasticbeanstalk update-environment --application-name lambda-elb-test --version-label elastic-beanstalk-vs-lambda_2.12-0.1-SNAPSHOT --environment-name lambda-elb-test

{
    "ApplicationName": "lambda-elb-test",
    "EnvironmentName": "lambda-elb-test",
    "VersionLabel": "elastic-beanstalk-vs-lambda_2.12-0.1-SNAPSHOT",
    "Status": "Updating",
    "EnvironmentArn": "arn:aws:elasticbeanstalk:eu-central-1:195499643157:environment/lambda-elb-test/lambda-elb-test",
    "PlatformArn": "arn:aws:elasticbeanstalk:eu-central-1::platform/Java 8 running on 64bit Amazon Linux/2.7.1",
    "EndpointURL": "awseb-e-s-AWSEBLoa-1IJ0QGEG44NME-197415464.eu-central-1.elb.amazonaws.com",
    "SolutionStackName": "64bit Amazon Linux 2018.03 v2.7.1 running Java 8",
    "EnvironmentId": "e-spvtgywyi2",
    "CNAME": "lambda-elb-test.cpmxg3eddt.eu-central-1.elasticbeanstalk.com",
    "AbortableOperationInProgress": true,
    "Tier": {
        "Version": "1.0",
        "Type": "Standard",
        "Name": "WebServer"
    },
    "Health": "Grey",
    "DateUpdated": "2018-06-14T12:56:02.263Z",
    "DateCreated": "2018-06-14T09:54:05.362Z"
}
```

And we can access the API as expected:

```
$ curl lambda-elb-test.cpmxg3eddt.eu-central-1.elasticbeanstalk.com/question

42
```

# Conclusion

In this post we have seen that AWS Elastic Beanstalk is a convenient way to manage the complexity behind scalable and maintainable cloud deployments. Thanks to reasonable defaults it allows you to get started quickly and adjust the configuration as needed. You will get load balancing, logging, metrics, alerting, application version management and DNS resolution out of the box.

Compared to the Lambda approach, Elastic Beanstalk gives you more control on the software stack and surrounding environment. However this makes the architecture a bit more complex, adding more pieces to the mix. Nevertheless I had the feeling that the complexity is manageable and thanks to the reasonable defaults it was actually faster to get started with Elastic Beanstalk than with Lambda and API Gateway.

One disadvantage is that autoscaling is not supported in all regions at the moment. Additionally, when using Terraform we cannot fully manage the whole lifecycle, as in the current version of Terraform deployment is not supported. In terms of deployment speed it might also not be the best choice to go with EC2 if you require fast scaling. To support this it might be an option to look into a container based solution, e.g. with [AWS ECS](https://aws.amazon.com/ecs/).

Have you used Elastic Beanstalk before? When do you prefer using FaaS (Lambda + AWS Gateway) over PaaS (Elastic Beanstalk)? Let me know in the comments what you think!
