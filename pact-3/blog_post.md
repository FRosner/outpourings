---
title: Implementing a Consumer-Driven Contract Testing Workflow with Pact Broker and Gitlab CI
published: true
description: The Pact broker helps when implementing consumer-driven contract testing with Pact. How can you integrate it into your Gitlab CI pipelines?
tags: pact, tdd, devops, testing
cover_image: https://dev-to-uploads.s3.amazonaws.com/i/yial3uaa388okgrr42mj.png
canonical_url: https://blog.codecentric.de/en/2020/02/implementing-a-consumer-driven-contract-testing-workflow-with-pact-broker-and-gitlab-ci/
series: Pact
---

# Introduction
In the previous posts we learned that the Pact workflow requires you to exchange contracts and verification results between consumers and providers. We introduced two approaches on how the contract exchange can happen: 1) committing the Pact files to the provider repository, 2) make the provider fetch the Pact files.

If you decide for the second approach you can utilize the Pact broker. The broker acts as an intermediary between consumers and providers. Consumers publish contracts to the broker and providers can download them. Additionally, providers can publish verification results. By checking the verification results, consumers can determine whether it is safe to deploy a specific version to an environment.

In this post you will learn how the Pact broker can support your development workflow. The post is structured as follows. The first part is going to elaborate on the different features of the broker from a theoretical point of view. The second part will be more practical, focusing on how to integrate the broker into your build pipeline. Afterwards we are discussing potential challenges when implementing a Pact broker based workflow. The final section summarizes the main findings and closes the post.


# Pact Broker Features
The Pact broker provides different features that can be used in different parts of your development workflow: exchanging contracts, exchanging verification results, tagging, and webhooks. Let’s look into each one in detail.
## Exchanging Contracts
Whenever a consumer generates a new contract it usually needs a verification from all its providers. Consumers can publish new contracts to the broker and providers can pull them when running the verification tests. But how does the provider know which contract it needs to verify?

The broker requires you to assign a consumer version for every contract you publish. This version should represent the software version of your consumer. It does not have to follow any specific naming scheme, such as semantic versioning. It is common to take the commit hash so you can easily understand which version of your code is linked to this contract.

When running a provider verification the provider needs to specify the consumer version it wants to verify. The broker will then return the latest version of the contracts for that specific consumer version.

## Exchanging Verification Results
As soon as the verification is finished, the provider can publish the results back to the broker. Each verification result is associated with a provider version. The broker will then use both the consumer version of the contract that has been verified and the provider version that reported the verification results to update its verification matrix.

![verification matrix](https://dev-to-uploads.s3.amazonaws.com/i/7od3n781871noa5g6yb4.png)

The verification matrix stores the verification results and the fact that a verification took place based on the consumer version, provider version, contract version, and tags.

This is useful if you want to check the compatibility between a specific consumer and provider version. You can simply query the matrix without the need of running another verification test. An implementation of this compatibility check is the [`can-i-deploy`](https://docs.pact.io/pact_broker/can_i_deploy) command line tool. You can specify the different pacticipant versions you want to deploy together and it will tell you whether it is safe to do so.

If we want to check whether it is safe to deploy to *production*, however, how do we know which versions are currently in production? Also, how can we check whether a feature branch of a consumer would be safe to merge? This is where tags come in.
## Tagging
The broker allows you to assign a tag to a pacticipant version. Tags can be used in any way you like but the following two use cases are common:

1. Indicate that a version is deployed in a specific environment by tagging the environment name (e.g. `test` or `prod`).
2. Indicate that a version is part of a feature branch by tagging the branch name (e.g. `ABC-123/new-login`).

Tagging the environment name is useful when executing `can-i-deploy` so that you don’t have to know the exact versions of your pacticipants but can simply ask: Is it safe to deploy this specific version to production?

Tagging the feature branch name on the other hand allows you to publish and verify the contracts of a new feature before merging the branches in all pacticipants. By tagging your consumer versions with the feature branch name, providers can verify the latest version of that feature. If you choose the same name for both the consumer and the provider branch, you can run provider verifications of the consumer branch from your provider branch.
## Webhooks
Webhooks can be used to notify other components in your development workflow about changes in the broker. They can be configured for the following events:

- Contract published
- Contract published with changed content, updated or new tags
- Verification results published

Additionally you can specify whether only certain consumers or providers should be considered. Whenever such an event occurs, the broker will send an HTTP request to the URL you configured.

You can specify an HTTP header and body of that request, as well as basic authentication if required. Additionally, there are some [dynamic variables](https://github.com/pact-foundation/pact_broker/blob/master/lib/pact_broker/doc/views/webhooks.markdown#dynamic-variable-substitution) that you can use in order to customize the request:

- Consumer and provider name
- Consumer and provider version number
- Consumer and provider version tags
- Consumer and provider labels
- URL to the contract on the broker
- URL to the verification result on the broker

This allows custom integrations with your build pipelines or other tools such as Jira or Slack. The next section will guide you through an example setup of the build pipelines in Gitlab.
# Pimping your Build Pipeline
Now that we discussed all the different parts of the Pact broker we want to put it to practical use. The following subsections feature an example setup including a consumer repository, a provider repository, a Pact broker and Gitlab build pipelines.
## Example Setup

Continuing the example of our [first blog post](https://dev.to/frosnerd/consumer-driven-contract-testing-with-pact-1a57), we are looking at a front-end consumer which uses the login functionality of a user service provider. The following diagram illustrates the actors / components relevant to our scenario.

![example setup](https://dev-to-uploads.s3.amazonaws.com/i/5bt0kd7wpjwreqo7f7an.png)

The consumer publishes contracts to the Pact broker via the pipeline. A webhook on newly published contracts triggers the respective provider verifications. The results of the provider verification are published to the broker. By creating version tags after successful deployments we enable the use of the `can-i-deploy` to check if a change can safely be deployed to production.

For the examples in this chapter we are using Gitlab CI build pipelines defined in `.gitlab-ci.yml` files. Each pipeline run consists of multiple stages where the preceding stage has to succeed for the next one to begin. Build artifacts are passed between the stages. The following stages are going to be relevant in the next subsections.

```yaml
stages:
 - build
 - publish # (consumer only)
 - can-i-deploy
 - deploy
 - tag
```
## Consumer pipeline: Generating and publishing contracts
In the pipeline of the `login-view` consumer we are generating the contracts during the build stage. We can then either immediately publish the generated contracts, or pass them as build artifacts to the following stages. The following code snippet illustrates a pipeline job that generates the contracts into the `pacts` folder that then gets exported as a build artifact by Gitlab.

```yaml
pact-test:
  image: node:latest
  stage: build
  script:
    - "npm run test:pact"
  artifacts:
    paths:
      - pacts
```

The follow-up job then uses the `pact-broker` executable from the `pactfoundation/pact-cli` Docker image to publish the contracts it picked up from the previous stage to the broker.

```yaml
pact-publish:
  image: pactfoundation/pact-cli:latest
  stage: publish
  script:
    - "pact-broker publish pacts
        --consumer-app-version=$CI_COMMIT_SHORT_SHA
        --tag=$CI_COMMIT_REF_NAME
        --broker-base-url=$PACT_BROKER_BASE_URL
        --broker-token=$PACT_BROKER_API_TOKEN"
```

We are using the current git commit hash as the consumer version and tagging it with the current branch name. The config options `broker-base-url` and `broker-token` are set via manually configured environmental variables. It is possible to define them in an overarching Gitlab group so that they are exposed to multiple projects.

Having the consumer pipeline in place that publishes new contracts, let’s investigate how to trigger provider verification tests through a Gitlab pipeline.
## Provider pipeline: Executing verification tests

As explained in the introduction, the Pact broker can act upon published contracts. In order to make the broker trigger a Gitlab pipeline through a webhook, we first need to [create a pipeline token](https://docs.gitlab.com/ee/ci/triggers/) in the `user-service`. We then use the resulting pipeline trigger to create a webhook on the Pact broker which acts on contract modifications.

The following JSON payload represents a webhook resource on the broker:

```json
{
  "description": "Trigger user-service verification",
  "provider": { "name": "user-service" },
  "enabled": true,
  "request": {
    "method": "POST",
    "url": "https://gitlab.com/api/v4/projects/1122344/ref/master/trigger/pipeline?token=12345678&variables[PACT_CONSUMER_TAG]=${pactbroker.consumerVersionTags}",
    "body": ""
  },
  "events": [{ "name": "contract_content_changed" }]
}
```

We are passing a variable `PACT_CONSUMER_TAG` to the pipeline that we can use in our build script to pull the correct contract for the verification. The broker replaces `${pactbroker.consumerVersionTags}` automatically.

As we do not want to run a full pipeline but only the verification tests, we need to make use of the [`only` and `except` keywords](https://docs.gitlab.com/ee/ci/yaml/#onlyexcept-basic). The following YAML snipped illustrates the pipeline job definition.

```yaml
pact-verify:
  stage: build
  script:
   - ./gradlew pactTest
  only:
   - triggers
```

In this case, the job will only be executed if the pipeline is triggered through the API and not in regular builds. To avoid running all the jobs in a triggered build, you will have to exclude triggers on all other steps.

In the example above we run the Pact verification tests through a custom gradle task `pactTest`. It pulls the correct Pact from the broker by evaluating the `System.env.PACT_CONSUMER_TAG` variable which was sent with the webhook. If the tests are configured correctly, the verification results will be published to the Pact broker. Each success and each failure is associated with both the consumer version and the provider version.

After successfully implementing the part of the provider pipeline that published verification results to the broker we can utilize the verification matrix to check which pacticipant versions are compatible and if it is safe to deploy a certain version to production.
## Can I deploy?
The `can-i-deploy` command queries the verification matrix. To answer the important question “Can I deploy this change to production?”, however, we first need to let the Pact broker know what pacticipant versions are currently running in production.

This can be accomplished using the `create-version-tag` command. Simply place it inside a pipeline job that gets executed right after a successful deployment. The following YAML snippet defines a `pact-tag` job that creates a version tag `production` based on the pacticipant version that was deployed.

```yaml
pact-tag:
  image: pactfoundation/pact-cli:latest
  stage: tag
  script:
    - "pact-broker create-version-tag
        --pacticipant=user-service
        --version=$CI_COMMIT_SHORT_SHA
        --tag=production
        --broker-base-url=$PACT_BROKER_HOST
        --broker-token=$PACT_BROKER_API_TOKEN"
  only:
    refs:
      - master
```

If you have a multi-stage deployment you can add different jobs at different stages that create version tags based on the environment, e.g. development or staging.

With the tagging in place we can further extend our pipelines to include a job before actually deploying that executes `can-i-deploy` and aborts the pipeline in case we were about to break something. The following YAML extract contains the definition of a `pact-can-i-deploy` job inside the login view project.

```yaml
pact-can-i-deploy:
  image: pactfoundation/pact-cli:latest
  stage: can-i-deploy
  script:
    - "pact-broker can-i-deploy
         --pacticipant login-view
         --version $CI_COMMIT_SHORT_SHA
         --to production
         --broker-base-url $PACT_BROKER_BASE_URL
         --broker-token $PACT_BROKER_API_TOKEN"
```

There are multiple ways to invoke the `can-i-deploy` command. For our use case we are going to specify the pacticipant, its version, and the stage to deploy to. In other words, we are checking if a positive verification result exists between the user service version that is running in production and the login view version that we are currently trying to deploy.

If this job fails and your pipeline stages are configured correctly, a missing verification will bring your pipeline to a halt. Note that a failing `can-i-deploy` does not always mean incompatible versions. It can also mean that the verification results are still pending. Based on how you configure your pipelines there can be a race between provider verifications and consumer pipelines attempting to deploy.
# Challenges
While the Pact broker is an extremely convenient way to share and verify Pacts, there are some obstacles we were facing during adoption that we would like to share.

When using the Pact broker, some challenges of distributed software development suddenly become visible. While this is not a shortcoming per se it can be confusing to developers at times, e.g. when your build is failing due to a missing verification but you do not immediately see why this verification is missing.

Additionally, it can be very difficult to implement a development workflow that integrates version control, your build server and the pact broker while being easy to use and fitting your processes. As always, the devil is in the details. Your setup looks differently depending on whether you use feature branches or do trunk based development, whether you use Gitlab CI or Jenkins, and whether you deploy only to one or multiple environments.

While webhooks give you the possibility to customize your integrations, there are not many pre-built integrations available, yet. We built a custom Slack application that notifies developers when new contracts or verification results are published and allows you to manually trigger provider verifications. Another nice feature would be to have merge request integration that tells you whether it is safe to merge a branch into another one based on the verification matrix.

You should also keep in mind that Pact is a rather new technology and documentation is scattered across different projects and websites. We’ve spent weeks figuring out all the details until we ended up with a usable Pact broker integration. We can recommend the hosted Pact broker service of [pactflow.io](https://pactflow.io/) which also features an updated, more streamlined user interface to at least take away the hassle of operating the broker yourself.
# Summary
In this post we have seen how you can use the Pact broker to support your consumer-driven contract testing workflow. The broker facilitates the exchange of contracts between consumers and providers, integrates other tools through webhooks, and can be used to store and query verification results.

We also demonstrated how to integrate the broker into your Gitlab CI pipelines. We looked at a job definition to publish contracts, how to trigger provider verification test jobs, how to tag pacticipant versions, as well as a job that queries the verification matrix before deploying to production.

Although the Pact broker is a very useful tool when implementing consumer-driven contract testing, setting everything up can be challenging and time-consuming. You will have to read a lot of documentation, or even source code. Nevertheless in the end we felt that it was worth the effort as the broker made the whole workflow more transparent and reliable.

Have you ever used the Pact broker? Did you set it up yourself or did you use the hosted solution? Would you do it again in the next project? Let us know!

---

This post was co-authored by [Raffael Stein](https://dev.to/rafaroca)
