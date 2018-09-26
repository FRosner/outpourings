---
title: Yarnception: Starting Yarn Within Yarn Through Gulp and When It Is Useful
published: true
description: In this post we are going to use a combination of Yarn, Yarn workspaces, Gulp, and Terraform to manage a Node.js AWS Lambda monorepository.
tags: aws, node, serverless, javascript
cover_image: https://thepracticaldev.s3.amazonaws.com/i/ibtasvtfc4q8220sccdz.jpg
---

# Introduction

When developing new services I personally prefer to design them with a clear purpose and well defined boundaries. I also like to keep all source code for one service inside the same version control repository. When you setup a new project containing multiple infrastructure components of a cloud provider such as AWS it is convenient to manage your infrastructure state inside the same repository (see my previous post on [Infrastructure as Code](https://dev.to/frosnerd/infrastructure-as-code---managing-aws-with-terraform-i9o)).

If you are storing source code for multiple AWS Lambda functions next to files describing your infrastructure, e.g. [Terraform](https://www.terraform.io/) files, you might want to use a single build tool to manage the whole application lifecycle:

- Checking formatting
- Compiling / linting
- Executing unit tests
- Packaging
- Executing integration tests
- Deployment
- Delivery

I like to use [Yarn](https://Yarnpkg.com/en/) as a package manager for my JavaScript applications but also to manage the application lifecycle. Although there is no first class lifecycle support like in [Maven](https://maven.apache.org/) or [SBT](https://www.scala-sbt.org/), you can build something usable yourself using [scripts](https://Yarnpkg.com/lang/en/docs/cli/run/) inside your `package.json`.

Wouldn't it be nice to be able to use Yarn not only for the lifecycle of a single Node.js Lambda function but the whole monorepository, including your Terraform files, and all different Lambda functions you might be using? I found a convenient way for myself to do that using a combination of **Yarn**, **Yarn workspaces**, **Gulp**, and **Terraform**. In this blog post I want to share my blue print.

The remainder of the post is structured as follows. First we will take a look at an overview of the project setup. Afterwards we will go into detail about the role of Yarn workspaces. The following two sections are going to discuss the deployment package creation and the actual deployment. We are closing the post by discussing the main findings.

# Project Setup

To execute the blue print I am using Yarn 1.7.0 and Terraform 0.11.7. All the other dependencies are defined within the respective `package.json` files. The [source code](https://github.com/FRosner/multi-aws-lambda-nodejs-example) is available on GitHub.

The project structure is depicted in the listing below. We define the overall structure and scripts inside the top level `package.json`. Then there are the two Node.js modules that contain the Lambda function handlers `calculator` and `concatenator`. They have individual `package.json` files which contain different dependencies. Each module also has a `gulpfile.js` which will be used to create the deployment packages. The `terraform` folder contains the Terraform files.

```
├── package.json
├── yarn.lock
├── lambda
│   ├── calculator
│   │   ├── gulpfile.js
│   │   ├── package.json
│   │   ├── src
│   │   │   └── lambda.js
│   │   └── test
│   │       └── lambdaSpec.js
│   └── concatenator
│       ├── gulpfile.js
│       ├── package.json
│       ├── src
│       │   └── lambda.js
│       └── test
│           └── lambdaSpec.js
└── terraform
    ├── calculator.tf
    ├── concatenator.tf
    ├── providers.tf
    └── variables.tf
```

# Yarn Workspace Configuration

Yarn workspaces are a convenient way to manage multiple Node.js modules within a single repository. It is to some extent comparable to [SBT subprojects](https://www.scala-sbt.org/0.13/docs/Multi-Project.html) or [Maven modules](https://maven.apache.org/guides/mini/guide-multiple-modules.html). All you need to do is to create a top-level `package.json` and specifiy the workspaces you need.

If you execute `yarn install` it will install all workspaces. For custom scripts I like to use the [wsrun](https://www.npmjs.com/package/wsrun) package, which executes a Yarn script within all workspaces. Here's what the top-level `package.json` looks like.

```json
{
  "private": true,
  "workspaces": [
    "lambda/*"
  ],
  "scripts": {
    "format:test": "prettier --config '.prettierrc.json' --list-different '**/*.js' && (cd terraform && terraform fmt -check=true -list=true)",
    "format:fix": "prettier --config '.prettierrc.json' --write '**/*.js' && (cd terraform && terraform fmt -write=true)",
    "lint:test": "eslint --config .eslintrc.json '**/*.js'",
    "lint:fix": "eslint --config .eslintrc.json '**/*.js' --fix",
    "terraform:init": "set -e; (cd terraform && terraform init)",
    "terraform:apply": "set -e; (cd terraform && terraform apply -auto-approve)",
    "terraform:destroy": "set -e; (cd terraform && terraform destroy -auto-approve)",
    "clean": "yarn wsrun clean && rm -rf node_modules",
    "test": "yarn wsrun test",
    "package": "yarn wsrun package",
    "deploy": "yarn package && yarn terraform:apply",
    "destroy": "yarn package && yarn terraform:destroy"
  },
  "devDependencies": {
    "eslint": "^5.5.0",
    "prettier": "^1.14.2",
    "terraform-npm": "^0.2.6",
    "wsrun": "^2.2.1"
  }
}
```

The individual workspaces typically have regular `package.json` files although there are some configuration options regarding workspaces as well. But we are not going to go into detail within this post. Next let's look how the `package` scripts are defined within the two modules.

# Generating the Deployment Packages

When working with Node.js on AWS Lambda the recommended way to create a [deployment package](https://docs.aws.amazon.com/lambda/latest/dg/nodejs-create-deployment-pkg.html) is to zip your whole source code including all required Node.js modules. Other methods like [browserify](http://browserify.org/) were not officially supported in the past and people encountered problems when using the AWS JavaScript SDK together with it.

Luckily Gulp provides a convenient way to automate the workflow of creating the deployment package as required by AWS. Inspired by a [A Gulp Workflow For Amazon Lambda](https://medium.com/@AdamRNeary/a-gulp-workflow-for-amazon-lambda-61c2afd723b6), I created a [`gulpfile.js`](https://github.com/FRosner/multi-aws-lambda-nodejs-example/blob/master/lambda/calculator/gulpfile.js) which defines five different tasks:

- `clean` removes the `stage` and `dist` folders
- `install` installs all production dependencies inside `stage/node_modules` using Yarn
- `copySrc` copies all source files inside `stage`
- `bundle` zips the content of `stage` into `dist`
- `default` executes all four previous tasks in order for to get a reproducible build

Now we can define the `yarn package` script to simply call `gulp`. It will then wipe the state from previous builds, install only the required dependencies for the current module, copy the source files, and zip the whole bundle.

# Deployment and Delivery

Deployment and delivery is done with Terraform. We first define the required resources, i.e. [`calculator.tf`](https://github.com/FRosner/multi-aws-lambda-nodejs-example/blob/master/terraform/calculator.tf), and [`concatenator.tf`](https://github.com/FRosner/multi-aws-lambda-nodejs-example/blob/master/terraform/concatenator.tf). At this point we only need to reference the respective zip files created in the previous step as the filename of the deployment package. Whenever we run `yarn deploy` in the top-level, it will first execute `yarn package` inside all Lambda workspaces and then deploy and deliver the changes via `terraform apply`.

If you want to decouple the deployment and delivery step, you can upload the artifacts to an S3 bucket first and [specify the location](https://www.terraform.io/docs/providers/aws/r/lambda_function.html#specifying-the-deployment-package) inside the resources. This is also recommended for larger deployment packages as the S3 API has better support for larger files.

# Conclusion

In this post we have seen how you can manage Node.js AWS Lambda monorepositories with a combination of Yarn, Yarn workspaces, Gulp, and Terraform. Yarn acts as a package manager and top-level build tool. Yarn workspaces allow efficient and flexible management of different Node.js modules within the same repository. Gulp enables us to install only the required production dependencies for every module within the `stage` folder and create a minimal deployment package. Terraform is used to deploy your infrastructure to AWS.

As always there are many ways to accomplish a task. I hear from people that the [serverless framework](https://serverless.com/) does similar things but I don't know if it supports all the different resources that Terraform does. If anybody knows, please comment down below! I personally do not have any experience with it as of today.

I also stumbled upon [Lerna](https://lernajs.io/) but I could not find any benefit over using Yarn workspaces directly, as they are supporting all the features I need natively. But maybe you can spot something I missed? Please comment below!

Do you prefer monorepositories or individual repositories for all your Lambda functions? Did you ever use the serverless framework or Terraform? Would you prefer Lerna or native Yarn workspaces? I'm curious about your experience and opinion :)

---

Cover image by [Marco Verch](https://flic.kr/p/XhpEMo).
