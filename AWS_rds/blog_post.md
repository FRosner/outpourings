---
title: Deploying and Benchmarking an AWS RDS MySQL Instance
published: true
description: In this blog post we are going to take a look at how to deploy a relational database using AWS RDS. Setting this up involves creation of custom networking components such as subnets, route tables, and security groups.
tags: aws, cloud, networking, mysql
cover_image: https://thepracticaldev.s3.amazonaws.com/i/2w594dheu0pb7qsfmekq.png
---

This blog post is part of my AWS series:

- [Infrastructure as Code - Managing AWS With Terraform](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o)
- [Deploying an HTTP API on AWS using Lambda and API Gateway](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-lambda-and-api-gateway-g61)
- [Deploying an HTTP API on AWS using Elastic Beanstalk](https://dev.to/frosnerd/deploying-an-http-api-on-aws-using-elastic-beanstalk-5dh7)
- [**Deploying and Benchmarking an AWS RDS MySQL Instance**](#)
- [Event Handling in AWS using SNS, SQS, and Lambda](https://dev.to/frosnerd/event-handling-in-aws-using-sns-sqs-and-lambda-2ng)
- [Continuous Delivery on AWS With Terraform and Travis CI](https://dev.to/frosnerd/continuous-delivery-on-aws-with-terraform-and-travis-ci-3914)
- [Sensor Data Processing on AWS using IoT Core, Kinesis and ElastiCache](https://dev.to/frosnerd/sensor-data-processing-on-aws-using-iot-core-kinesis-and-elasticache-26j1)
- [Monitoring AWS Lambda Functions With CloudWatch](https://dev.to/frosnerd/monitoring-aws-lambda-functions-with-cloudwatch-1nap)

# Introduction

In the previous posts we were focusing on the compute and application deployment part of AWS. Although we were using a bit of S3 here and there, we did not talk much about other persistence mechanisms. We also did not touch the networking part that much. AWS provides reasonable defaults for many components, including the networking, so you can get started quickly.

In this blog post we are going to take a look at how to deploy a relational database using [AWS RDS](https://aws.amazon.com/rds). To make it a bit more interesting we will add an EC2 instance that is able to connect the database and run an exemplary benchmark on it. Setting this up involves creation of custom networking components such as subnets, route tables, and security groups. The [source code](https://github.com/FRosner/aws_rds_test) is available on GitHub.

The remainder of this post is structured as follows. First there will be an overview of the target architecture, including the RDS and EC2 instances but also all required network resources. Then - you might have guessed it - we will go into details about how to set things up using Terraform step by step. We are closing the post by discussing the main findings.

# Architecture

The core components of our infrastructure will be a MySQL database managed by RDS and an EC2 instance from which we can run the benchmark. In order to set it up in a way that we can use it, we are going to use the following architecture:

![Architecture Overview](https://thepracticaldev.s3.amazonaws.com/i/7fr9it72kyor0in4owe0.png)

Let's look into the individual parts in detail. All our instances are placed within a [VPC](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_Introduction.html). A VPC is a virtual network which is isolated from other tenants in the cloud and has its own private IP address range. Within the VPC there will be [subnets](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_Subnets.html). We are creating three private subnets (A - C) and one public subnet (A). A public subnet is a subnet that has a route to the internet through an [internet gateway](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_Internet_Gateway.html).

When creating a subnet we have to choose an [availability zone](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html). Each region, e.g. `eu-central-1` in our case, has multiple availability zones. Availability zones map to hardware that is physically separated, e.g. located in different buildings. By choosing different availability zones for our subnets we allow AWS to configure fail-over mechanisms between the MySQL instances in case of an outage of one availability zone.

The setup of RDS requires to define a [subnet group](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html). By grouping our three private subnets spanning three availability zones we allow AWS to launch redundant instances within those subnets.

The EC2 instance from which we are going to run the [sysbench](https://github.com/akopytov/sysbench) benchmark is placed within one of the private subnets, as we do not need it to be highly available. In order to SSH to that machine, we need to go through an instance running in the public subnet. We are using a [NAT instance](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_NAT_Instance.html) as our [bastion host](https://en.wikipedia.org/wiki/Bastion_host).

In addition to the correct [routing](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_Route_Tables.html) between the internet gateway and the NAT instance, as well as the NAT instance and the private subnet where the sysbench instance is located, we also need to setup up [security groups](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-network-security.html) accordingly.

A security group corresponds to a set of resources that share the same access rules in terms of network. You can think of it as a firewall configuration. We will enable TCP traffic on port 22 coming from the internet to flow through the NAT instance towards our private subnet A. Additionally our sysbench instance will get access to the MySQL RDS security group through port 3306 in order to connect to the database.

Now that we are familiar with the overall architecture, let's look into how to create the infrastructure with Terraform.

# Implementation

## Basic Networking

First we will create the basic network resources to have that technical part out of the way. We will need a VPC with one public and three private subnets. The following diagram highlights the parts we are creating now.

![basic networking architecture](https://thepracticaldev.s3.amazonaws.com/i/c95gy9xa6j8acg1bbx21.png)

### VPC

The VPC configuration is straightforward. All we need to do is to specify an IP range for our virtual network in the [CIDR notation](https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing) for the subnet prefix. We will use `10.0.0.0/16`, which gives us 65534 different host IP addresses from `10.0.0.1` to `10.0.255.254`. I recommend using a subnet mask calculator tool like [ipcalc](http://jodies.de/ipcalc) if you want to double check.

```conf
resource "aws_vpc" "rds_test" {
  cidr_block = "10.0.0.0/16"
}
```

### Availability Zones

Currently there are three availability zones supported in `eu-central-1`: `eu-central-1a`, `eu-central-1b`, and `eu-central-1c`. We can access them in Terraform using the `data` stanza. We are not defining a `resource` as the availability zones themselves are not created or destroyed by Terraform but only referenced.

```conf
data "aws_availability_zone" "eu-central-1a" {
  name = "eu-central-1a"
}

data "aws_availability_zone" "eu-central-1b" {
  name = "eu-central-1b"
}

data "aws_availability_zone" "eu-central-1c" {
  name = "eu-central-1c"
}
```

### Subnets

Next, we are dividing our VPC into multiple subnets. As our VPC (`10.0.0.0/16`) has only 65534 addresses available we need to distribute them somehow. Luckily, Terraform provides a convenient way to do that using the [`cidrsubnet`](https://www.terraform.io/docs/configuration/interpolation.html#cidrsubnet-iprange-newbits-netnum-) built-in function.

`cidrsubnet` devides your available IP addresses evenly across smaller subnets. It takes three parameters:

1. The network to devide into subnets, e.g. `10.0.0.0/16`.
2. The size of the smaller networks given as the difference in the subnet mask, e.g. `4` which will devide `10.0.0.0/16` into subnets of size `/20`.
3. The index of the subnet.

Given the three parameters, including the index *i* it will output a new CIDR block corresponding to the *i*-th subnet of the given size within the original network. Using this information we can conveniently enumerate our subnets by assigning them an index based on the availability zone they will be in, plus one index for the public subnet. We can implement this in Terraform using a variable of type `map`.

```conf
variable "az_number" {
  type = "map"
  # 1 = public subnet
  default = {
    a = 2
    b = 3
    c = 4
  }
}
```

Now we can define the public subnet and the three private subnets:

```conf
resource "aws_subnet" "eu-central-1a-public" {
  vpc_id = "${aws_vpc.rds_test.id}"
  cidr_block = "${cidrsubnet(aws_vpc.rds_test.cidr_block, 4, 1)}"
  availability_zone = "${data.aws_availability_zone.eu-central-1a.id}"
}

resource "aws_subnet" "rds_test_a" {
  vpc_id     = "${aws_vpc.rds_test.id}"
  cidr_block = "${cidrsubnet(aws_vpc.rds_test.cidr_block, 4, var.az_number[data.aws_availability_zone.eu-central-1a.name_suffix])}"
  availability_zone = "${data.aws_availability_zone.eu-central-1a.id}"
}

resource "aws_subnet" "rds_test_b" {
  vpc_id     = "${aws_vpc.rds_test.id}"
  cidr_block = "${cidrsubnet(aws_vpc.rds_test.cidr_block, 4, var.az_number[data.aws_availability_zone.eu-central-1b.name_suffix])}"
  availability_zone = "${data.aws_availability_zone.eu-central-1b.id}"
}

resource "aws_subnet" "rds_test_c" {
  vpc_id     = "${aws_vpc.rds_test.id}"
  cidr_block = "${cidrsubnet(aws_vpc.rds_test.cidr_block, 4, var.az_number[data.aws_availability_zone.eu-central-1c.name_suffix])}"
  availability_zone = "${data.aws_availability_zone.eu-central-1c.id}"
}
```

Next let's create the MySQL RDS.

## RDS

In order to create a new MySQL database we need to first create a subnet group and a security group that we can assign it to. The following diagram highlights the components we are creating now.

![rds architecture](https://thepracticaldev.s3.amazonaws.com/i/vmp86ozhr6o5blaqjsb4.png)

When creating a new MySQL RDS instance, you have to specify a subnet group that spans at least two availability zones. First we create the subnet group and assign our three private subnets to it.

```conf
resource "aws_db_subnet_group" "rds_test" {
  name       = "rds_test"
  subnet_ids = ["${aws_subnet.rds_test_a.id}", "${aws_subnet.rds_test_b.id}", "${aws_subnet.rds_test_c.id}"]
}
```

In order to control access in and out of the database, we also need a security group. It will not have any rules associated with it, yet.

```conf
resource "aws_security_group" "rds_test_mysql" {
  name = "rds_test_mysql"
  description = "RDS Test MySQL Security Group"
  vpc_id = "${aws_vpc.rds_test.id}"
}
```

Next we can define the MySQL resource. In addition to the name of the instance we need to provide the following information:

- Amount (GB) and [type](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html) of storage we want to allocate.
- Database engine and version, i.e. MySQL 5.7 in our case. AWS also supports [other engines](https://aws.amazon.com/rds/details/) like PostgreSQL or Amazon Aurora.
- [EC2 instance type](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html), depending on your memory and CPU requirements.
- Initial login credentials. It is highly recommended to inject secrets into your scripts and not store them anywhere within your source repository. Also make sure to store the Terraform state file somewhere safe as it might contain those secrets as well.
- The [parameter group](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithParamGroups.html) to use. Parameter groups allow you to reuse database configuration but we are sticking to the default configuration.
- The subnet group and the security groups we created earlier.
- Decide on a deletion strategy. We can either choose a `final_snapshot_identifier` which will be used to create a final snapshot of the database before it gets deleted, or set `skip_final_snapshot` to true in order to throw away the database without any snapshot.

Additionally we are passing a parameter called `apply_immediately` which indicates whether changes to the database should be applied immediately after being issued or queued until the next maintenance window. For convenience reasons I encoded this into a variable.

```conf
variable "apply_immediately" {
  default = "false"
  description = "Whether to deploy changes to the database immediately (true) or at the next maintenance window (false)."
}

resource "aws_db_instance" "rds_test_mysql" {
  allocated_storage      = 10
  storage_type           = "gp2"
  engine                 = "mysql"
  engine_version         = "5.7"
  instance_class         = "db.t2.micro"
  name                   = "rds_test_mysql"
  username               = "foo"
  password               = "foobarbaz"
  parameter_group_name   = "default.mysql5.7"
  db_subnet_group_name   = "${aws_db_subnet_group.rds_test.name}"
  vpc_security_group_ids = ["${aws_security_group.rds_test_mysql.id}"]
  apply_immediately      = "${var.apply_immediately}"
  skip_final_snapshot    = true
}
```

Now it is time for the sysbench EC2 instance.

## Sysbench Instance

In order to conduct the sysbench MySQL benchmark we need to have the `sysbench` and the `mysql-client-core-5.7` package installed. To do that we first create a new AMI using [Packer](https://www.packer.io/) and deploy it on an EC2 instance.

![sysbench ec2](https://thepracticaldev.s3.amazonaws.com/i/iq6m3wb6rob1rqeck2f1.png)

### AMI Creation

To create a new AMI, we need to specify information about how to build the AMI and then how to provision it. Packer supports different [provisioners](https://www.packer.io/docs/provisioners/index.html), which can be used to customize the built image before it is pushed to AWS and available for use.

I do not want to go into too much detail about Packer at this point, but most of the parameters should be more or less self explanatory. We can pass the following JSON to `packer build` in order to receive an Ubuntu image which has sysbench and a MySQL 5.7 client installed.

```json
{
  "builders": [{
    "type": "amazon-ebs",
    "region": "eu-central-1",
    "source_ami_filter": {
      "filters": {
        "virtualization-type": "hvm",
        "name": "ubuntu/images/*ubuntu-xenial-16.04-amd64-server-*",
        "root-device-type": "ebs"
      },
      "owners": ["099720109477"],
      "most_recent": true
    },
    "instance_type": "t2.micro",
    "ssh_username": "ubuntu",
    "ami_name": "rds_test_sysbench {{timestamp}}"
  }],
  "provisioners": [{
    "type": "shell",
    "inline": [
      "sudo apt-get update",
      "sudo apt-get install -y sysbench",
      "sudo apt-get install -y mysql-client-core-5.7"
    ]
  }]
}
```

### Instance Definition

Creating an EC2 instance is done in the same way as in the [first post](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o). We need to specify the image, the instance type, the authorized public key, as well as the subnet and security group. The security group will be created but, similarly to the RDS security group, does not have any rules associated with it, yet.

```conf
data "aws_ami" "rds_test_sysbench" {
  most_recent      = true
  name_regex = "rds_test_sysbench.*"
  owners     = ["195499643157"]
}

resource "aws_security_group" "rds_test_sysbench" {
  name = "rds_test_sysbench"
  vpc_id = "${aws_vpc.rds_test.id}"
}

resource "aws_key_pair" "my-key" {
  key_name = "my-key"
  public_key = "${file("~/.ssh/id_rsa.pub")}"
}

resource "aws_instance" "rds_test_sysbench" {
  ami           = "${data.aws_ami.rds_test_sysbench.id}"
  instance_type = "t2.micro"
  key_name = "${aws_key_pair.my-key.key_name}"
  vpc_security_group_ids = ["${aws_security_group.rds_test_sysbench.id}"]
  subnet_id = "${aws_subnet.rds_test_a.id}"
}
```

## Finding Our Way Through The Network

Last but not least we need to connect all the different components and grant ourselves a way to access the system. To do that we need to setup our bastion host in the public subnet, configure an internet gateway, adjust the routing logic between the internet gateway, the public subnet and the private subnet, as well as adding rules to our security groups.

![internet gateway and routing](https://thepracticaldev.s3.amazonaws.com/i/5m971kvh0q8vnj03nmdh.png)

### EC2 NAT Instance

Our bastion host will run the `amzn-ami-vpc-nat-hvm-2018.03.0.20180508-x86_64-ebs` AMI. It is recommended to always use the latest NAT AMI to make use of configuration updates.

EC2 instances by default perform checks on source or destination of network packets, making sure that it is either the source or the destination of that packet. For a NAT instance to function we have to disable this check.

Like before we have to provide a security group. This time we can already fill in the rules for incoming and outgoing SSH traffic.

```conf
resource "aws_security_group" "rds_test_nat" {
  name = "rds_test_nat"
  description = "Allow SSH"

  ingress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["${aws_vpc.rds_test.cidr_block}"]
  }

  vpc_id = "${aws_vpc.rds_test.id}"
}
```

And here comes the EC2 instance.

```conf
data "aws_ami" "nat" {
  most_recent      = true
  name_regex = "amzn-ami-vpc-nat-hvm-2018.03.0.20180508-x86_64-ebs"
  owners     = ["137112412989"]
}

resource "aws_instance" "rds_test_nat" {
  ami = "${data.aws_ami.nat.id}"
  availability_zone = "${data.aws_availability_zone.eu-central-1a.id}"
  instance_type = "t2.micro"
  key_name = "${aws_key_pair.my-key.key_name}"
  vpc_security_group_ids = ["${aws_security_group.rds_test_nat.id}"]
  subnet_id = "${aws_subnet.eu-central-1a-public.id}"
  associate_public_ip_address = true
  source_dest_check = false
}
```

### Internet Gateway And Route Tables

An internet gateway is what makes a subnet public. To be precise it is a route table that routes traffic between the subnet and the internet gateway which makes it be treated as public. We can create an internet gateway by providing the VPC it should be running in.

```conf
resource "aws_internet_gateway" "rds_test" {
  vpc_id = "${aws_vpc.rds_test.id}"
}
```

There needs to be one route table that routes all non-subnet traffic towards the internet gateway and one that routes all traffic towards our NAT instance.

```conf
resource "aws_route_table" "eu-central-1a-public" {
  vpc_id = "${aws_vpc.rds_test.id}"

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = "${aws_internet_gateway.rds_test.id}"
  }
}

resource "aws_route_table" "eu-central-private" {
  vpc_id = "${aws_vpc.rds_test.id}"

  route {
    cidr_block = "0.0.0.0/0"
    instance_id = "${aws_instance.rds_test_nat.id}"
  }
}
```

By associating a route tables to a subnet it becomes effective. We will assign the internet gateway route table to the public subnet and the NAT route table to the private subnet which contains the sysbench host.

```conf
resource "aws_route_table_association" "eu-central-1a-public" {
  subnet_id = "${aws_subnet.eu-central-1a-public.id}"
  route_table_id = "${aws_route_table.eu-central-1a-public.id}"
}

resource "aws_route_table_association" "eu-central-1a-private" {
  subnet_id = "${aws_subnet.rds_test_a.id}"
  route_table_id = "${aws_route_table.eu-central-private.id}"
}
```

### Adding Security Group Rules

The last thing we need to do is to adjust the firewall rules of the MySQL and sysbench security groups. In Terraform you can either provide security group rules directly within the `aws_security_group` stanza like we did for the NAT instance, or you can add the rules as individual `aws_security_group_rule` resources.

First let's configure the MySQL security group to allow incoming traffic from the sysbench security group on port 3306.

```conf
resource "aws_security_group_rule" "mysql_in" {
  type            = "ingress"
  from_port       = 3306
  to_port         = 3306
  protocol        = "tcp"
  source_security_group_id = "${aws_security_group.rds_test_sysbench.id}"

  security_group_id = "${aws_security_group.rds_test_mysql.id}"
}
```

Then we also need to add an outgoing rule to the sysbench security group towards the MySQL group. Additionally we need to accept incoming SSH traffic. Here we are going to accept SSH from anywhere, although at the moment the bastion host is the only instance which is able to reach our sysbench host.

```conf
resource "aws_security_group_rule" "mysql_out" {
  type            = "egress"
  from_port       = 3306
  to_port         = 3306
  protocol        = "tcp"
  source_security_group_id = "${aws_security_group.rds_test_mysql.id}"

  security_group_id = "${aws_security_group.rds_test_sysbench.id}"
}

resource "aws_security_group_rule" "sysbench_ssh_in" {
  type            = "ingress"
  from_port       = 22
  to_port         = 22
  protocol        = "tcp"
  cidr_blocks = ["0.0.0.0/0"]

  security_group_id = "${aws_security_group.rds_test_sysbench.id}"
}
```

## Connecting Through An SSH Tunnel

Now that everything is more or less setup, let's connect via SSH! But where to connect to? What is the address of the bastion host?

For convenience reasons we are going to assign an [Elastic IP](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/vpc-eips.html) to our NAT instance. It is required for the internet gateway to be available before the Elastic IP is created as otherwise the subnet would not be treated as public. We can declare this dependency explicitly using the `depends_on` key.

```conf
resource "aws_eip" "rds_test_nat" {
  instance = "${aws_instance.rds_test_nat.id}"
  depends_on = ["aws_internet_gateway.rds_test"]
  vpc = true
}
```

We can also generate the SSH commands we need to use in order to tunnel through the bastion host towards the sysbench instance. First we tunnel and forward traffic directed towards the local port 2201 to our sysbench private IP on port 22. Then we connect to the local port 2201.

```conf
output "ssh-tunnel" {
  value = "ssh ec2-user@${aws_eip.rds_test_nat.public_ip} -L 2201:${aws_instance.rds_test_sysbench.private_ip}:22"
}

output "ssh" {
  value = "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ubuntu@localhost -p 2201"
}
```

After we ran `terraform apply` we are good to go. We can run the SSH commands in two terminal windows.

```
$ ssh ec2-user@18.185.78.248 -L 2201:10.0.36.116:22

__|  __|_  )
_|  (     /   Amazon Linux AMI
___|\___|___|

https://aws.amazon.com/amazon-linux-ami/2018.03-release-notes/
[ec2-user@ip-10-0-22-123 ~]$
```

```
$ ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ubuntu@localhost -p 2201

Welcome to Ubuntu 16.04.4 LTS (GNU/Linux 4.4.0-1060-aws x86_64)
ubuntu@ip-10-0-33-52:~$
```

## Running The Benchmark

Sysbench supports testing different components of your system like RAM, CPU, and disk. It also supports benchmarking a MySQL database. Here is what we need to do:

1. Create a new database called `sbtest`
2. Prepare the database for our benchmark
3. Run the benchmark
4. ???
5. Profit

I am again using Terraform output variables to generate the commands required for each step.

```conf
output "sysbench_cmd_1" {
  value = "mysql -u${aws_db_instance.rds_test_mysql.username} -p${aws_db_instance.rds_test_mysql.password} -h${aws_db_instance.rds_test_mysql.address} -P${aws_db_instance.rds_test_mysql.port} -e 'create database sbtest;'"
}

output "sysbench_cmd_2" {
  value = "sysbench --test=oltp --oltp-table-size=250 --mysql-user=${aws_db_instance.rds_test_mysql.username} --mysql-password=${aws_db_instance.rds_test_mysql.password} --db-driver=mysql --mysql-host=${aws_db_instance.rds_test_mysql.address} --mysql-port=${aws_db_instance.rds_test_mysql.port} prepare"
}

output "sysbench_cmd_3" {
  value = "sysbench --db-driver=mysql --num-threads=4 --max-requests=10 --test=oltp --mysql-table-engine=innodb --oltp-table-size=250 --max-time=300 --mysql-engine-trx=yes --mysql-user=${aws_db_instance.rds_test_mysql.username} --mysql-password=${aws_db_instance.rds_test_mysql.password} --mysql-host=${aws_db_instance.rds_test_mysql.address} --mysql-port=${aws_db_instance.rds_test_mysql.port} run"
}
```

We can then execute them step by step. I am going to choose a very small table size and limit the number of threads and requests drastically. This is not recommended if you are really trying to figure out the performance of your database. But I just didn't want to pay all the requests to my RDS instance 😉.

```sh
# Create sbtest database
mysql -ufoo -pfoobarbaz \
  -hterraform-20180619122208519900000001.cuz2lrjuxtf2.eu-central-1.rds.amazonaws.com \
  -P3306 -e 'create database sbtest;'
```

```sh
# Prepare database for OLTP workload
sysbench --test=oltp --oltp-table-size=250 --db-driver=mysql \
  --mysql-user=foo --mysql-password=foobarbaz \
  --mysql-host=terraform-20180619122208519900000001.cuz2lrjuxtf2.eu-central-1.rds.amazonaws.com \
  --mysql-port=3306 prepare
```

```sh
# Run OLTP benchmark
sysbench --num-threads=4 --max-requests=10 \
  --db-driver=mysql --test=oltp --mysql-table-engine=innodb \
  --oltp-table-size=250 --max-time=300 --mysql-engine-trx=yes \
  --mysql-user=foo --mysql-password=foobarbaz \ --mysql-host=terraform-20180619122208519900000001.cuz2lrjuxtf2.eu-central-1.rds.amazonaws.com \
  --mysql-port=3306 run
```

```
OLTP test statistics:
queries performed:
    read:                            210
    write:                           58
    other:                           25
    total:                           293
transactions:                        10     (103.26 per sec.)
deadlocks:                           5      (51.63 per sec.)
read/write requests:                 268    (2767.31 per sec.)
other operations:                    25     (258.14 per sec.)
```

Et voilà. Easy, wasn't it? I believe that is enough for now. Do not forget to destroy your infrastructure once you are done experimenting.

# Discussion

We have seen how easy it is to spawn a highly available relational database within AWS. But we have also seen how complex managing the network yourself can become. Of course it is always possible to use the default components as much as possible but if you are trying to build something secure it makes sense to invest some time into this part.

I really love the granularity on which AWS allows you to configure your network. And it works super fast even if you update existing rules. Terraform supports with its built-in functions.

Packer allows you to create custom AMIs in case you cannot find any of the publicly available AMIs that fit your needs. It is a simple but powerful tool that everyone working on AWS with Terraform should be aware of.

Note that usually you set up a NAT instance to grant internet access to our private subnets without being exposed to the internet directly. However we did not configure the firewall in a way that allows traffic to flow from the components within the private subnet towards the NAT instance. We primarily used the NAT instance as a bastion host. If you require internet access from within the private instances you need to modify the NAT security group. Please see the section [Creating the NATSG Security Group](https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_NAT_Instance.html) within the AWS documentation for details.

Did you ever configure a virtual private cloud environment yourself? How does the AWS networking mechanisms compare to the ones in other major cloud providers? Let me know what you think in the comments!
