---
title: Server Name Indication (SNI)
published: true
description: SNI is a TLS extension that allows a client to specify the hostname it is trying to reach in the first step of the TLS handshake process, enabling the server to present multiple certificates on the same IP address and port number.
tags: networking, cloud, security
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/3wqkb93i9i177e3u6ik4.jpg
series: Networking
---

## Introduction

In the ever-evolving landscape of the internet, there's a constant need for technologies that allow for more efficient use of resources. One such technology is Server Name Indication (SNI), which has become a critical component in the world of web hosting and network management. In this blog post, we'll delve deep into the concept of SNI, exploring its definition and how it works, why we need it, how to implement it with nginx and on Kubernetes, its advantages and disadvantages, and some alternatives. 

## How does SNI work?

**SNI** is an extension to the TLS (Transport Layer Security) protocol that allows a client device to specify the hostname it is trying to reach in the first step of the TLS handshake process. This specification enables the server to present multiple certificates on the same IP address and port number and hence allows multiple secure (HTTPS) websites to be served off the same IP address without requiring all those sites to use the same certificate.

Here's a step-by-step example of how a TLS handshake works with SNI:

- The client sends a `ClientHello` message to start the TLS handshake process. This message includes the hostname of the website the client is trying to reach.
- The server receives the `ClientHello` message, extracts the hostname from the SNI field, and selects the appropriate SSL certificate.
- The server responds with a `ServerHello` message, which includes the selected certificate.
- The client verifies the server's certificate and sends a `Finished` message to the server.
- The server sends a `Finished` message back to the client to complete the handshake, and the secure connection is established.

## Why do we need SNI?

**HTTP (Hypertext Transfer Protocol)** has been the foundation of data communication on the World Wide Web since its inception. However, HTTP was not originally designed with security in mind, leading to the development of **HTTPS (HTTP Secure)**. HTTPS is essentially HTTP over TLS, providing secure communication over a network by encrypting the data being transmitted, thus protecting against eavesdropping and tampering.

With the explosion of the internet, the concept of **Virtual Hosting** was introduced. Virtual hosting allows one server to host multiple domain names or websites. This is done by the web server software (like Apache or nginx) using the 'Host' header field of the HTTP request to discern which website to show, depending on the domain name requested by the client.

However, before SNI, each secure website (HTTPS) needed its own dedicated IP address, even if it was hosted on the same server. This was because the server didn't know which certificate to present during the TLS handshake process, and the 'Host' header field was only sent after this process. This presented a significant challenge due to the shortage of IPv4 addresses.

That's where SNI came in. SNI was introduced as an extension to the TLS protocol to indicate which hostname the client is attempting to connect to during the handshake process. This allows a server to present multiple certificates on the same IP address and TCP port number and negotiate the correct certificate for the site the client wants to connect to.

In today's cloud environments, SNI is used extensively. For example, in Kubernetes, you can use SNI to securely expose multiple services using an Ingress resource and an Ingress controller like nginx.

## How to Implement SNI

### SNI in a self-hosted nginx server

Nginx is a popular open-source web server and reverse proxy server. It's known for its high performance, stability, feature set, and simple configuration. In this section, we'll discuss how to configure nginx to use SNI.

Before you start, ensure you have:

1. Installed nginx on your server
2. Own domain names (e.g. `domain1.com` and `domain2.com`) pointing to your server's IP address
3. Generated certificates for each domain name

Once you have all the prerequisites, you can use the following nginx configuration to enable SNI in nginx:

```nginx
server {
    listen 443 ssl;
    server_name domain1.com;
    ssl_certificate /etc/nginx/ssl/domain1.com.crt;
    ssl_certificate_key /etc/nginx/ssl/domain1.com.key;
}

server {
    listen 443 ssl;
    server_name domain2.com;
    ssl_certificate /etc/nginx/ssl/domain2.com.crt;
    ssl_certificate_key /etc/nginx/ssl/domain2.com.key;
}
```

With this configuration, nginx will use the correct certificate based on the domain name that the client is trying to reach, as specified in the TLS handshake via SNI.

### SNI in Kubernetes

To use SNI in Kubernetes, you will typically use an [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) resource along with an Ingress controller. The Ingress resource defines how to route external HTTP/HTTPS traffic to services within the cluster, and the Ingress controller fulfills the rules defined by the Ingress resource.

Firstly, let's assume you have two services, `service1` and `service2`, running in your Kubernetes cluster. You want to expose these services via HTTPS using the hostnames `service1.example.com` and `service2.example.com`.

You would first need to ensure you have an Ingress controller running. There are several available, such as nginx, Traefik, or the one provided by a cloud provider like GKE's [Ingress-GCE](https://github.com/kubernetes/ingress-gce) or AWS's [ALB Ingress Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v1.1/).

Next, you'll need certificates for `service1.example.com` and `service2.example.com`. You can create these manually, or use [cert-manager](https://cert-manager.io/docs/usage/certificate/) to automatically provision and manage TLS certificates in Kubernetes.

Once you have your certificates, you can create a Kubernetes secret for each certificate in the same namespace as your services:

```bash
kubectl create secret tls service1-tls --key service1.key --cert service1.crt
kubectl create secret tls service2-tls --key service2.key --cert service2.crt
```

Finally, you can create an Ingress resource that uses these secrets and routes traffic based on the hostname:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example-ingress
spec:
  rules:
  - host: service1.example.com
    http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: service1
            port:
              number: 80
  - host: service2.example.com
    http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: service2
            port:
              number: 80
  tls:
  - hosts:
    - service1.example.com
    secretName: service1-tls
  - hosts:
    - service2.example.com
    secretName: service2-tls
```

In this Ingress resource, the `rules` field describes how to route the traffic based on the hostname and path. The `tls` field refers to the Kubernetes secrets that contain the SSL certificates for the hostnames. When a client makes an HTTPS request, the nginx Ingress controller uses SNI to select the appropriate SSL certificate based on the hostname specified by the client.

Next, let's dive into the advantages and disadvantages of SNI.

## Advantages and Disadvantages of SNI

Just like any other technology, SNI has its advantages and disadvantages. Let's explore some of them.

### Advantages of SNI

1. **Efficiency in IP address usage**: With SNI, multiple secure websites can share the same IP address without having to share the same certificate.

2. **Flexibility and scalability**: SNI offers improved flexibility and scalability for hosting providers. It allows them to serve multiple secure websites from a single server, thereby reducing their hardware requirements and costs.

### Disadvantages of SNI

1. **Compatibility issues**: SNI is not supported by all client software. Most notably, Internet Explorer on Windows XP and some older mobile operating systems don't support SNI. However, this is becoming less of an issue as these older systems continue to decline in usage.

2. **Security concerns**: While SNI improves the efficiency of IP address usage, it does reveal the server name in plaintext during the TLS handshake. This could potentially be used by an eavesdropper to identify which site a user is visiting. To address this concern, the IETF has proposed a new standard called [Encrypted SNI (ESNI)](https://www.cloudflare.com/learning/ssl/what-is-encrypted-sni/), which encrypts the SNI extension in the TLS handshake using asymmetric cryptography.

## Alternatives to SNI

Although SNI is a powerful tool, it may not always be the best solution depending on the situation. Here are a few alternatives:

1. **Dedicated IP addresses**: Before SNI, the primary method of serving multiple secure websites from a single server was to assign each site its own dedicated IP address. While this approach solves the problem, it's not scalable when using IPv4 due to the limited number of available IP addresses.

2. **Wildcard Certificates**: Wildcard SSL certificates can secure a domain and an unlimited number of its subdomains. For example, a single wildcard certificate for `*.example.com` can secure `www.example.com`, `blog.example.com`, `shop.example.com`, etc. However, they can't secure multiple different domain names, and if the wildcard certificate is compromised, an attacker can impersonate any of the subdomains. 

3. **Multi-domain SSL certificates**: Multi-domain SSL certificates (also known as SAN or Subject Alternative Name certificates) allow multiple domain names to be secured with a single certificate. They're more flexible than wildcard certificates, but they're also generally more expensive and still have a limit on the number of domain names that can be included.

## Conclusion

Throughout this post, we've explored the concept of SNI, a technology that allows a server to present multiple certificates on the same IP address and port number, enabling multiple secure websites to be served off the same IP address. We delved into its history and the challenges it addresses, particularly the shortage of IPv4 addresses, and we also looked at how to implement SNI in a self-hosted environment as well as on Kubernetes.

Although SNI has its advantages, such as improving the efficiency of IP address usage and offering better flexibility and scalability, its also has its downsides, including compatibility issues with some older client software and the fact that the hostname is transmitted unencrypted. We also examined some alternatives to SNI, including dedicated IP addresses, wildcard certificates, and multi-domain SSL certificates.

Have you used SNI before? Have you been confronted with clients that don't support SNI? Let me know in the comments!

---

Cover image by <a href="https://unsplash.com/@jordanharrison?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Jordan Harrison</a> on <a href="https://unsplash.com/photos/40XgDxBfYXM?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
  