---
title: Border Gateway Protocol (BGP) 
published: true
description: Border Gateway Protocol (BGP) is one of the key elements that keep the internet operational. As an essential internet protocol, BGP manages how packets are routed across the internet through the exchange of routing and reachability information among edge routers.
tags: networking, security, protocols, internet
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/qgmr0zzgfvekiln5msx9.jpg
series: Networking
---

## Introduction to BGP

**Border Gateway Protocol (BGP)** is one of the key elements that keep the internet operational. As an essential internet protocol, BGP manages how packets are routed across the internet through the exchange of routing and reachability information among edge routers. It makes routing decisions based on paths, network policies, and rule-sets. BGP has proven to be scalable and powerful, capable of handling the complex and vast network of the internet.

BGP's primary purpose is to facilitate communication between different networks on the internet. It achieves this by enabling data routing from one Internet Service Provider (ISP) to another. This aspect of BGP makes it an Exterior Gateway Protocol (EGP), as opposed to Interior Gateway Protocols (IGPs), that handle data routing within a single network.

BGP makes the internet a collection of independently managed networks rather than a single, large entity. Each ISP manages its network and communicates with other networks using BGP, which forms the basis of interconnectivity that we often take for granted. Without BGP, the current scale and functionality of the internet would not be possible.

## Understanding Basic Network Concepts

Before diving deep into BGP, it's important to grasp some fundamental network concepts that play a crucial role in how BGP operates. These concepts include the Internet Protocol (IP), the Transmission Control Protocol (TCP), and the basics of routing protocols.

### IP Fundamentals

IP is a network layer protocol, primarily responsible for addressing and routing of packets between devices. It uses unique numerical IP addresses to identify source and destination devices for data packets.

There are two standard versions of IP in use today: IPv4 and IPv6. IPv4 uses 32-bit addresses, while IPv6 uses 128-bit addresses, offering an almost infinite number of unique addresses.

IP operates in a connectionless mode, meaning that it doesn't establish a connection before sending data. It sends packets individually, and these packets may take different paths to reach the destination, where they are reassembled.

IP itself doesn't guarantee reliable delivery of packets or prevent packets from being duplicated or delivered out of order. These functions are handled by the transport layer protocols like TCP that work in conjunction with IP.

### TCP Fundamentals

TCP is a transport layer protocol, typically used with IP. It provides reliable, ordered, and error-checked delivery of a stream of data between applications running on hosts communicating over a network.

TCP is connection-oriented, meaning a connection is established between the two communicating endpoints before the data transfer can begin. This connection is maintained until all the data has been successfully delivered or until the connection is manually terminated.

Additionally, it has some useful features such as flow control (adjusting the transmission rate to network conditions), acknowledgements and retransmissions (to avoid data loss), as well as congestion control (to prevent overloading).

### Routing Protocols

Routing protocols dictate how routers communicate with each other to forward packets between networks. Based on routing protocols, routers can dynamically learn network destinations, select the best path to reach a network, and also recover from a failure in the network path.

Routing protocols can be divided into two primary types: Interior Gateway Protocols (IGPs) and Exterior Gateway Protocols (EGPs). IGPs are used for routing within a network. Examples of IGPs include the Routing Information Protocol (RIP), Open Shortest Path First (OSPF), and Interior Gateway Routing Protocol (IGRP).

On the other hand, EGPs are used for routing between different networks. BGP is the only EGP in widespread use today. BGP's primary role is to connect separate networks – also known as autonomous systems (AS) – on the internet.

An AS is a collection of IP networks and routers under the control of one entity that presents a common routing policy to the Internet. Each AS is assigned a unique number, the Autonomous System Number (ASN), used in BGP routing.

## BGP Messages, Attributes, and Decision-Making

In this section, we'll dissect BGP to understand how it works, what types of messages it uses, its various attributes, and how it makes routing decisions.

BGP is a policy-based, path-vector routing protocol. It uses TCP as its transport protocol (port 179), ensuring reliable delivery of messages. Each BGP router forms a connection (session) with its peer and exchanges messages to share and update routing information.

BGP has four [types of messages](https://datatracker.ietf.org/doc/html/rfc4271#section-4):

1. `OPEN`: This message initiates a BGP communication session. When a BGP connection is established, the first message sent is an `OPEN` message.
2. `UPDATE`: This message provides routing updates. It advertises a new path to a network, or withdraws a previously advertised path.
3. `KEEPALIVE`: This message helps maintain the connection and verifies that the link to the BGP peer is alive.
4. `NOTIFICATION`: If there are any issues, a `NOTIFICATION` message is sent, and the BGP session that encountered the issue is closed.

BGP uses various attributes for decision-making and best path selection. The [mandatory attributes](https://techhub.hpe.com/eginfolib/networking/docs/switches/K-KA-KB/15-18/5998-8164_mrg/content/ch15s07.html) are:

1. `ORIGIN`: It shows the origin of the path information.
2. `AS_PATH`: It lists the ASs that the routing update has passed through.
3. `NEXT_HOP`: It specifies the next hop IP address to reach the destination.

BGP makes routing decisions using a [best path algorithm](https://www.cisco.com/c/en/us/support/docs/ip/border-gateway-protocol-bgp/13753-25.html#anc2). The algorithm starts off with the first valid path as the best path, and then iterates through all remaining paths, comparing against the current best path. Comparing two paths, it decides based on the most important attribute, tie-breaking by looking at lower-priority attributes as necessary.

## BGP in Cloud Computing and Kubernetes

BGP plays a crucial role in cloud computing, especially for routing between the cloud service provider and the customer networks. It enables the cloud providers to advertise the customer's IP prefixes to the internet, and vice versa. This is particularly important in Infrastructure as a Service (IaaS) cloud models, where customers might host parts of their network in the cloud.

In Microsoft Azure, for instance, BGP is used in conjunction with ExpressRoute for private network connections from on-premises networks to the Azure cloud. Amazon Web Services (AWS) also uses BGP for routing with its Direct Connect service.

In container orchestration systems like Kubernetes, networking solutions are required to facilitate communication between containers across different hosts. [Project Calico](https://github.com/projectcalico/calico) is one such solution that leverages BGP for this purpose.

Calico uses BGP to distribute routes for each pod's IP address. By default, it sets up a full-mesh network where each node peers with every other node, and BGP is used to propagate these routes across the network.

Calico can also be configured to use BGP peering with a network infrastructure, making it an excellent fit for hybrid cloud scenarios where a Kubernetes cluster spans across a private data center and a public cloud. Additionally, Calico can provide network policy enforcement, which allows for fine-grained control over inter-pod communication.

## Security Concerns

BGP plays a critical role in the security of network infrastructures. From BGP hijacking to DDoS attacks, this section will discuss the security concerns related to BGP and some techniques used to secure BGP.

BGP hijacking is a malicious practice where the attacker misleads routers into sending data along incorrect paths. The attacker announces a prefix that it doesn't actually own, causing other networks to route traffic meant for that prefix to the attacker instead of the legitimate owner. BGP hijacking can be used for various purposes, such as stealing sensitive information, causing service disruptions, or conducting surveillance.

BGP can also be exploited to amplify Distributed Denial of Service (DDoS) attacks. In a typical DDoS attack, the attacker floods a target with traffic, overwhelming its resources and causing a service outage. With BGP, an attacker can misdirect the traffic of multiple sources to a single target, amplifying the impact of the DDoS attack.

To secure BGP, several techniques and extensions have been developed. Some examples include:

- **Resource Public Key Infrastructure** (RPKI): A system for verifying the association between a BGP route announcement and the correct originating AS. RPKI can help prevent BGP hijacking by ensuring that only valid routes are accepted.
- **BGPsec** (BGP Security): A protocol that uses digital signatures to ensure that the received BGP routes are valid and haven't been tampered with.
- **Generalized TTL Security Mechanism** (GTSM): A technique that uses the TTL field in the IP header to protect against CPU-intensive attacks on a router.
- **Outbound Route Filtering** (ORF): Prefix-based ORF allows a router to filter the routes that it wants to receive based on a configured prefix.
- **AS Path Filtering**: Using AS path filters, routers permit or deny prefixes from certain ASs based on regular expressions, for example.

## Conclusion

BGP is a crucial component of the internet's functioning, providing the necessary mechanisms for routing data across different networks. From its fundamental operations to its role in advanced networking concepts, understanding BGP is essential for anyone working with network infrastructures.

However, BGP is not without its challenges. The protocol was designed at a time when the internet was much smaller and less hostile than it is today. Security issues like BGP hijacking and the misuse of BGP for DDoS attacks are significant concerns that network operators have to deal with.

---

Cover image by <a href="https://unsplash.com/@thomasjsn?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Thomas Jensen</a> on <a href="https://unsplash.com/photos/UrtxBX5i5SE?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
