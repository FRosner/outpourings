---
title: Using a Private GitHub Repository as a Helm Chart Repository
published: true
description: In this post I am going to walk you through the steps needed to set up a private GitHub repository to use it as a private Helm chart repository.
tags: kubernetes, helm, git, github
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/b7nfiyj5i7rtengm79al.jpg
---

# Introduction

Applications deployed on Kubernetes typically consist of multiple Kubernetes resources, such as deployments, services, config maps, and so on. Application developers can package those resources together to make it easier to install and upgrade them holistically. Helm is a very popular package manager for Kubernetes.

When using Helm, applications are packaged in the form of Helm charts, which can be installed either from the local file system or from a remote chart repository. If you want to distribute your Helm charts through a chart repository, there are many options available, such as GCS or S3 buckets, GitHub pages, or JFrog Artifactory. A [chart repository](https://helm.sh/docs/topics/chart_repository/) is really just an HTTP server that hosts an `index.yaml` file together with a bunch of packaged charts in form of `.tgz` files.

If you need your chart repository to be private, i.e. password protected, and you do not have an S3 bucket or JFrog Artifactory handy, you can convert any private GitHub repository into a private chart repository. While GitHub pages is typically recommended as a free alternative, I have not found a way to implement a private chart repository using GitHub pages.

In this post I am going to walk you through the steps needed to set up a private GitHub repository to use it as a private Helm chart repository. The post is structured as follows. First, we will introduce the Helm chart repository structure. Afterwards, we are going to explain how to use a private GitHub repository as a Helm chart repository. The next section illustrates how to push to the repository via a GitHub Actions workflow. We are following up by explaining how to install charts from the newly created repository. The post is closed by discussing advantages and disadvantages of the presented approach.

# Chart Repository Structure

As mentioned already in the introduction, the main component of any chart repository is the index file. The index file is a YAML file called `index.yaml` and it contains metadata about all the packages, including the information of the respective `Chart.yaml` files. Each entry in the index file also points to the location of the chart package, which is a `.tgz` file.

Note that it is not mandatory for the `.tgz` files and the `index.yaml` to be co-located, but it is often the case. The following listing shows an example repository layout.

```
.
|- index.yaml
|- mychart-0.1.2.tgz
|- mychart-0.2.0.tgz
|- yourchart-1.0.0.tgz
```

In this case, the index file would contain information about the two charts `mychart` and `yourchart` in the respective versions. Next, let's see how we can configure a private GitHub repository so that we can use it as a chart repository.

# Private GitHub Chart Repository Setup

First, you'll have to create a [private GitHub repository](https://docs.github.com/en/get-started/quickstart/create-a-repo) that will function as the chart repository. Inside, you configure a new GitHub Actions workflow by creating a file called `.github/workflows/update-index.yml` with the following content: 

```yaml
# yourorg/helm-chart-repository/.github/workflows/update-index.yml
name: Update Index

on:
  push:
    branches: [ main ]
    paths:
      - '**.tgz'

jobs:
  build:
    runs-on: ubuntu-20.04
    steps:
      - name: Git Checkout
        uses: actions/checkout@v2
      - name: Helm Installation
        uses: azure/setup-helm@v1.1
        with:
          version: v3.7.0
      - name: Update Index
        run: |
          helm repo index .
          git config --global user.email "yourbot@yourorg.com"
          git config --global user.name "YourOrg Bot"
          git add index.yaml
          git commit -m "Update chart index"
          git push
```

This file defines a workflow that updates the helm repository index file every time a chart package (`.tgz`) is updated. It then commits and pushes the changes. To publish a new chart version, simply commit a packaged version of your chart (`.tgz`). You can package your chart using `helm package`:

```bash
helm package $CHART_NAME --version "$CHART_VERSION"
```

After you pushed your changes, the GitHub Actions workflow will run and update the repository index file. The index file is going to look similar to the following one:

```yaml
# yourorg/helm-chart-repository/index.yaml
apiVersion: v1
entries:
  my-chart:
  - apiVersion: v2
    appVersion: 0.1.0
    created: "2021-11-09T19:05:08.827079146Z"
    description: My chart is amazing
    digest: 399637d8794fd211d5e63e4bb77e40ab9f2292ab0d5394fb607e878225e70e2e
    name: my-chart
    type: application
    urls:
    - my-chart-0.1.0+fa0e2a7.tgz
    version: 0.1.0+fa0e2a7
  - apiVersion: v2
    appVersion: 0.1.0
    created: "2021-11-09T19:05:08.69877266Z"
    description: My chart is amazing
    digest: 24ce7b3276ed063f245213d8f8dbd18f07d9fb083747771f7ace55271bfe91ea
    name: my-chart
    type: application
    urls:
    - my-chart-0.1.0+0ac530b.tgz
    version: 0.1.0+0ac530b
generated: "2021-11-09T19:05:08.690772398Z"
```

Now that we have the Helm chart repository configured and know how to push new charts to it manually, let's see how to automate this in another GitHub Actions workflow.

# Pushing to the Private Repository from Another Workflow

Imagine we are storing the source code of a Helm chart in another GitHub repository, and you want to package and push any changes automatically to the chart repository we created. We can accomplish this by creating another GitHub Actions workflow file with the following content:

```yaml
# yourorg/my-chart/.github/workflows/helm.yml
name: Helm

jobs:
  publish:
    runs-on: ubuntu-20.04
    steps:
      - name: Chart Checkout
        uses: actions/checkout@v2
      - name: Helm Installation
        uses: azure/setup-helm@v1.1
        with:
          version: v3.7.0
      - name: Helm Repository Checkout
        uses: actions/checkout@v2
        with:
          repository: yourorg/helm-chart-repository
          token: ${{ secrets.YOUR_BOT_GH_TOKEN }}
          fetch-depth: 0
          persist-credentials: true
          ref: main
          path: helm-chart-repository
      - name: Helm Package
        run: helm package my-chart --version "0.1.0+$(git rev-parse --short "$GITHUB_SHA")" -d helm-chart-repository
      - name: Helm Push
        env:
          GITHUB_TOKEN: ${{ secrets.YOUR_BOT_GH_TOKEN }}
        run: |
          git config --global user.email "yourbot@yourorg.com"
          git config --global user.name "YourOrg Bot"
          CHART_PACKAGE_NAME="my-chart-0.1.0+$(git rev-parse --short "$GITHUB_SHA").tgz"
          cd helm-chart-repository
          git add "$CHART_PACKAGE_NAME"
          git commit -m "$CHART_PACKAGE_NAME"
          git push origin main
```

This workflow is going to run in the source code repository and will package up your chart, commit and push it to the chart repository. Note that you will need to grant permissions to the workflow to push changes to the chart repository. This can be achieved by providing a GitHub API token in a secondary `checkout@v2` action that has the required permissions (e.g. full access to org repos).

# Installing from the Private Repository

Now that we've seen how to set up our private chart repository and how to push to it, let's use it to install a chart! First, you have to add the repository to your local Helm repository list. To authenticate, you must provide a GitHub API token that can read from the chart repository. It has to be provided using HTTP Basic Auth but it does not seem to matter whether you provide it as username, password, or both.

```bash
helm repo add yourorg \
  --username "${GITHUB_TOKEN}" \
  --password "${GITHUB_TOKEN}" \
  "https://raw.githubusercontent.com/yourorg/helm-chart-repository/main/"
```

Once the repository is added, you can search it or install charts from it. Note that you'll have to update the local repository index when looking for new versions. 

```bash
helm repo update
helm search repo my-chart --devel
```

And that's it! This is how you can transform any private GitHub repository into a private Helm chart repository.

# Discussion

Before we end the post, I want to note that this solution is far from ideal. It is one possible option in your tool belt and might be great if you need to setup something but have no access to other alternatives. There are some caveats, however.

First, although this solution gives you a private repository, access management is not very flexible. You need to use API keys that can be difficult to manage and might have too wide permissions. Also, a chart developer can easily use their permission to overwrite other charts / publish new versions of other charts, injecting malicious code. Secondly, it requires setup both on the repository side but also every project that wants to push to the repository. This can be quite tedious, compared to a managed solution such as Artifactory. Thirdly, you are limited by GitHub repository limits. They shouldn't hit you too soon but are still something to be aware of.

In my opinion it would be sufficient for many use cases if it was possible to install charts directly from git. You simply specify a git repository and a version (hash) to use when running `helm install` and it pulls the chart from git directly. I see the benefit of the simple repository API (webserver + `index.yaml`) but still, installing from git would be an amazing feature.

---

Cover image by <a href="https://unsplash.com/@loik_marras?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Loik Marras</a> on <a href="https://unsplash.com/s/photos/helm?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
  