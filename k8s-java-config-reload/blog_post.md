---
title: Automatic Configuration Reloading in Java Applications on Kubernetes
published: true
description: How can you implement automatic configuration reloading in your Java application without pod restarts in Kubernetes?
tags: java, kubernetes, cloud, devops
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/ducuaj779zjzvo3vljfu.jpg
---

# Introduction

Applications developed for Kubernetes following the [twelve-factor methodology](https://12factor.net/) are typically straightforward to operate. The third factor governs [application configuration](https://12factor.net/config). Twelve-factor apps should strictly separate configuration from code, making it easy to deploy them to different environments without code changes. They should also store configuration as environment variables, since they are language- and OS-agnostic.

If there are special quality requirements however, you might want to deviate from that principle. Let's take a stateful, highly available application, such as a distributed database, for example. Since Linux assigns environment variables to a process on startup, it is not (easily) possible to change them without restarting the process.

In Kubernetes terms, this means any change to the environment variables of a deployment will roll its pods. If your application is stateful, this can be costly, since state has to be migrated when pods get restarted, making a configuration change a non-trivial operation.

Luckily, there are other ways to implement configuration changes that do not require pod restarts. One of them is to store your application configuration in a config map and mount it into your containers. When you update the config map, Kubernetes will eventually update the mounted files as well and your application can read the updated configuration.

In this blog post we want to take a look at how to implement that mechanism inside a Java application. The remainder of the post is structured as follows. First, we will implement our Java application which supports automatic configuration reloading. The following section describes how to deploy it to Kubernetes. We are closing the post by discussing and summarizing the findings. The [source code](https://github.com/FRosner/k8s-java-config-reload) is available on GitHub.

# Implementation

When it comes to configuration management on the JVM, there are many options. One of the "old hands" in the business is [Apache Commons Configuration](https://commons.apache.org/proper/commons-configuration/index.html). It provides a generic configuration interface to manage Java application configuration coming from various sources since 2005.

Apache Commons Configuration also supports [automatic reloading](https://commons.apache.org/proper/commons-configuration/userguide/howto_reloading.html) of configuration sources, which is what we are going to use to reload the changes to our configuration file which will be mounted inside the container.

First, let's define a `ConfigReloader` class that encapsulates the periodic configuration reloading and exposes a method to retrieve the latest configuration. To accomplish periodic reloading, we need two components: A `ReloadingFileBasedConfigurationBuilder` and a `PeriodicReloadingTrigger`.

The `ReloadingFileBasedConfigurationBuilder` is responsible for reloading the configuration file and we will set it up to work with a given properties file. The `PeriodicReloadingTrigger` triggers the builder to check for modifications on the file and reload it if necessary at a given interval. The following code snippet shows our implementation of the `ConfigReloader` class.

```java
import java.io.File;
import java.util.concurrent.TimeUnit;
import org.apache.commons.configuration2.Configuration;
import org.apache.commons.configuration2.FileBasedConfiguration;
import org.apache.commons.configuration2.PropertiesConfiguration;
import org.apache.commons.configuration2.builder.ReloadingFileBasedConfigurationBuilder;
import org.apache.commons.configuration2.builder.fluent.Parameters;
import org.apache.commons.configuration2.ex.ConfigurationException;
import org.apache.commons.configuration2.reloading.PeriodicReloadingTrigger;

public class ConfigReloader implements AutoCloseable {

  private final PeriodicReloadingTrigger trigger;
  private final ReloadingFileBasedConfigurationBuilder<FileBasedConfiguration> builder;

  public ConfigReloader(String configFilePath) {
    Parameters params = new Parameters();
    File propertiesFile = new File(configFilePath);
    builder = new ReloadingFileBasedConfigurationBuilder<FileBasedConfiguration>(
        PropertiesConfiguration.class)
        .configure(params.fileBased().setFile(propertiesFile));
    trigger = new PeriodicReloadingTrigger(
        builder.getReloadingController(),
        null, 1, TimeUnit.SECONDS);
    trigger.start();
  }

  public Configuration getConfig() {
    try {
      return builder.getConfiguration();
    } catch (ConfigurationException cex) {
      throw new RuntimeException(cex);
    }
  }

  @Override
  public void close() {
    trigger.stop();
  }
}
```

Note that in order to return the latest configuration, we must query the builder on each request. Internally, it will keep a reference to the current configuration that gets updated atomically after a successful reload. This way, we guarantee to the callers of `ConfigReloader.getConfig` that the returned configuration does not update while it is in use.

Next, let's implement a main class that will print something to the standard output stream based on the current configuration value. First, we initialize the `ConfigReloader` with a path to a properties file that will later be mounted inside the container. Then we endlessly print a greeting message to a configurable user at a configurable interval. Here goes the code.

```java
import java.util.Date;
import org.apache.commons.configuration2.Configuration;

public class App {

  public static void main(String[] args) throws InterruptedException {
    try (ConfigReloader configReloader = new ConfigReloader("/config/config.properties")) {
      while (true) {
        Configuration config = configReloader.getConfig();
        String name = config.getString("name");
        int sleepInterval = config.getInt("sleepIntervalMillis");
        System.out.println(String.format("Hello %s, it is %s", name, new Date()));
        Thread.sleep(sleepInterval);
      }
    }
  }
}
```

# Deployment

In order to deploy our application to Kubernetes, we first need to bake it into a Docker image. We are going to utilize the Jib Maven plugin:

```xml
<plugin>
  <groupId>com.google.cloud.tools</groupId>
  <artifactId>jib-maven-plugin</artifactId>
  <version>3.0.0</version>
  <configuration>
    <to>
      <image>k8s-java-config-reload</image>
    </to>
  </configuration>
</plugin>
```

To test it, we can start a minikube cluster and build the image directly with the minikube Docker daemon:

```bash
minikube start
eval $(minikube docker-env)
mvn compile jib:dockerBuild
```

Next, we create a new config map manifest containing the properties file.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-java-config-reload-configmap
data:
  config.properties: |-
    name=Frank
    sleepIntervalMillis=1000
```

We then create a pod manifest and tell Kubernetes to mount the config map into the container. Note that in production, you probably want to use a more sophisticated mechanism to deploy your application, such as a deployment. But for the sake of this example, a pod is perfectly fine.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: k8s-java-config-reload-pod
spec:
  containers:
    - image: k8s-java-config-reload
      name: k8s-java-config-reload
      imagePullPolicy: IfNotPresent
      volumeMounts:
        - name: config-volume
          mountPath: /config
  volumes:
    - name: config-volume
      configMap:
        name: k8s-java-config-reload-configmap
  restartPolicy: Always
```

We can then deploy both resources using `kubectl` and the application should load the configuration file and start greeting Frank. When following the container logs and updating the config map we can observe how the greetings change.

{% asciinema 411280 %}

# Discussion and Summary

As you can see from the demo, it takes a bit of time until the config change is propagated entirely. The reason for this is that kubelet syncs the mounted config maps in the pod once every minute (see [`--sync-frequency`](https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/)). It also caches existing config map data which has to be invalidated before the new value becomes visible to the container. Additionally, we have the periodic reloading delay inside our Java program. Note that you can trigger an immediate reload of the config map by updating one of the pod's annotations, e.g. by storing a hash of the config map contents in a pod annotation.

If you need your configuration changes to be rolled out more immediate, there are other options as well. Rather than reading from a properties file, you could use a key-value store such as [Consul](https://www.consul.io/), [etcd](https://etcd.io/), or [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html). While this gives you more direct control of configuration changes, it introduces new challenges. First, managing your configuration as code might require additional tooling, such as defining them as Terraform resources. Additionally, your application will have to know how to speak to the configuration services, including a proper authentication mechanism.

Another use case where the mounted configmap approach falls short is when you want to reload application secrets, such as credentials, without restarting the pod. In this case, using a central configuration store / secrets manager in combination with an application-internal cache is a good option. The cache can be invalidated once a 401 is hit. This way, rotating the secret inside the secrets manager will eventually propagate to all pods and you do not have to store your secrets in files.

To summarize, I would suggest following the twelve-factor methodology and passing your configuration as environment variables if possible. If you need to support hot reloading of configuration, and you are fine that this happens with a bit of delay, choosing the config map file mount based solution described in this post is a good option. It relies only on Kubernetes internal mechanisms and basic file system operations from within your application, without the need for special protocols or authentication. Central configuration stores are a viable alternative as well, especially when managing application secrets.

---

Cover image by <a href="https://unsplash.com/@guibolduc?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Guillaume Bolduc</a> on <a href="https://unsplash.com/s/photos/container?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
  