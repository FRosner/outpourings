---
title: Infrastructure as Code - Managing AWS With Terraform
published: true
description: Infrastructure as Code (IaC) refers to the process of managing IT infrastructure through definition files rather than interactive configuration tools.
tags: devops, cloud, aws, xaas
cover_image: https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/TerraformedMoonFromEarth.jpg/1024px-TerraformedMoonFromEarth.jpg
---

This blog post is part of my AWS series:

- [**Infrastructure as Code - Managing AWS With Terraform**](#)
- [Deploying an HTTP API on AWS using Lambda and API Gateway](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61)
- [Deploying an HTTP API on AWS using Elastic Beanstalk](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-elastic-beanstalk-5dh7)
- [Deploying and Benchmarking an AWS RDS MySQL Instance](https://dev.to/frosnerd/deploying-and-benchmarking-an-aws-rds-mysql-instance-2faf)
- [Event Handling in AWS using SNS, SQS, and Lambda](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng)

# Introduction

Companies today often do not have to run their own data center anymore. Public and private cloud providers offer great products on different levels of abstraction. Whether you need access to hypervisors to create virtual machines or just want to run a Python snippet, anything is possible. These different levels of abstraction are usually referred to as XaaS. Starting from the highest abstraction the following categorization is commonly used:

- Software as a Service (SaaS)
- Platform as a Service (PaaS)
- Infrastructure as a Service (IaaS)

Although using offerings like this from [Amazon Web Services](https://aws.amazon.com/) (AWS) or [Google Cloud](https://cloud.google.com/) take away a lot of the complexity, managing different resources and dependencies between the individual components can become very messy. How do you deal with malfunctioning parts? How do you perform upgrades and roll-backs? What about maintenance?

You may have heard about the analogy to treat your servers as cattle, not cats. If a cat doesn't feel good you pet it and try to make it happy. If this happens to one of your cows you slaughter it and get a new one. You don't invest resources into fixing one animal from the herd. I am vegan and I do not approve slaughtering animals but the concept applied to infrastructure makes sense to me.

In software engineering people have developed techniques for dependency management and version control of software modules. Can we maybe apply some of those techniques to our infrastructure as well? The answer is yes, we can. And one of the important ingredients to accomplish this is treating our infrastructure as code. And this is what we are going to look at in this post, together with an example of managing AWS resources using Terraform.

The blog post is structured as follows. In the first part we want to dig a bit deeper into the concept of infrastructure as code. The second part will go through a simple example on how to manage resources on AWS using Terraform. We are closing the post by summarizing the main ideas.

# Infrastructure As Code

*Infrastructure as Code* (IaC) refers to the process of managing IT infrastructure through definition files rather than interactive configuration tools. It is closely coupled with the cattle-not-cat principle, as recreating parts of the infrastructure can be completely automated based on the definition files.

The definition files are typically put under version control. Combined with continuous integration and continuous delivery pipelines, a high degree of automation can be achieved. IaC combined with automation brings three advantages:

- **Reproducibility.** It is possible to recreate parts or the whole infrastructure from scratch based on the definition files. By using explicit versions for each component and versioning the definition files as well, the results of the deployments are reproducible.
- **Speed.** Computers are fast when it comes to executing predefined tasks. When setting up and configuring a new environment, having as little human interaction as possible will speed up your deployment.
- **Quality.** Due to the the first two advantages it becomes possible and reasonably cost-efficient to implement automated tests for your infrastructure. This improves the robustness and quality of your deployment. Removing human interactions also helps in avoiding errors.

Many tools exist that enable the IaC approach, all of them to a different extend. [Ansible](https://www.ansible.com/), [Puppet](https://puppet.com/), [Chef](https://www.chef.io/chef/), and [SaltStack](https://saltstack.com/) are a few notable examples. Ansible is *imperative*, i.e. you declare how to setup the infrastructure, and operates with the *push* principle, i.e. it actively goes to the components and changes them. Puppet on the other hand is *declarative*, i.e. you describe the desired state, and works in the *pull* principle, i.e. a Puppet agent runs on each server, pulling the latest configuration from the Puppet master.

What all the above-mentioned tools have in common is that they are *configuration management* tools. They are designed to install software and manage configuration on different servers. The question is, how do you get the servers you want to manage? The answer is *orchestration management*.

Orchestration management focuses on creating different resources, e.g. virtual machines, in the correct order and wiring them together as required. Combined with immutable infrastructure, which is a very much related to our cattle-not-cats principle, the question arises whether you actually need configuration management at all. Every cloud provider offers some sort of immutable component storage in the form of container or virtual machine images.

[HashiCorp Terraform](https://www.terraform.io/) is a powerful infrastructure orchestration tool. In the following section we want to take a closer look at Terraform in action.

# Terraform In Action

## Problem

To demonstrate the workflow of Terraform we are going to deploy a simple infrastructure on AWS. The goal is to create a virtual machine using Amazon [Elastic Compute Cloud](https://aws.amazon.com/ec2/) (EC2) and use SSH to connect it. To do that we need to configure the firewall to allow TCP traffic on port 22 and copy our public key to the machine.

## AWS Setup

Before we can start we need to make sure we can access the [AWS console](https://aws.amazon.com/console/). To do that you first need to create an AWS account if you do not have one already. Then you should create a new user and assign full access to EC2 so that we can perform the required operations.

On the machine that will run Terraform, e.g. our laptop for now, we need to perform some basic configuration. There are multiple ways to do that but we are going to choose the file based approach. We need to create a `credentials` and a `config` file inside the `~/.aws` folder with the following content:

```ini
# ~/.aws/credentials
[default]
aws_access_key_id=<access_key>
aws_secret_access_key=<secret_access_key>
```

```ini
# ~/.aws/config
[default]
region=eu-central-1
output=json
```

Both the access key and the secret access key can be obtained from the AWS console. Note that it is not recommended to use the root credentials but rather a specific user. You can also install the [AWS CLI](https://aws.amazon.com/cli/), but it is not required for Terraform to work. Here we are also configuring the region and output format of the AWS CLI, although it does not really affect Terraform.

Note that we are working with the default profile. If you are using AWS for other purposes already you might want to [create a new profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-multiple-profiles.html).

## Terraform Deployment

### Setup

An infrastructure managed by Terraform is defined in `.tf` files, which are written in [HashiCorp Configuration Language](https://github.com/hashicorp/hcl) (HCL) or JSON. Terraform supports variable interpolation based on different sources like files, environment variables, other resources, and so on.

The definition files are declarative, describing how the final picture should look. If the current state does not satisfy the definition, resources will be adjusted, e.g. destroyed and recreated, in order to match the desired state.

In order to initialize a Terraform directory, you execute the `terraform init` command. Of course you should have Terraform [installed](https://www.terraform.io/downloads.html). Terraform stores its state in a so called *backend*. For this simple example we are going to use the *local* backend, which stores the state in a `terraform.tfstate` file in the working directory. In a production scenario you can choose a [different backend](https://www.terraform.io/docs/backends/types/index.html) depending on your needs.

Initialization will also download the required [providers](https://www.terraform.io/docs/providers/), in our case for AWS. A provider is used as an abstraction to interact with resources. The AWS provider enables us to manage AWS resources.

Let's create a new definition file called `example.tf`.

```conf
# example.tf
provider "aws" {
  region     = "eu-central-1"
}
```

Running `terraform init` will give the following output:

```
Initializing provider plugins...
...
* provider.aws: version = "~> 1.21"
...
Terraform has been successfully initialized!
```

### Basic Commands

For now we are going to need four basic commands: `plan`, `apply`, `show`, and `destroy`. Similarly to the `init` command they can be executed using the terraform CLI (`terraform <command>`).

`terraform plan` is used to evaluate the current and desired state of your infrastructure and tell you what operations are required to make the two match. For full predictability you can save the plan to make sure that when you run it nothing unexpected happens in case your current state has changed in the meantime. If in this case Terraform detects any discrepancies it will abort the application.

`terraform apply` is used to execute the required operations in order to reach the desired infrastructure state. Missing resources will be created and modifications will trigger changes in the existing resources.

`terraform show` can be used to inspect the current state of the infrastructure. While it is mostly useful for debugging, it can be very helpful in some cases.

`terraform destroy` will remove all defined resources. Useful if you do not need your infrastructure anymore or your boss told you to cut some costs.

### Steps

#### Add EC2 Instance

First we are going to add a new EC2 instance based on the Ubuntu 14.04 image. Note that we configured the Frankfurt region (`eu-central-1`) and the identifier `ami-23a48cc8` is region dependent. You can use the [Ubuntu AMI Locator](https://cloud-images.ubuntu.com/locator/ec2/) to find the correct image for your region. Let's install this image on a `t2.micro` instance, which is included in the [free tier](https://aws.amazon.com/free).

```conf
# example.tf
provider "aws" { ... }

resource "aws_instance" "example" {
  ami           = "ami-23a48cc8" # Ubuntu 14.04 LTS AMD64 in eu-central-1
  instance_type = "t2.micro"
}
```

Running `terraform plan` will tell us that it will create the new instance once we apply the changes:

```
Terraform will perform the following actions:

  + aws_instance.example
      id:                                    <computed>
      ami:                                   "ami-23a48cc8"
      instance_type:                         "t2.micro"
```

Besides the `id` field there are many other `<computed>` fields which I excluded from the pasted output for now. A computed field means that Terraform will produce a value once the plan is executed. We will see later how we can access those computed values directly other than using `terraform show`.

Now that we have defined the instance, let's proceed with preparing the public key authentication for our SSH server.

#### Add Public Key

In addition to managing virtual machines in EC2, AWS allows you to [manage your public keys](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html) as well. In order to login with our public/private key pair we need to create a new public key inside AWS. We can add a new `aws_key_pair` resource to our definition file:

```conf
# example.tf
provider "aws" { ... }

resource "aws_instance" "example" { ... }

resource "aws_key_pair" "my-key" {
  key_name   = "my-key"
  public_key = "${file("~/.ssh/id_rsa.pub")}"
}
```

As you can see we imputed the key from a public key file. You can also store the keys in a separate variable file or paste them directly, for example.

Adding a public key is not enough, however. We need to associate a set of firewall rules with our instance in order to correctly route the SSH traffic to port 22.

#### Add Security Group

In AWS you manage incoming and outgoing traffic by defining [security rules](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-network-security.html). Let's add a new `aws_security_group` that forwards any incoming TCP connection on port 22.

```conf
# example.tf
provider "aws" { ... }

resource "aws_instance" "example" { ... }

resource "aws_key_pair" "my-key" { ... }

resource "aws_security_group" "allow_ssh" {
  name = "allow_ssh"
  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

Looks good! Now that we have the EC2 instance in place, as well as the public key and the security rules, the only thing we need to do is to wire them together.

#### Update EC2 Instance

In order to declare a dependency between Terraform resources, you simply use a variable from another resource. By accessing `aws_key_pair.my-key.key_name` and `aws_security_group.allow_ssh.name` from within the `aws_instance.example` resource, Terraform will know that it has to create the key and security group first. We can now modify our example instance to use the defined key and security groups:

```conf
# example.tf
provider "aws" { ... }

resource "aws_instance" "example" {
  ami             = "ami-23a48cc8" # Ubuntu 14.04 LTS AMD64 in eu-central-1
  instance_type   = "t2.micro"
  key_name        = "${aws_key_pair.my-key.key_name}"
  security_groups = ["${aws_security_group.allow_ssh.name}"]
}

resource "aws_key_pair" "my-key" { ... }

resource "aws_security_group" "allow_ssh" { ... }
```

Let's execute `terraform apply`. First it will print the plan and ask for confirmation:

```
Terraform will perform the following actions:

  + aws_instance.example
    ...
  + aws_key_pair.my-key
    ...
  + aws_security_group.allow_ssh
    ...
```

If we approve, the resources will be created in the correct order. Terraform parallelizes the creation of independent resources.

```
aws_key_pair.my-key: Creating...
aws_security_group.allow_ssh: Creating...
aws_key_pair.my-key: Creation complete after 0s (ID: my-key)
aws_security_group.allow_ssh: Creation complete after 2s (ID: sg-0231ae1c04f2f9556)
aws_instance.example: Creating...
aws_instance.example: Still creating... (10s elapsed)
aws_instance.example: Still creating... (20s elapsed)
aws_instance.example: Creation complete after 22s (ID: i-0761f0d410df33154)

Apply complete! Resources: 3 added, 0 changed, 0 destroyed.
```

Amazing! But how do we know where to connect to? What is the name of the server? We could use `terraform show` or the AWS console to find out. But there is a much nicer way.

#### The Result

We can add `output` declarations to the definiton files, which will give us access to computed values right after a successful execution. The final `example.tf` looks like this:

```conf
# example.tf
provider "aws" {
  region = "eu-central-1"
}

resource "aws_instance" "example" {
  ami             = "ami-23a48cc8" # Ubuntu 14.04 LTS AMD64 in eu-central-1
  instance_type   = "t2.micro"
  key_name        = "${aws_key_pair.my-key.key_name}"
  security_groups = ["${aws_security_group.allow_ssh.name}"]
}

resource "aws_security_group" "allow_ssh" {
  name = "allow_ssh"
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_key_pair" "my-key" {
  key_name   = "my-key"
  public_key = "${file("~/.ssh/id_rsa.pub")}"
}

output "example_public_dns" {
  value = "${aws_instance.example.public_dns}"
}
```

Now `terraform apply` will give us the server name:

```
Outputs:
example_public_dns = ec2-18-184-130-203.eu-central-1.compute.amazonaws.com
```

And executing `ssh ubuntu@<server-name>` succeeds as expected:

```
Welcome to Ubuntu 14.04.5 LTS (GNU/Linux 3.13.0-149-generic x86_64)
ubuntu@ip-172-31-47-208:~$
```

After you are done, do not forget to destroy the infrastructure using `terraform destroy` as it is no longer needed.

# Summary and Final Thoughts

In this blog post we have seen how to treat your infrastructure as immutable components defined in version controlled code. Infrastructure as code can improve the reproducibility, speed, and quality of your deployment. Many different tools exist to support this paradigm.

Using an orchestration tool like Terraform together with immutable container or virtual machine images is a valid alternative to traditional configuration management tools like Ansible or Puppet. Terraform supports many different resource providers and allows configurable backends to store its state.

Which tools do you use to manage your infrastructure? Have you used any of the mentioned tools before? Do you favour configuration management tools, orchestration management tools, or a combination of both? Let me know what you think in the comments!

---

Cover image licensed under CC BY-SA 3.0, https://commons.wikimedia.org/w/index.php?curid=1194108.
