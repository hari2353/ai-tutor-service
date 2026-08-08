# Networking: VPC, Subnets, SG vs NACL, ALB/NLB, PrivateLink, Route53

> **Track:** C-AWS AWS Atlas · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-networking` · **Tags:** networking, critical

## The 30-second version

A VPC is just a CIDR block sliced into AZ-scoped subnets, and whether a subnet is "public" or "private" is entirely a route-table fact, not a property of the subnet itself. Security groups are stateful and allow-only at the ENI level; NACLs are stateless, allow-and-deny at the subnet level, and the classic bug is a NACL that permits inbound but forgets the outbound ephemeral-port return path, which looks exactly like an application timeout. ALB does L7 (HTTP-aware, path/host routing, TLS termination, no static IP) and NLB does L4 (TCP/UDP passthrough, static IP, minimal latency, required for non-HTTP protocols or IP allowlisting) — most "which load balancer" questions resolve to "do you need to route on HTTP content or not." PrivateLink, VPC Peering, and Transit Gateway solve three different problems — unidirectional service exposure without shared CIDR, simple 2-4 VPC full-mesh, and transitive hub-and-spoke at scale, respectively — and the single most common AWS bill surprise is S3/SQS/ECR traffic from a private subnet routing through a NAT gateway at $0.045/GB when a free gateway endpoint or cheap interface endpoint would have carried it over the AWS backbone instead.

## Why this gets asked

Because everyone can draw a VPC with two subnets and an internet gateway, and almost nobody can explain why their NAT bill was $4,000 last month, why traffic silently drops in one direction after they "locked things down with a NACL," or why their p99 jumped 8ms after they put an ALB in front of a gRPC service. The interviewer has been paged for at least one of: a NAT gateway cost blowup, a security-group-vs-NACL asymmetric-drop bug, or a "why can't service A reach service B" ticket that took an hour because nobody checked route tables first. They want the debugging method, not the diagram.

---

## Lineage: past → present → future

**What came before.** EC2 launched in 2006 with a flat, shared network — every instance got a public IP in one shared address space, security was managed with permissive Amazon EC2 Security Groups that had no concept of subnetting, and there was no way to control routing or truly isolate tenants at the network layer beyond the security group's own logic. This was fine for a single account running a handful of instances and impossible for anyone who needed to reason about compliance boundaries, hybrid connectivity, or multi-tier applications. Amazon VPC shipped in 2009 specifically to give customers their own logically isolated slice of the AWS network with real subnets, route tables, and the option to bring your own IP ranges and connect back to on-prem via VPN.

**Where it stands now.** VPC-by-default is universal — every new AWS account gets a default VPC per region — and the standard production topology is public/private subnet pairs per AZ, a NAT gateway per AZ (not one shared across AZs, to avoid a cross-AZ single point of failure and cross-AZ data charges), and VPC endpoints for anything talking to AWS-native services so that traffic never has to leave the AWS backbone. The live disagreement is at the multi-VPC layer: VPC Peering is simple and free but non-transitive and doesn't scale past a handful of VPCs; Transit Gateway is the current default for anything beyond ~3-4 VPCs needing hub-and-spoke connectivity, at the cost of a per-attachment and per-GB charge and a genuinely more complex routing model; PrivateLink is the right answer when you're exposing one service to many consumers without ever sharing a route table, CIDR, or security group with them. Interface VPC endpoints (PrivateLink under the hood) have become the default fix for "why is my NAT gateway bill so high" once teams realize S3/DynamoDB traffic and control-plane calls to SQS/SNS/CloudWatch/ECR were routing through NAT at $0.045/GB when a free gateway endpoint or a cheap interface endpoint would do.

**Where it's heading.** IPv6-only VPC subnets are increasingly the AWS-recommended default for new builds, driven by public IPv4 address scarcity and AWS's own per-hour charge on public IPv4 addresses (introduced 2024) that made "just allocate more Elastic IPs" no longer free; expect more shops to route dual-stack or IPv6-only rather than fight for IPv4 space, though most production fleets today are still IPv4-primary — treat IPv6-only as the direction of travel, not yet the median deployment. Multi-Region and multi-account network topologies are consolidating around Transit Gateway + AWS Network Manager for centralized visibility, and zero-trust patterns (PrivateLink-first, no NACLs as the primary control, identity-aware proxies in front of internal tools) are gaining ground over "big flat VPC with a perimeter firewall," though the flat-VPC-plus-perimeter model remains extremely common in practice and is not going away soon.

---

## Mental model

```
                              INTERNET
                                 │
                          ┌──────┴──────┐
                          │     IGW      │  (Internet Gateway — stateless NAT
                          └──────┬──────┘   for public subnets, no cost itself)
                                 │
     ┌───────────────────────────┴───────────────────────────┐
     │                         VPC (10.0.0.0/16)              │
     │  ┌─────────────────────┐        ┌─────────────────────┐│
     │  │  AZ-a                │        │  AZ-b               ││
     │  │  ┌────────────────┐  │        │  ┌────────────────┐ ││
     │  │  │ Public subnet  │  │        │  │ Public subnet  │ ││
     │  │  │ 10.0.0.0/24    │  │        │  │ 10.0.1.0/24    │ ││
     │  │  │  [NAT GW-a]────┼──┼────────┼──┤                │ ││
     │  │  │  [ALB node]    │  │        │  │  [ALB node]    │ ││
     │  │  └───────┬────────┘  │        │  └───────┬────────┘ ││
     │  │          │ route: 0.0.0.0/0 → NAT GW-a (own AZ)     ││
     │  │  ┌───────▼────────┐  │        │  ┌───────▼────────┐ ││
     │  │  │ Private subnet │  │        │  │ Private subnet │ ││
     │  │  │ 10.0.10.0/24   │  │        │  │ 10.0.11.0/24   │ ││
     │  │  │  [app / EMR /  │  │        │  │  [app / EMR /  │ ││
     │  │  │   SageMaker    │  │        │  │   SageMaker    │ ││
     │  │  │   endpoint]    │  │        │  │   endpoint]    │ ││
     │  │  └────────────────┘  │        │  └────────────────┘ ││
     │  └─────────────────────┘        └─────────────────────┘│
     │           SG: stateful, instance/ENI-level               │
     │           NACL: stateless, subnet-level, evaluated first │
     └───────────────────────────────────────────────────────┘
```

Route tables decide *where* a packet can go; security groups and NACLs decide *whether* it's allowed. A packet that's misrouted never reaches the SG check at all — that's why routing is step one in any "traffic is being dropped" investigation, not step three.

---

## How it actually works

### VPC, subnets, route tables — the structure and its cost

A VPC is a CIDR block (e.g. `/16`) scoped to a region; subnets carve it into AZ-scoped pieces (e.g. `/24`). A subnet is "public" only by convention: its route table has a `0.0.0.0/0 → igw-xxxx` route. A "private" subnet's default route points at a NAT gateway instead, so outbound-only internet access is possible but nothing can initiate inbound from the internet. Nothing about a subnet is inherently public or private — it's entirely the route table.

**The NAT gateway bill surprise.** A NAT gateway costs an hourly charge (roughly $0.045/hr, ~$32-33/month) *plus* $0.045 per GB processed, in both directions, in us-east-1 as of mid-2026 [AWS NAT Gateway Pricing — CostGoat](https://costgoat.com/pricing/aws-nat-gateway) — accessed 2026-08-01. If your NAT gateway sits in a different AZ than the instance sending traffic through it, you pay an *additional* ~$0.01/GB each way for the cross-AZ hop on top of that [AWS NAT Gateway Pricing — The True Cost](https://spendark.com/blog/aws-nat-gateway-pricing/) — accessed 2026-08-01. Stack that on top of standard internet egress ($0.09/GB) for internet-bound traffic and the effective cost of shipping a gigabyte of training data or S3 reads through a misconfigured NAT path can reach ~$0.135/GB. The fix in the overwhelming majority of cases is a **gateway VPC endpoint** for S3 and DynamoDB (no hourly charge, no per-GB charge at all) and **interface VPC endpoints** for everything else you talk to a lot (SQS, SNS, CloudWatch Logs, ECR, Bedrock, SageMaker runtime) — interface endpoints run about $0.01/hour per AZ plus roughly $0.01/GB, which is a ~75-80% reduction versus routing the same traffic through NAT [VPC Endpoints vs NAT Gateways — SoftwareCrafting](https://softwarecrafting.in/blog/slashing-aws-networking-costs-replacing-expensive-nat-gateways) — accessed 2026-08-01. One NAT gateway **per AZ**, not one shared across AZs — sharing saves the per-gateway hourly charge but creates both a cross-AZ data charge on every packet from the other AZs and a single point of failure for all outbound traffic.

### Security Group vs NACL — the bug that actually bites people

| | Security Group | NACL |
|---|---|---|
| Scope | ENI / instance | subnet |
| State | **Stateful** — return traffic auto-allowed | **Stateless** — must allow both directions explicitly |
| Rule type | Allow only | Allow **and** explicit Deny |
| Evaluation | All rules evaluated, most permissive wins | Rules evaluated in numeric order, first match wins |
| Default | Deny all inbound, allow all outbound | Allow all in/out (default NACL); custom NACLs deny all by default |

Security groups being stateful means: allow inbound TCP/443, and the response on the ephemeral port range is automatically permitted — you never write an outbound rule for it. NACLs are stateless: allowing inbound 443 does *nothing* for the response unless you also have an outbound rule permitting traffic to the client's ephemeral port range (1024-65535, though the exact range depends on the client OS — Linux commonly uses 32768-60999, Windows historically 49152-65535) [How to handle ephemeral ports in SGs and NACLs](https://ethannguyen2k.github.io/blog/aws-sec.html) — accessed 2026-08-01.

**The bug, concretely.** A team locks down a NACL to "only allow inbound 443 from the ALB subnet" for a compliance audit, forgets the matching outbound rule for the ephemeral port range, and the symptom is: connections establish (SYN/SYN-ACK complete, because the NACL evaluates the inbound SYN and permits it) but then hang or reset, because the response packets going out on the server's ephemeral source port get blocked by the stateless outbound NACL rule. This looks exactly like an application timeout in the logs and wastes hours because nobody thinks to check the NACL — SGs get checked first out of habit, and SGs are fine, because SGs are stateful and would never produce this symptom. The tell: `curl` from inside the subnet works, but through the LB doesn't, or the connection completes the handshake (visible in a packet capture / VPC Flow Logs `ACCEPT` on the SYN) but no data flows.

Rule of thumb from practice: use security groups as your primary and only control for 95% of cases; use NACLs sparingly, for subnet-wide explicit *deny* (blocking a known-bad CIDR, or enforcing "this subnet never talks directly to the internet" as a second layer) — something SGs cannot express since SGs have no deny rules at all [Security Groups vs NACLs](https://stackharbor.com/en/knowledge-base/awsvpc-security-groups-vs-nacls/) — accessed 2026-08-01.

### ALB vs NLB vs GWLB

| | ALB | NLB | GWLB |
|---|---|---|---|
| Layer | L7 (HTTP/HTTPS/gRPC/WebSocket) | L4 (TCP/UDP/TLS) | L3 (GENEVE-encapsulated) |
| Latency | Higher — parses HTTP, does TLS termination in the app layer | Lowest — passes packets through with minimal added latency (low double-digit microseconds is commonly cited) | Adds an extra hop through inspection appliances |
| Targets | Instance, IP, Lambda | Instance, IP, ALB (chaining) | Third-party virtual appliances (firewalls, IDS/IPS) |
| Static IP | No (DNS name only, IPs can change) | **Yes** — one static/Elastic IP per AZ | N/A |
| Routing | Path, host, header, query string, method | Connection/flow only | Transparent pass-through |
| Use when | Content-based routing across services on one domain | Extreme throughput, need a fixed IP, non-HTTP protocols (raw TCP, MQTT, gRPC needing pure L4), preserving client source IP without proxy protocol | Inserting a fleet of third-party network appliances transparently in front of traffic |

The "when NLB is required" list, concretely: (1) you need a **static IP** for allowlisting (a partner firewall rule that only accepts specific IPs — ALB's IP addresses are not guaranteed stable), (2) you're terminating **millions of concurrent connections** and the CPU cost of L7 parsing at that volume is real money, (3) the protocol **isn't HTTP** (raw TCP for a database proxy, MQTT for IoT, SMTP), or (4) you need to preserve the **original client IP** without depending on the `X-Forwarded-For` header or PROXY protocol, which some legacy clients don't handle. If none of those apply and you're routing HTTP traffic to multiple backend services by path, ALB is the right and cheaper-to-operate choice — it does host/path routing that NLB structurally cannot do (NLB never looks past the TCP header).

### PrivateLink vs VPC Peering vs Transit Gateway

- **VPC Peering** — point-to-point, non-transitive (A↔B and B↔C does not give you A↔C), free within a region, full network-level reachability once the routes are added. Right for a small, static number of VPCs (2-4) that all genuinely need full bidirectional network access. The regret at scale is always the non-transitivity: N VPCs needing full mesh connectivity requires N(N-1)/2 peering connections, each with its own route table entries [VPC Peering vs Transit Gateway — jayendrapatil](https://jayendrapatil.com/aws-vpc-peering-vs-transit-gateway-vs-privatelink-decision-guide/) — accessed 2026-08-01.
- **Transit Gateway** — a managed hub; every attached VPC gets one attachment to the hub and transitive routing to every other attached VPC through it, with centralized route table control per attachment (segment production from staging even though both attach to the same TGW). Billed per attachment-hour plus per-GB processed. Right once you're past ~4-5 VPCs or need hybrid (VPN/Direct Connect) fan-out to many VPCs from one place.
- **PrivateLink** — unidirectional: a service provider exposes an endpoint service, consumers connect to it via an interface endpoint in their own VPC. The consumer never sees the provider's CIDR, route table, or security groups, and the reverse is also true — this is the only one of the three that supports **overlapping CIDRs** between provider and consumer, because there's no real routing merge happening, just a proxy. Right for exposing one service (an internal API, a SaaS product, a shared platform team's endpoint) to many consumers with zero-trust boundaries and no shared address space assumption [AWS PrivateLink — Megaport](https://www.megaport.com/blog/aws-privatelink-explained/) — accessed 2026-08-01.

Decision in one line: 2-4 VPCs needing full mesh → Peering. Growing hub-and-spoke, especially with on-prem → Transit Gateway. Exposing a specific service without sharing network topology, especially cross-account or cross-org → PrivateLink.

### VPC endpoints — gateway vs interface

Gateway endpoints (S3, DynamoDB only) are a route-table entry, free, no ENI. Interface endpoints (everything else — SQS, SNS, CloudWatch, ECR, Bedrock runtime, SageMaker runtime, KMS, Secrets Manager, dozens more) are ENIs with private IPs in your subnets, backed by PrivateLink, costing ~$0.01/hour per AZ plus ~$0.01/GB processed. The mistake this fixes: a private-subnet workload calling S3 or reading/writing SQS messages by default routes through the NAT gateway at $0.045/GB (plus internet egress if the destination isn't actually on the AWS backbone path your route table thinks it is) — adding the matching endpoint and updating DNS resolution (interface endpoints get a private DNS name that overrides the public one by default) redirects that traffic onto the AWS backbone for a fraction of the cost, and for gateway endpoints, for free.

### Route53 routing policies and health checks

| Policy | What it does | Use when |
|---|---|---|
| Simple | One record, no health check | Single endpoint, no failover needed |
| Weighted | Split traffic by percentage across records | Canary releases, gradual migration |
| Latency-based | Route to the region with lowest measured latency for that user | Multi-region active-active, minimize RTT |
| Geolocation | Route by the query's geographic origin (country/continent) | Compliance/data-residency, localized content |
| Geoproximity | Like geolocation but with a "bias" you can tune, via Traffic Flow | Shifting traffic gradually toward/away from a region |
| Failover | Primary/secondary; only the primary answers while healthy | Active-passive DR |
| Multivalue answer | Up to 8 healthy records returned, client picks | Cheap client-side load spreading with health awareness |

Route53 health checks poll an endpoint (HTTP/HTTPS/TCP) or another CloudWatch alarm and mark records healthy/unhealthy; failover and multivalue-answer routing exclude unhealthy records from the answer set automatically [Route 53 routing policies — TechTarget/AWS docs](https://disaster-recovery.workshop.aws/en/services/networking/route53/routing-policies.html) — accessed 2026-08-01. The critical caveat, covered in depth in `T29-dns-lb`: **DNS-based failover is bounded by client and resolver cache behavior, not by your TTL.** A 60-second TTL is what you *ask for*; real-world propagation to 100% of clients routinely takes far longer because OS resolvers, corporate proxies, and old JVMs cache more aggressively than instructed. For sub-10-second failover requirements, anycast/BGP-level failover beats DNS; Route53 failover is the right tool for "few minutes is acceptable," not "seconds."

### DNS resolution inside a VPC

Every VPC gets a resolver at the base of its CIDR range plus two (`10.0.0.2` for a `10.0.0.0/16` VPC) that forwards to Route53 Resolver, handling both public DNS and any private hosted zones associated with the VPC. Interface VPC endpoints rely on this: by default they create a private hosted zone entry that makes the *public* service DNS name (e.g. `sqs.us-east-1.amazonaws.com`) resolve to the endpoint's private IP inside the VPC — this is why enabling an interface endpoint with "private DNS enabled" silently redirects existing application traffic onto the endpoint with zero code changes, which is exactly the behavior you want but can also surprise you if you expected the public IP and firewall rules assumed it.

### Debugging method: "traffic is being dropped, where do I look"

In order, cheapest-to-check first:

1. **Route table** — does the subnet have a route to where the packet needs to go (IGW, NAT, peering connection, TGW attachment, VPC endpoint)? Misrouting never reaches the SG/NACL check.
2. **Security group** — outbound on the source, inbound on the destination. Remember it's stateful; you don't need a return-path rule.
3. **NACL** — both inbound *and* outbound, on both the source and destination subnet, including the ephemeral port range for return traffic. This is the one people forget.
4. **DNS resolution** — is the name resolving to the IP you expect (private vs public, endpoint vs internet)? `dig`/`nslookup` from inside the VPC.
5. **VPC Flow Logs** — filter for the specific 5-tuple; an `ACCEPT` on the SYN with no corresponding return traffic strongly suggests an asymmetric NACL/SG issue or an intermediate hop (NAT, firewall appliance) dropping the response.
6. **MTU / path MTU discovery** — for intermittent large-payload failures specifically, check whether ICMP "fragmentation needed" is being blocked somewhere in the path (common when a security appliance blocks ICMP entirely) [Path MTU Discovery and network ACLs — AWS docs](https://docs.aws.amazon.com/vpc/latest/userguide/path_mtu_discovery.html) — accessed 2026-08-01.

Full protocol-level debugging methodology (packet captures, tcpdump reading, `ss`/`netstat`) is in `T29-net-debugging`.

**Azure/GCP equivalent.** VPC → VNet (Azure, regional) / VPC (GCP, **global** — one VPC spans all regions with per-region subnets, which changes multi-region design entirely). Security Group + NACL → NSG (Azure, no stateless-NACL equivalent at the same layer) / Firewall rules (GCP). ALB → Application Gateway (Azure) / Cloud Load Balancing L7 (GCP, global anycast by default). NLB → Azure Load Balancer / Cloud Load Balancing L4. PrivateLink → Private Link (Azure) / Private Service Connect (GCP). Route53 → Azure DNS / Cloud DNS. See `clouds/CROSS-CLOUD-MAP.md` for the full table.

---

## Build it from scratch

Minimal CDK-equivalent thought experiment in raw AWS CLI — the multi-AZ public/private VPC with NAT and a gateway endpoint, the shape almost every "design our network" interview question wants sketched:

```bash
# untested sketch — illustrates the object graph, not a copy-paste deploy script

VPC_ID=$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 --query Vpc.VpcId --output text)

# One public + one private subnet per AZ (repeat for AZ-b)
PUB_A=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.0.0/24 \
  --availability-zone us-east-1a --query Subnet.SubnetId --output text)
PRIV_A=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.10.0/24 \
  --availability-zone us-east-1a --query Subnet.SubnetId --output text)

IGW_ID=$(aws ec2 create-internet-gateway --query InternetGateway.InternetGatewayId --output text)
aws ec2 attach-internet-gateway --vpc-id $VPC_ID --internet-gateway-id $IGW_ID

# NAT gateway lives in the PUBLIC subnet, serves the PRIVATE subnet in the same AZ
EIP_ALLOC=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
NAT_ID=$(aws ec2 create-nat-gateway --subnet-id $PUB_A --allocation-id $EIP_ALLOC \
  --query NatGateway.NatGatewayId --output text)

# Public route table: 0.0.0.0/0 -> IGW
RT_PUB=$(aws ec2 create-route-table --vpc-id $VPC_ID --query RouteTable.RouteTableId --output text)
aws ec2 create-route --route-table-id $RT_PUB --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --route-table-id $RT_PUB --subnet-id $PUB_A

# Private route table: 0.0.0.0/0 -> NAT (same-AZ NAT only, avoid cross-AZ charges)
RT_PRIV_A=$(aws ec2 create-route-table --vpc-id $VPC_ID --query RouteTable.RouteTableId --output text)
aws ec2 create-route --route-table-id $RT_PRIV_A --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT_ID
aws ec2 associate-route-table --route-table-id $RT_PRIV_A --subnet-id $PRIV_A

# S3 gateway endpoint - free, kills NAT egress cost for S3 traffic from the private subnet
aws ec2 create-vpc-endpoint --vpc-id $VPC_ID --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids $RT_PRIV_A --vpc-endpoint-type Gateway
```

The line that actually matters for the cost conversation: the gateway endpoint at the end. Everything above it is standard topology; that one line is the difference between an S3-heavy workload paying $0.045/GB through NAT and paying nothing.

---

## How it's done in production

| Concern | Tool | What it adds |
|---|---|---|
| Multi-account network hub | Transit Gateway + AWS Network Manager | Centralized route control, per-attachment route tables (segment prod/staging), topology visibility across accounts |
| IaC | CDK / Terraform `aws_vpc` modules | Reproducible topology, avoids the classic "someone clicked a route table change in the console and nobody knows why" |
| Service exposure without shared CIDR | PrivateLink endpoint services | Zero-trust boundary, works across overlapping CIDRs and across accounts/orgs |
| Traffic inspection | Gateway Load Balancer + third-party appliance | Transparent insertion of a firewall/IDS fleet without changing app-level routing |
| DNS + failover | Route53 + health checks | Managed weighted/latency/geo routing, doesn't require you to run your own DNS infra |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Connection handshake completes, then hangs or resets | NACL missing an outbound rule for the ephemeral port range (stateless) | Add outbound allow for 1024-65535 (or the specific client OS range) on the NACL |
| NAT gateway bill jumped 3-5x with no traffic growth | S3/DynamoDB/SQS/ECR traffic from a private subnet routing through NAT instead of a VPC endpoint | Add gateway endpoint for S3/DynamoDB (free) and interface endpoints for the rest |
| One AZ's NAT gateway shows abnormal cross-AZ data charges | Private subnet in AZ-b routing to a NAT gateway only deployed in AZ-a | Deploy one NAT gateway per AZ, route each private subnet to its own-AZ NAT |
| `curl` from an EC2 instance in the VPC works, but through the ALB fails | Health check path/port mismatch, or SG on targets doesn't allow inbound from the ALB's SG | Verify target group health check config; ensure target SG allows inbound from the ALB security group, not just "the VPC CIDR" |
| PrivateLink endpoint resolves but connection refused | Endpoint service's SG isn't allowing inbound from the interface endpoint's ENI, or the endpoint isn't in an AZ where the service is available | Check the endpoint's associated SG and confirm AZ coverage matches |
| Route53 failover took much longer than the configured TTL | Client/resolver caching ignoring or extending TTL (see `T29-dns-lb`) | For sub-10s requirements use anycast, not DNS failover |
| Large payload transfers intermittently fail or truncate, but small ones work | Path MTU Discovery blocked because ICMP "fragmentation needed" is filtered somewhere in the path | Confirm ICMP type 3 code 4 isn't blocked; check jumbo frame / MTU settings across the hop |

---

## Tradeoffs & when NOT to use it

- **Don't use a NAT gateway for AWS-native traffic.** If the destination is S3, DynamoDB, or any service with an interface endpoint, routing it through NAT is pure waste — the cost delta is 4-5x at minimum and the endpoint traffic never leaves the AWS backbone.
- **Don't reach for Transit Gateway for 2-3 VPCs.** It's a real per-attachment, per-GB cost and operational surface for a topology VPC Peering solves for free. Reach for it when the *transitivity* or the *hybrid fan-out* actually matters.
- **Don't use NLB by default "for performance."** If you need path/host routing and aren't at the connection volume where L7 CPU cost is the bottleneck, ALB is simpler to operate (native WAF integration, native TLS cert management via ACM at the LB) and the latency difference is single-digit milliseconds, rarely the actual bottleneck in an AI-serving stack where model inference dominates.
- **Don't rely on NACLs as your primary security control.** They're stateless, easy to misconfigure into the asymmetric-drop bug, and provide no meaningful advantage over security groups for allow-only rules. Use them narrowly for explicit subnet-wide deny.
- **Don't treat anycast/geolocation/latency-based DNS as a substitute for actual regional data residency controls.** DNS routing is advisory and client-cache-dependent; compliance boundaries need to be enforced at the application/data layer, not assumed from a Route53 policy.
- **Don't put a service behind PrivateLink if it only ever has one consumer in the same VPC.** That's just a security group; PrivateLink earns its complexity when you're exposing to genuinely separate network boundaries (cross-account, cross-org, overlapping CIDR).

---

## Interview questions

### Q1 — Your NAT gateway bill tripled overnight with no traffic increase in your app logs. Walk through the diagnosis.
**Testing:** whether cost intuition is backed by mechanism, not vibes.
**Answer:** Check Cost Explorer filtered to NAT Gateway data-processing charges by hour to correlate with the spike, then check VPC Flow Logs for the NAT gateway's ENI to see which destination IPs/ports dominate. The common cause is a change that pushed AWS-native traffic (S3 reads for a new dataset, a new SQS-heavy service, ECR image pulls for a new deploy pipeline) through the NAT path instead of a VPC endpoint — often because someone added a new private subnet and forgot to associate it with the existing gateway endpoint's route table, or the new service talks to a region/service that doesn't have an endpoint yet.
**Follow-up trap:** *"The traffic is going to S3 in a different region than the VPC. Does a gateway endpoint fix it?"* — no, gateway/interface endpoints are regional; cross-region S3 access still needs an internet path (through NAT or an IGW with a public IP) unless you use S3 Multi-Region Access Points or replicate the bucket to the VPC's region.

### Q2 — Explain stateful vs stateless in the context of SG vs NACL, and describe a bug this distinction causes in production.
**Testing:** baseline, but the bug story is where the signal is.
**Answer:** SGs are stateful — an allowed inbound connection's response traffic is automatically permitted outbound, no matching rule needed. NACLs are stateless — inbound and outbound are two independent rule sets, so an allowed inbound request needs an explicit outbound rule permitting the response, typically to the client's ephemeral port range. The bug: a NACL locked down to allow only inbound 443 with no matching outbound ephemeral-range rule lets the SYN/SYN-ACK complete but silently drops every response packet, which looks identical to an application-level timeout.
**Follow-up trap:** *"Would VPC Flow Logs show you this?"* — yes, but only if you know to look for it: you'd see `ACCEPT` on the inbound SYN and either no logged outbound record at all for the response, or a `REJECT` on the outbound leg at the NACL — the giveaway is asymmetry between inbound accepts and outbound rejects for the same flow.

### Q3 — When is NLB required instead of ALB?
**Answer:** Static IP requirements (partner IP allowlisting), extreme connection volume where L7 CPU cost matters, non-HTTP protocols (raw TCP, MQTT, database proxies), or needing the original client source IP without depending on `X-Forwarded-For`/PROXY protocol support in the client.
**Follow-up trap:** *"Can you get path-based routing on an NLB?"* — no, NLB never parses past the TCP header; if you need both a static IP and path routing, the pattern is NLB in front of a fleet of ALBs (NLB target type "ALB"), not choosing one or the other.

### Q4 — Design connectivity for 15 VPCs across 3 teams that all need to reach a shared internal API, but not each other.
**Testing:** whether PrivateLink vs Transit Gateway is understood as "different problems," not interchangeable options.
**Answer:** PrivateLink. Put the shared API behind an NLB, create a VPC endpoint service, and let each of the 15 consumer VPCs create an interface endpoint into it — no shared route table, no CIDR overlap concerns, no accidental lateral connectivity between the 15 VPCs. Transit Gateway would connect all 15 VPCs together, which grants far more reachability than "everyone needs to reach one API" requires and needs additional route-table segmentation to claw back the isolation PrivateLink gives by default.
**Follow-up trap:** *"What if those 15 VPCs also need general connectivity to each other for unrelated reasons?"* — then you need both: Transit Gateway for the general mesh, PrivateLink for the specific service exposure, because Transit Gateway wouldn't stop you from also wanting the tighter exposure boundary for the one shared API.

### Q5 — What's non-transitive about VPC Peering and why does it bite teams at scale?
**Answer:** If VPC A peers with B, and B peers with C, A cannot reach C through B — each peering connection is a separate, isolated relationship with its own route table entries. Teams hit this when they've peered a handful of VPCs pairwise and then need a new VPC to reach all of them, discovering they need N-1 new peering connections instead of one new attachment.
**Follow-up trap:** *"At what VPC count would you switch to Transit Gateway?"* — there's no hard number, but once you're maintaining more than a handful of peering connections and manually reconciling route tables across all of them, or you need centralized route control per environment (segmenting prod/staging traffic even though they attach to the same hub), the operational cost of Peering's O(n²) growth exceeds Transit Gateway's per-attachment cost.

### Q6 — A gRPC service behind an ALB has higher p99 latency than the same service behind an NLB. Why, and is it worth switching?
**Answer:** ALB terminates TLS and does HTTP/2 framing/parsing before forwarding, adding measurable per-request overhead (typically single-digit milliseconds); NLB passes TCP/TLS through with near-zero added latency because it never inspects the payload. Whether it's worth switching depends on what the ALB is *for* — if you need host/path routing across multiple gRPC services on one endpoint, or ACM-managed TLS termination, or WAF, that's real value the NLB can't provide, and a few milliseconds against an inference call that itself takes 200ms+ is very unlikely to matter.
**Follow-up trap:** *"What if the workload is a synchronous low-latency trading or bidding system where every millisecond counts?"* — then the tradeoff flips: NLB's lower overhead becomes the deciding factor and you either terminate TLS at the target directly or use mTLS between NLB and targets, since NLB itself doesn't do L7 termination.

### Q7 — Explain why S3 read-heavy training data pipelines from SageMaker/EMR in a private subnet can get expensive, and how you'd fix it.
**Testing:** direct application to the student's own SageMaker/EMR background.
**Answer:** Without a gateway VPC endpoint, S3 traffic from a private subnet defaults to routing through the NAT gateway, at $0.045/GB processed on top of the NAT's hourly charge — for a training job pulling terabytes of data, that's a meaningful and entirely avoidable line item. A gateway endpoint for S3 is free and routes the traffic over the AWS backbone directly, no NAT involvement at all.
**Follow-up trap:** *"Does this affect SageMaker Training job throughput, not just cost?"* — potentially yes: NAT gateways have their own bandwidth scaling behavior (they scale automatically but there's a per-gateway limit, historically cited around 45 Gbps, that a training job saturating S3 reads across many workers can approach), whereas the endpoint traffic isn't funneled through that single chokepoint.

### Q8 — Walk through your debugging method when "service A can't reach service B" inside a VPC, in order.
**Answer:** Route table first (is there a path at all), then security groups (both source outbound and destination inbound, remembering SGs are stateful so no return rule is needed), then NACLs (both directions, on both subnets, including ephemeral ports), then DNS resolution (is the name resolving where you expect), then VPC Flow Logs to confirm empirically where the drop happens, then MTU/path issues for large-payload-specific failures.
**Follow-up trap:** *"Why route tables before security groups?"* — because a misrouted packet never reaches the SG/NACL evaluation for the intended path at all; checking SG rules on a security group that's never actually being evaluated wastes time. Cheapest, most structural checks first.

### Q9 — Why can gateway VPC endpoints only serve S3 and DynamoDB, and what's the practical consequence?
**Answer:** Gateway endpoints work by adding a route-table entry — they're not a network interface, so they only work for services AWS implemented this way historically (S3 and DynamoDB). Every other AWS service that supports VPC endpoints does so via interface endpoints (ENIs, PrivateLink-backed), which cost per-hour and per-GB, unlike the free gateway endpoints. The practical consequence: S3/DynamoDB traffic optimization is free and should always be done; optimizing NAT costs for everything else (SQS, ECR, CloudWatch) has a real cost tradeoff to evaluate against the NAT cost it replaces.
**Follow-up trap:** *"Is it ever cheaper to leave traffic on NAT instead of adding an interface endpoint?"* — yes, at low volume: an interface endpoint costs a flat ~$0.01/hour per AZ (~$7-8/month) regardless of traffic, so for a service that moves a trivial amount of data through NAT, the endpoint's fixed cost can exceed what you're currently paying in NAT data-processing charges. Do the arithmetic, don't assume endpoints are always cheaper.

### Q10 — A partner requires you to allowlist a single static IP for their firewall. Your service currently sits behind an ALB. What do you do?
**Answer:** ALB doesn't guarantee static IPs (its underlying nodes can change). Put an NLB in front of the ALB (NLB supports "ALB" as a target type) and allocate Elastic IPs to the NLB, one per AZ — that gives you the static IP the partner needs while keeping the ALB's L7 routing for everything else.
**Follow-up trap:** *"Does this add meaningful latency?"* — an extra network hop, typically low single-digit milliseconds at most; for partner-integration traffic this is very rarely the bottleneck compared to the actual request processing.

### Q11 — Explain why NACLs evaluate rules "in order" but SGs don't.
**Answer:** NACL rules have explicit numbered priorities and the first matching rule (allow or deny) wins, so rule ordering is a real design decision — a broad deny at rule 100 will shadow a more specific allow at rule 200. Security groups have no explicit ordering or deny rules at all; every rule is evaluated and the result is the union of all allows (there's nothing to shadow because there's no deny to conflict with).
**Follow-up trap:** *"What's the practical implication for rule design?"* — NACL rule numbering needs deliberate gaps (traditionally increments of 100) to allow inserting new rules between existing ones without renumbering everything; SGs need no such planning since order is irrelevant.

### Q12 — Design the network for a multi-region active-active service with sub-10-second failover.
**Testing:** whether DNS's real-world limitations are internalized, not just recited.
**Answer:** Don't rely on Route53 failover alone — DNS TTL is advisory and real propagation to all clients can take far longer than the configured TTL due to caching outside your control. Use an anycast-based approach (AWS Global Accelerator, which anycasts two static IPs across AWS edge locations and can shift traffic away from an unhealthy region within its own health-check interval, independent of DNS caching) as the primary failover mechanism, with Route53 latency-based or failover routing as a secondary/coarser layer for clients or paths that don't traverse Global Accelerator.
**Follow-up trap:** *"Why not just set the TTL to 5 seconds?"* — because plenty of resolvers and client stacks ignore or extend TTLs regardless of what you set (see `T29-dns-lb`); a low TTL reduces but doesn't guarantee fast propagation, and anycast-based failover doesn't have this dependency at all.

---

## Red flags that fail you

- Saying NACLs are "more secure" than security groups without qualifying what they're actually good for.
- Not knowing SGs are stateful and NACLs are not.
- Recommending Transit Gateway for 2-3 VPCs "because it's more scalable," with no mention of the cost/complexity tradeoff against Peering.
- Claiming ALB and NLB differ "just in speed" without explaining the L7 parsing/TLS termination reason why.
- Assuming a private subnet's S3 traffic is free or backbone-routed by default (it isn't, without a gateway endpoint).
- Treating Route53 failover as instant.
- Not mentioning route tables at all when asked to debug a connectivity issue.

---

## Cheat card

```
VPC/SUBNET   subnet is public/private only by its ROUTE TABLE (0.0.0.0/0 -> IGW or NAT)
NAT GW       ~$0.045/hr + $0.045/GB processed; +~$0.01/GB x2 if cross-AZ
             fix: gateway endpoint (S3/DynamoDB, FREE) + interface endpoints (~$0.01/hr/AZ + ~$0.01/GB)
             one NAT per AZ, not shared -- avoids cross-AZ charge + single point of failure

SG           stateful, ENI-level, ALLOW only, all rules unioned
NACL         stateless, subnet-level, ALLOW+DENY, first-match numeric order
             BUG: NACL inbound-only rule -> SYN/SYN-ACK OK, response dropped
                  (forgot outbound ephemeral port 1024-65535 rule)

ALB (L7)     HTTP/gRPC/WS, path/host/header routing, TLS term, no static IP
NLB (L4)     TCP/UDP/TLS passthrough, near-zero latency, STATIC IP, non-HTTP
GWLB (L3)    transparent insertion of 3rd-party inspection appliances
  need static IP + path routing -> NLB in front of ALB (NLB target type "ALB")

PEERING      point-to-point, NON-TRANSITIVE, free, good for 2-4 VPCs
TGW          hub-and-spoke, transitive, per-attachment+per-GB, good 5+ VPCs / hybrid
PRIVATELINK  unidirectional service exposure, works w/ OVERLAPPING CIDRs, zero-trust

ROUTE53      simple/weighted/latency/geolocation/geoproximity/failover/multivalue
             health checks gate failover + multivalue answers
             DNS failover is TTL-ADVISORY, not guaranteed -- use anycast (Global
             Accelerator) for <10s failover, not DNS alone

DEBUG ORDER  route table -> SG -> NACL (both dirs, both subnets) -> DNS ->
             VPC Flow Logs -> MTU/PMTUD
```

## Sources

- [AWS NAT Gateway Pricing Calculator & Guide](https://costgoat.com/pricing/aws-nat-gateway) — accessed 2026-08-01
- [AWS NAT Gateway Pricing — The True Cost Is $0.135/GB](https://spendark.com/blog/aws-nat-gateway-pricing/) — accessed 2026-08-01
- [Slashing AWS Networking Costs: VPC Endpoints vs NAT Gateways](https://softwarecrafting.in/blog/slashing-aws-networking-costs-replacing-expensive-nat-gateways) — accessed 2026-08-01
- [How to handle ephemeral ports in Security Groups and Network ACLs](https://ethannguyen2k.github.io/blog/aws-sec.html) — accessed 2026-08-01
- [Security groups vs NACLs — Stack Harbor](https://stackharbor.com/en/knowledge-base/awsvpc-security-groups-vs-nacls/) — accessed 2026-08-01
- [VPC Peering vs Transit Gateway vs PrivateLink — Decision Guide](https://jayendrapatil.com/aws-vpc-peering-vs-transit-gateway-vs-privatelink-decision-guide/) — accessed 2026-08-01
- [AWS PrivateLink, Explained — Megaport](https://www.megaport.com/blog/aws-privatelink-explained/) — accessed 2026-08-01
- [Amazon Route 53 — Routing Policies — AWS Disaster Recovery Workshop](https://disaster-recovery.workshop.aws/en/services/networking/route53/routing-policies.html) — accessed 2026-08-01
- [Path MTU Discovery and network ACLs — AWS VPC docs](https://docs.aws.amazon.com/vpc/latest/userguide/path_mtu_discovery.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
