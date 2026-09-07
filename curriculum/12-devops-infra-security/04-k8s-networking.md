# K8s Networking: Service Types, kube-proxy, Ingress, CNI, DNS, Network Policy

> **Track:** T12 DevOps, Infra & Security Â· **Time:** 3h Â· **Prereqs:** T12-k8s-objects, T29-tcp-deep Â· **Updated:** 2026-08-02
> **Module id:** `T12-k8s-networking` Â· **Tags:** k8s, critical
> **Lab:** `labs/misc/04-k8s-networking/`

## The 30-second version

A Service is a stable virtual IP in front of a churning set of pod IPs, tracked via EndpointSlices and translated to real pod destinations by kube-proxy â€” iptables by default (linear rule-chain evaluation, a real bottleneck past thousands of Services), IPVS as a now-deprecated (as of 1.35) hash-table-based fix for that exact bottleneck, and nftables (stable since 1.33) as the intended long-term replacement that isn't the default yet for compatibility reasons. Ingress gives basic L7 host/path routing but pushes everything else (traffic splitting, header rules) into controller-specific annotations that don't port between implementations â€” which is exactly what Gateway API's GA'd core resources (GatewayClass/Gateway/HTTPRoute) fix with a role-oriented, vendor-neutral model, and the migration has real urgency now that ingress-nginx is being retired (best-effort maintenance only through March 2026, then archived). The CNI plugin is what actually wires up pod-to-pod L3 connectivity underneath all of this, and NetworkPolicy enforcement is entirely dependent on whether the installed CNI implements it â€” a cluster on a policy-blind CNI will silently accept NetworkPolicy objects that do nothing at all. CoreDNS resolves names to those virtual IPs, and the single most common unnecessary-latency bug in Kubernetes networking is the default `ndots:5` search-list behavior causing up to five failed DNS lookups before an external domain finally resolves.

## Why this gets asked

Because "Service, Ingress, DNS" sounds like plumbing until you've watched a service work fine on `kubectl port-forward` and fail over the ClusterIP, discovered a whole namespace of NetworkPolicy objects doing nothing because nobody checked whether the CNI enforces them, or traced an intermittent slow first-request-to-a-third-party-API bug back to `ndots`. The interviewer wants to know whether you can actually debug connectivity from the packet's perspective â€” which layer owns the failure, Service, kube-proxy, CNI, DNS, or the application â€” rather than reciting the object hierarchy from the docs. This is also one of the fastest-moving parts of the Kubernetes ecosystem right now (Gateway API's rise, ingress-nginx's retirement, kube-proxy's mode transition), so it doubles as a check on whether your knowledge is current.

---

## Lineage: past â†’ present â†’ future

**What came before.** Early container networking had no standard model at all â€” Docker's own bridge networking handled single-host container-to-container communication via manual port mapping, with no answer for cross-host pod networking or a common interface multiple runtimes and network vendors could implement against. The Container Network Interface spec (CNI, originally from CoreOS, donated to CNCF in 2017) fixed this by defining a minimal exec-based plugin contract â€” `ADD`/`DEL` operations the container runtime invokes to allocate an IP and wire up networking for a pod â€” decoupling "how do pods get IPs and routes" from Kubernetes's own code entirely. kube-proxy's original and still-default mode, iptables, was designed when cluster sizes and Service counts were assumed modest; the pain that produced IPVS as an alternative mode was measured and specific â€” iptables evaluates a Service's NAT rules as a linear chain walk per packet, and a full rule sync (needed on every Service/Endpoint change) becomes a genuinely slow, non-atomic operation at high Service counts, both of which show up as real, measurable latency and control-plane churn at scale. Ingress (added early, well before workload-routing needs matured) was deliberately thin â€” host, path, backend service, TLS â€” and every capability beyond that got pushed into vendor-specific annotations, which was fine until organizations running multiple Ingress controllers or migrating between them discovered those annotations simply didn't translate.

**Where it stands now.** iptables remains kube-proxy's default mode on Linux even though it's the acknowledged performance laggard, for compatibility reasons the project has stated explicitly rather than left ambiguous. IPVS, added specifically to solve the iptables scaling problem via O(1) in-kernel hash table lookups instead of O(n) chain walks, is itself now **deprecated as of Kubernetes 1.35**, with **nftables** â€” stable since **1.33**, offering atomic rule replacement (no non-atomic multi-second reload window during high churn) and comparable-or-better performance â€” positioned as the actual long-term replacement, though the project has been explicit that nftables is **not yet the default**, with no committed timeline to make it so. Separately, and more disruptively, Cilium's eBPF-based dataplane bypasses kube-proxy's Service-proxying model entirely for clusters that adopt it, replacing iptables-based DNAT with eBPF programs attached directly in the kernel â€” per the CNCF's 2025 annual survey, Cilium overtook both Flannel and Calico to become the most-used CNI in production, with **47% year-over-year adoption growth**. At the routing-layer level, Gateway API's core resources (GatewayClass, Gateway, HTTPRoute, GRPCRoute, TLSRoute, ReferenceGrant) are GA and production-ready, explicitly designed around role separation (a platform/infra team owns the `Gateway`, application teams own their own `HTTPRoute` objects referencing it) that Ingress's flat single-object model never expressed. The concrete forcing function behind migration urgency: the most widely deployed Ingress controller, ingress-nginx, is being retired â€” best-effort maintenance only through **March 2026**, after which it moves to read-only archival with no further bug fixes or security patches â€” even though Kubernetes SIG-Network has stated the core Ingress *API* itself will continue to be maintained for the foreseeable future, which is a real, worth-stating distinction between "the API is dying" (false) and "your specific controller implementation is dying" (true, for ingress-nginx specifically).

**Where it's heading.** Expect kube-proxy-less clusters (via Cilium or similar eBPF-native CNIs) to keep growing at the high-performance end, and Gateway API to become the default recommendation for new clusters rather than Ingress over the next several years, while existing working Ingress deployments are not forced into an abrupt migration â€” SIG-Network's stated position is migrate when you hit a concrete limitation, not preemptively. TCPRoute and UDPRoute (Gateway API's non-HTTP route types) remain experimental, so full protocol parity with Ingress's simpler but broader use cases isn't there yet, which is itself a reason some teams are deliberately waiting rather than migrating immediately.

---

## Mental model

```
                 DNS query: "my-svc.my-ns.svc.cluster.local"
                              â”‚
                              â–¼
                       CoreDNS (Corefile plugin chain)
                       resolves to Service's ClusterIP
                              â”‚
                              â–¼
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚  SERVICE (stable virtual IP)                             â”‚
   â”‚  tracked by EndpointSlices (live pod IPs matching        â”‚
   â”‚  the Service's selector, sharded ~100 endpoints/slice)   â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                 kube-proxy translates virtual IP -> real pod IP
        iptables (default, O(n) chain walk)  |  IPVS (deprecated 1.35, O(1) hash)
                    |  nftables (stable 1.33, atomic, not-yet-default)
                    |  eBPF (Cilium, bypasses kube-proxy entirely)
                              â”‚
                              â–¼
                   actual pod-to-pod packet delivery
                     via the CNI plugin's routing
             (VXLAN overlay / BGP peering / eBPF datapath â€”
              NetworkPolicy enforcement ONLY exists if the
              CNI implements it; otherwise policy objects
              are silently inert)

   L7 entry point (external traffic):
   Ingress (thin: host/path/TLS, rest = vendor annotations, ingress-nginx retiring)
      -vs-
   Gateway API (GatewayClass + Gateway [infra-owned] + HTTPRoute [app-owned],
                native traffic splitting/header routing, GA, vendor-neutral)
```

The layer to isolate in any debugging session: **Service/kube-proxy** (is there a virtual IP, does it have healthy endpoints, is the proxy rule actually programmed) is a completely different failure domain from **CNI** (can packets physically move between these two pod IPs at all) which is different again from **NetworkPolicy** (is this specific traffic *allowed* even though it *can* physically flow) which is different again from **DNS** (did the client even resolve the right IP in the first place). Conflating these four is the single most common reason networking debugging goes in circles.

---

## How it actually works

### Service types, precisely

- **ClusterIP** (default): a virtual IP allocated from the cluster's service CIDR, stable for the Service's lifetime regardless of pod churn. Not routable outside the cluster.
- **NodePort**: additionally opens the **same port in the 30000-32767 range** (default range) on *every* node, whether or not a matching pod actually runs on that node â€” traffic arriving at any node's NodePort gets DNAT'd by kube-proxy to a matching pod, potentially on a completely different node, adding an extra network hop. `externalTrafficPolicy: Local` avoids that extra hop (traffic is only forwarded to pods on the *same* node it arrived at) but trades away even load balancing if pods aren't spread across every node receiving traffic â€” a node with no local pod for that Service simply drops the traffic under `Local`.
- **LoadBalancer**: builds on NodePort by additionally asking the cloud provider (via a cloud-controller-manager integration) to provision an actual external load balancer pointed at the node set. Provisioning one per Service is a real, recurring cloud cost at scale â€” a common production mistake is giving every microservice its own `LoadBalancer` Service instead of fronting many Services with a single Ingress/Gateway.
- **ExternalName**: a pure DNS CNAME to an external hostname, no proxying or virtual IP at all â€” used to give an in-cluster-style name to something outside the cluster (an external database endpoint, for instance).
- **Headless** (`clusterIP: None`): no virtual IP and no load-balancing at all; DNS queries against it return the individual pod IPs directly (or, for a StatefulSet, individually addressable per-pod DNS names), and it additionally publishes **SRV records** so clients can discover both the IP and port of each backing pod without a separate lookup â€” this is structurally different from a normal ClusterIP Service's DNS answer (one A record for the virtual IP) and is why StatefulSet requires it: normal Service DNS can't express "give me pod-0 specifically."

### kube-proxy modes, mechanically

**iptables** mode programs a chain of NAT rules per Service and per endpoint â€” a packet destined for a Service's ClusterIP is matched and DNAT'd to a chosen pod IP by walking through these chains sequentially. This is fine at modest scale, but two things degrade as Service/endpoint count grows: per-packet latency (longer chains to walk) and rule-sync time (kube-proxy regenerates large portions of the ruleset on Service/Endpoint changes, and iptables rule replacement isn't atomic at the reload granularity that matters here, meaning there's a real window of inconsistent state during high-churn updates). **IPVS** mode was added specifically to fix this: it uses an in-kernel hash table for **O(1)** Service lookup regardless of count, a direct answer to iptables's O(n) chain-walk cost â€” but IPVS itself is now **deprecated as of Kubernetes 1.35**. **nftables** mode (stable since 1.33) is the intended replacement: comparable-or-better performance to IPVS with the added benefit of atomic rule replacement (no inconsistent-state window during updates), but it is explicitly **not the default** as of this writing, purely for backward-compatibility reasons the project has stated rather than a performance argument. Cilium and similar eBPF-native CNIs sidestep the entire kube-proxy model, attaching eBPF programs directly at kernel hook points to do Service load-balancing without any iptables/IPVS/nftables layer involved at all â€” genuinely a different architecture, not just another kube-proxy mode.

### NetworkPolicy â€” additive, default-allow until touched

With **zero** NetworkPolicy objects in a namespace, the default is **allow-all**: every pod can reach every other pod, and every pod's egress is unrestricted, subject only to whatever the CNI's own default posture is. The moment **any** NetworkPolicy object selects a given pod for a given direction (ingress or egress), that direction flips to **default-deny** for that pod, with only what's explicitly allowed by matching policies permitted through. Policies are purely additive â€” multiple policies selecting the same pod are OR'd together (you can't write an explicit "deny" rule, only narrower or broader "allow" rules layered on top of the implicit deny baseline that appears once any policy touches that pod/direction). The single most common real mistake: writing an **ingress-only** NetworkPolicy for a pod and assuming egress is now restricted too â€” it isn't; egress stays fully open until a separate policy explicitly selects that pod for the egress direction, and teams that only write ingress rules are frequently surprised, during a security review, that every pod they thought was locked down can still freely reach anything outbound.

Crucially: **none of this is enforced by the API server or kube-proxy.** NetworkPolicy objects are just stored, schema-validated data unless the cluster's CNI plugin implements a policy controller that watches them and programs actual enforcement (via iptables rules, eBPF programs, or whatever mechanism that CNI uses). Flannel, in its basic form, implements **no** NetworkPolicy enforcement at all â€” a cluster running plain Flannel will accept, store, and display NetworkPolicy objects via `kubectl get networkpolicy` that have precisely zero effect on actual traffic, a genuinely dangerous gap that's easy to discover only during an incident or audit rather than up front.

### DNS â€” CoreDNS and the `ndots:5` trap

CoreDNS has been the default cluster DNS add-on since **Kubernetes 1.13** (2018), replacing kube-dns, running as a Deployment behind its own Service and configured via a `Corefile` plugin chain (the `kubernetes` plugin resolves in-cluster names against the API server's Service/Endpoint data; the `forward` plugin sends anything else upstream to the configured resolver). Every pod's default `/etc/resolv.conf` (under the default `dnsPolicy: ClusterFirst`) gets a search list â€” typically the pod's own namespace's `svc.cluster.local`, the cluster-wide `svc.cluster.local`, and `cluster.local` itself â€” plus `options ndots:5`. The `ndots` value means: any query name with **fewer than 5 dots** gets each search-suffix appended and tried, **in order**, before the resolver ever attempts the name as an absolute, fully-qualified lookup. A query for an external API like `api.stripe.com` (2 dots) is not an exception â€” it gets tried against every search suffix first (up to 4 failed internal lookup attempts, each incurring a full round trip and a negative response from CoreDNS or an upstream) before the 5th, bare, correct external lookup finally succeeds. This is the single most common source of unexplained extra latency on the *first* call to any external dependency from inside a pod, and it silently multiplies real external-API latency by up to roughly **5x** in the worst case per cold lookup. Standard fixes: appending a trailing dot to known-external hostnames in application code (`api.stripe.com.` is treated as already fully-qualified, skipping the search list entirely), tuning `ndots` down for specific latency-sensitive workloads via `pod.spec.dnsConfig`, or deploying **NodeLocal DNSCache** (a per-node caching DNS agent that absorbs repeat lookups locally, reducing both latency and load on the central CoreDNS Deployment) â€” the last of which also helps with a separate, related problem: CoreDNS itself becoming a real bottleneck or partial single point of failure under high query volume at cluster scale.

---

## Build it from scratch

The two objects worth being able to write cold, since they're both frequently gotten wrong in exactly the ways described above:

```yaml
# untested sketch â€” default-deny-all baseline, then a scoped allow, the correct
# pattern for zero-trust namespace networking
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: payments
spec:
  podSelector: {}       # empty selector = applies to EVERY pod in this namespace
  policyTypes:
  - Ingress
  - Egress             # <- both directions explicitly, the commonly-forgotten one
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-to-db
  namespace: payments
spec:
  podSelector:
    matchLabels: { app: payments-db }
  policyTypes: [Ingress]
  ingress:
  - from:
    - podSelector: { matchLabels: { app: payments-api } }
    ports:
    - protocol: TCP
      port: 5432
```

```yaml
# untested sketch â€” Gateway API HTTPRoute with native traffic splitting,
# something Ingress can only do via non-portable controller annotations
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: checkout-canary
  namespace: payments
spec:
  parentRefs:
  - name: shared-gateway      # references a Gateway object the platform team owns
  hostnames: ["checkout.example.com"]
  rules:
  - matches:
    - path: { type: PathPrefix, value: / }
    backendRefs:
    - name: checkout-v1
      port: 8080
      weight: 90
    - name: checkout-v2
      port: 8080
      weight: 10           # native 90/10 canary split, no controller-specific annotation
```

Applying the default-deny pair first proves the additive-policy model mechanically: before any second policy exists, every pod in `payments` is fully isolated (both directions), and only the second, narrower policy carves out the specific `payments-api -> payments-db:5432` path â€” exactly the deny-by-default, explicitly-allow posture a real production namespace should have, not the accidental partial version most teams end up with by only writing ingress rules.

---

## How it's done in production

Most production clusters standardize on one CNI cluster-wide (Cilium or Calico dominate for policy-enforcing, production-grade needs; Cilium specifically for teams wanting eBPF-level performance and its built-in Hubble observability layer giving per-flow network telemetry without extra tooling) rather than mixing, since NetworkPolicy semantics and performance characteristics genuinely differ between them. New clusters increasingly default to Gateway API from day one rather than starting on Ingress and migrating later, given ingress-nginx's retirement timeline and Gateway API's now-GA status removing the "not production ready yet" objection that held for years. CoreDNS is commonly deployed with a cluster-proportional-autoscaler (scaling replica count with cluster/node size rather than a fixed replica count) and paired with NodeLocal DNSCache in query-heavy clusters specifically to keep DNS off the critical path for external API latency.

| Symptom | Cause | Fix |
|---|---|---|
| Service has healthy endpoints, `kubectl port-forward` to the pod works, but ClusterIP connections time out | NetworkPolicy blocking the traffic (if the CNI enforces it), or kube-proxy rules not actually programmed for that Service | `kubectl describe networkpolicy` in the relevant namespaces for scope-matching rules; check kube-proxy mode-specific state (`iptables-save \| grep <service>`, `ipvsadm -Ln`, or the CNI's own policy-debugging tool for eBPF) |
| First request to an external API from a pod is consistently slow, subsequent ones are fast | `ndots:5` default causing up to 4 failed in-cluster DNS lookups before the correct external one succeeds | Trailing-dot the hostname in code, tune `ndots` via `pod.spec.dnsConfig` for that workload, or deploy NodeLocal DNSCache to absorb the cost cluster-wide |
| NetworkPolicy objects exist and look correct, but traffic still flows freely regardless | The installed CNI doesn't implement NetworkPolicy enforcement at all (e.g. bare Flannel) | Confirm the CNI's policy-enforcement capability explicitly before relying on NetworkPolicy for anything security-relevant; switch to a policy-enforcing CNI (Calico, Cilium) if it doesn't |
| Ingress rules that worked on one controller break silently after switching Ingress controller implementations | Behavior beyond basic host/path routing depended on vendor-specific annotations that don't exist on the new controller | Either replicate the needed annotations for the new controller, or migrate the routing logic to Gateway API's native fields (traffic splitting, header matching) so it's controller-portable going forward |
| Cluster-wide DNS timeouts/errors spike under load | CoreDNS not scaled proportionally to cluster size/query volume, or no local caching layer absorbing repeat lookups | Enable a cluster-proportional-autoscaler for CoreDNS replica count; deploy NodeLocal DNSCache to cut central CoreDNS load |
| Pods on one specific node can't reach pods on another specific node, everything else is fine | CNI overlay/routing broken between those two nodes specifically â€” a common concrete cause is an MTU mismatch, since VXLAN-style overlay encapsulation adds header overhead that an unadjusted node MTU doesn't account for, causing silent packet drops for larger payloads | Check CNI daemon logs on both nodes; verify node/interface MTU accounts for the CNI's encapsulation overhead (commonly needs to be set several dozen bytes below the physical interface's MTU for VXLAN-based overlays) |
| A `NodePort`/`LoadBalancer` Service with `externalTrafficPolicy: Local` drops all traffic hitting certain nodes | `Local` skips forwarding to pods on other nodes to avoid the extra hop, but that means a node with zero local pods for that Service simply has nothing to forward to | Ensure pods are spread across every node that could receive traffic (or accept `externalTrafficPolicy: Cluster`'s extra hop in exchange for even distribution regardless of pod placement) |

---

## Tradeoffs & when NOT to use it

- **Don't give every microservice its own `LoadBalancer` Service by default.** Each one provisions a real, billed cloud load balancer; front many Services behind a single Ingress or Gateway instead unless a specific service genuinely needs its own dedicated external entry point (a non-HTTP protocol Ingress/Gateway can't route, for instance).
- **Don't reach for a kube-proxy-less, full eBPF CNI migration (Cilium) purely chasing the performance numbers** without the operational maturity to debug it when something goes wrong â€” eBPF-based networking has a real, steeper troubleshooting learning curve than iptables's well-understood (if slower) semantics, and "we don't actually know how to read Hubble output during an incident" is a genuine cost worth weighing against the latency win.
- **Don't treat NetworkPolicy as optional "because the internal network is trusted."** In any multi-tenant or compliance-relevant cluster, default-allow inter-pod networking is the wrong baseline; assume zero-trust and write explicit default-deny-then-allow policies, and verify the CNI actually enforces them before relying on that posture at all.
- **Don't migrate a stable, working Ingress setup to Gateway API on day one just because it's the newer standard.** SIG-Network's own stated guidance is to migrate when a concrete limitation is actually hit (needing native traffic splitting, the specific controller being deprecated), not preemptively â€” migration churn has a real cost, and TCPRoute/UDPRoute are still experimental, so full non-HTTP protocol parity with Ingress isn't universally there yet.
- **Don't dismiss `ndots` tuning as premature optimization.** For any service making frequent calls to external dependencies, it's a cheap, well-understood, measurable fix â€” ignoring it because "DNS is fast enough usually" leaves real, avoidable latency on the table specifically on cold/first lookups, which matters disproportionately for tail latency and cold-start-sensitive paths.

---

## Interview questions

### Q1 â€” Explain the four core Service types and when you'd actually choose NodePort over LoadBalancer.
**Testing:** whether Service types are understood as a real decision, not memorized definitions.
**Answer:** ClusterIP (default, internal-only stable virtual IP), NodePort (opens the same port, 30000-32767 range by default, on every node, DNAT'd to a matching pod possibly on another node), LoadBalancer (NodePort plus a cloud-provisioned external LB pointed at the node set), and ExternalName (a pure CNAME, no proxying). NodePort over LoadBalancer is chosen when you already have your own external load balancer or ingress layer routing to the cluster and just need a stable node-level port to target, avoiding provisioning a redundant cloud LB per Service, or in bare-metal/on-prem clusters where no cloud LB integration exists at all.
**Follow-up trap:** *"What's the actual downside of NodePort's default behavior that `externalTrafficPolicy: Local` fixes, and what does Local cost you in return?"* â€” default (`Cluster`) traffic policy can forward a request to a pod on a *different* node than the one it arrived at, adding an extra network hop and, worse, obscuring the real client source IP behind SNAT; `Local` avoids both by only forwarding to same-node pods, but a node with no local pod for that Service then simply drops traffic that lands on it, trading correctness/hop-cost for potentially uneven load distribution.

### Q2 â€” Why is iptables still kube-proxy's default mode despite being the acknowledged performance laggard?
**Testing:** currency and precision â€” this is a genuinely recent, specific fact.
**Answer:** Compatibility. IPVS was added specifically to fix iptables's O(n) chain-walk scaling problem via O(1) hash table lookups, but IPVS itself is deprecated as of Kubernetes 1.35. nftables (stable since 1.33) is the intended long-term replacement â€” atomic rule replacement, comparable-or-better performance â€” but the Kubernetes project has explicitly stated it is not yet the default, for backward-compatibility reasons, with no committed timeline to change that.
**Follow-up trap:** *"If nftables is better and IPVS is deprecated, why not just default to nftables now?"* â€” because defaulting a core networking dataplane on every existing cluster carries real upgrade risk across a huge installed base with varying kernel/tooling support; the project's stated approach is a deliberate, gradual transition rather than an abrupt default change, which is itself a reasonable answer about how infrastructure-critical defaults get changed responsibly at this scale.

### Q3 â€” A team applies a NetworkPolicy restricting ingress to a set of pods, deploys it, and later discovers in a security audit that those same pods can still reach anything outbound. What happened?
**Testing:** the additive, direction-specific nature of NetworkPolicy â€” a very common real mistake.
**Answer:** NetworkPolicy is direction-specific â€” writing a policy that selects those pods only for `Ingress` flips ingress to default-deny-then-allow for them, but leaves egress completely untouched at its original default-allow posture, since no policy ever selected those pods for the `Egress` direction. This is the single most common NetworkPolicy misconfiguration; a real zero-trust posture requires an explicit `policyTypes: [Ingress, Egress]` default-deny baseline, then scoped allow rules for both directions as needed.
**Follow-up trap:** *"If a second policy is later added selecting the same pods for Egress only, does it silently override or narrow the still-open-by-default egress, or does something break?"* â€” nothing breaks; policies are purely additive/OR'd, so adding the first policy that selects those pods for Egress is what actually flips egress to default-deny for the first time â€” before that policy existed, egress was open regardless of how many Ingress-only policies already existed for those same pods.

### Q4 â€” Your organization runs a cluster on plain Flannel. You've written comprehensive NetworkPolicy objects. Are you actually protected?
**Testing:** the CNI-dependency gap, a genuinely dangerous and common misunderstanding.
**Answer:** Not necessarily â€” NetworkPolicy objects are just schema-validated API data; nothing enforces them unless the CNI plugin implements a policy controller watching and programming actual traffic rules from them. Plain Flannel, in its basic form, implements no NetworkPolicy enforcement at all, so those objects would be entirely inert while `kubectl get networkpolicy` shows them looking correctly applied â€” a false sense of security that typically only surfaces during an incident or a real audit that actually tests enforcement rather than checking object existence.
**Follow-up trap:** *"How would you actually verify enforcement rather than just object existence?"* â€” test it directly: deploy two pods, apply a deny policy between them, and attempt the traffic that should now be blocked (a simple `kubectl exec ... curl` from one pod to the other) â€” if it still succeeds, the CNI isn't enforcing policy regardless of how correct the YAML looks, and that live test should be part of any cluster's baseline validation, not assumed from documentation about the CNI choice.

### Q5 â€” Explain `ndots:5` and why it matters for a service that calls an external third-party API.
**Testing:** whether this genuinely-easy-to-miss DNS behavior is understood mechanically, not just as "DNS is sometimes slow."
**Answer:** Every pod's default resolver config sets `ndots:5` alongside a search list of in-cluster domain suffixes. Any hostname with fewer than 5 dots gets each search suffix tried, in order, before an absolute lookup is attempted â€” so a call to `api.stripe.com` (2 dots) triggers up to 4 failed internal lookup attempts (each a real round trip with a negative response) before the 5th, correct, bare lookup finally succeeds, multiplying the DNS portion of that call's latency by up to roughly 5x on a cold lookup.
**Follow-up trap:** *"Wouldn't caching fix this after the first request?"* â€” it helps subsequent requests to the *same* hostname (the negative responses get cached too, up to their TTL), but it doesn't help the first request to any given external hostname, which matters disproportionately for cold-start-sensitive paths, low-traffic external dependencies hit infrequently enough to keep expiring from cache, or services with many distinct external hostnames where "the first call to each" happens far more often than the caching benefit suggests.

### Q6 â€” What's structurally different about DNS for a headless Service versus a normal ClusterIP Service?
**Testing:** the SRV-record/per-pod-name distinction, tying back to why StatefulSet requires headless Services.
**Answer:** A normal ClusterIP Service's DNS answer is a single A record pointing at the virtual IP â€” the actual pod behind it is opaque to the client. A headless Service (`clusterIP: None`) returns the individual pod IPs directly instead (or per-pod names for a StatefulSet's pods specifically), and additionally publishes SRV records so a client can discover both the IP *and* port of each backing pod in one lookup, without a separate query â€” a materially different DNS answer shape that's what makes addressing a *specific* pod (rather than any interchangeable one) possible at all.
**Follow-up trap:** *"Does a headless Service still load-balance across the returned pod IPs?"* â€” no, that's precisely the point of "headless" â€” there's no virtual IP and no proxying/load-balancing layer at all; the client (or its client-side DNS/connection library) is responsible for choosing which of the returned addresses to use, which is exactly the control a StatefulSet client needs when it must address a specific ordinal rather than accept any pod.

### Q7 â€” Why is ingress-nginx's retirement significant, and does it mean the Ingress API itself is going away?
**Testing:** the specific, current, and easy-to-conflate distinction between an API and a controller implementation.
**Answer:** No â€” Kubernetes SIG-Network has stated the core Ingress API will continue to be maintained for the foreseeable future. What's retiring is one specific, widely-deployed controller implementation, ingress-nginx, moving to best-effort-only maintenance through March 2026 and then read-only archival â€” no further bug fixes or security patches after that. Anyone running ingress-nginx specifically needs a real migration plan (to another Ingress controller, or to Gateway API); anyone running Ingress via a different, actively maintained controller isn't directly affected by this specific announcement.
**Follow-up trap:** *"Given the API itself isn't going away, is there still a reason to prefer Gateway API for a brand-new cluster today?"* â€” yes, independent of the ingress-nginx retirement specifically: Gateway API's role-oriented model (infra owns Gateway, app teams own HTTPRoute) and native support for traffic splitting/header-based routing without vendor-specific annotations is a genuinely better fit for how most platform teams actually operate, and it's now GA and production-ready, removing the main historical objection to adopting it early.

### Q8 â€” Walk through why EndpointSlices replaced the older single Endpoints object.
**Testing:** the scale-driven history, not just "EndpointSlices are newer."
**Answer:** A Service's original single Endpoints object listed every matching pod's IP in one API object; for a Service with thousands of backing pods, any single pod's IP changing required rewriting and re-serializing/re-watching that entire large object across every kube-proxy and controller watching it, becoming a real etcd-write-size and watch-propagation bottleneck at scale. EndpointSlices shard endpoints into multiple smaller objects (roughly 100 endpoints per slice by default), so a single pod IP change only requires updating and propagating the one small slice containing it, not the entire Service's full endpoint list.
**Follow-up trap:** *"Does this mean the old Endpoints object is gone entirely?"* â€” it's still created for backward compatibility with older tooling/clients that only understand the original API, but EndpointSlices are the actual source kube-proxy and other components consume for anything at meaningful scale, and the old object should be treated as a legacy compatibility shim rather than the primary mechanism going forward.

### Q9 â€” What does the CNI spec's `ADD`/`DEL` model actually do, mechanically, when a pod is created?
**Testing:** whether "CNI" is understood as a concrete exec-based contract, not an abstract buzzword.
**Answer:** When kubelet creates a pod's network namespace (sandbox), it invokes the configured CNI plugin binary with an `ADD` command and a JSON config describing the pod; the plugin is responsible for allocating an IP (from whatever IPAM scheme it uses â€” per-node CIDR blocks are common), creating the veth pair or equivalent connecting the pod's network namespace to the node's networking stack, and programming whatever routing/overlay/policy mechanism that CNI implements (VXLAN encapsulation for a simple overlay, BGP route advertisement for Calico's non-overlay mode, eBPF program attachment for Cilium). `DEL` is the inverse, invoked on pod teardown to release the IP and clean up the wiring.
**Follow-up trap:** *"If two different CNI plugins are somehow both configured on the same node, what happens?"* â€” this is explicitly not a supported configuration for normal cluster networking (as opposed to Multus, a meta-plugin specifically designed to attach multiple network interfaces per pod for specialized cases) â€” kubelet expects exactly one CNI config to be authoritative per node, and having conflicting configs present is a misconfiguration that produces unpredictable, hard-to-debug pod networking behavior, not a supported multi-CNI setup.

### Q10 â€” Why does Cilium's eBPF approach claim a fundamentally different scaling characteristic than iptables, not just "faster"?
**Testing:** the actual algorithmic distinction (O(n) vs effectively O(1)/logarithmic), not marketing language.
**Answer:** iptables evaluates Service NAT rules as a sequential chain walk â€” cost grows roughly linearly with the number of rules (Services/endpoints), which is why the gap becomes dramatic specifically at high Service/policy counts (often cited around 1,000+ policies as where the difference becomes stark) rather than being uniformly "a bit faster" at every scale. eBPF programs backing Cilium's dataplane compile policies into efficient in-kernel maps with near-constant or logarithmic lookup cost regardless of rule count, so the performance gap isn't a fixed multiplier, it's a difference in growth curve â€” small clusters may see little practical difference, while very large ones see the iptables approach degrade in a way eBPF's approach structurally doesn't.
**Follow-up trap:** *"Does this mean IPVS, which is also roughly O(1) via hash tables, gives you the same benefit as eBPF?"* â€” for pure Service load-balancing lookup cost, they're comparably fast; but IPVS is still layered on top of the traditional netfilter/iptables machinery for other functions (and is now deprecated regardless), whereas Cilium's eBPF approach replaces the Service-proxying model end to end, including NetworkPolicy enforcement and observability (Hubble), in a single coherent mechanism rather than combining several separate subsystems â€” the scope of what's unified is the more meaningful difference at that point, not just the Service-lookup complexity class alone.

### Q11 â€” Give a concrete debugging methodology for "Service X is unreachable from pod Y" that correctly isolates the failing layer.
**Testing:** structured incident debugging skill, the practical payoff of understanding the layers separately.
**Answer:** First confirm the Service actually has healthy endpoints (`kubectl get endpointslices` / `kubectl describe service`) â€” no endpoints means the selector doesn't match any Ready pod, an application/labeling problem, not a networking one. If endpoints exist, test raw pod-to-pod connectivity directly (bypassing the Service, hitting the pod IP:port from pod Y) to isolate whether this is a CNI/routing problem versus a Service/kube-proxy problem specifically. If direct pod-to-pod works but the Service VIP doesn't, inspect kube-proxy's actual programmed state for that mode (iptables rules, ipvsadm output, or the eBPF-CNI's own debugging tool). If both work but only from certain source pods, suspect NetworkPolicy (check what's applied, and independently verify the CNI enforces it at all) rather than a generic connectivity bug.
**Follow-up trap:** *"What if direct pod-to-pod IP connectivity itself fails, isolating it to a CNI-level problem â€” what do you check next?"* â€” cross-node vs same-node specifically (a very different failure surface: same-node usually means a local bridge/veth misconfiguration, cross-node usually means overlay/BGP routing or an MTU mismatch between the encapsulated and physical interface), then the CNI's own daemon logs and node-level agent health on both the source and destination nodes, since a CNI daemon crash-looping on one specific node explains asymmetric connectivity failures that a purely Service/DNS-level investigation would never surface.

### Q12 â€” When would you deliberately avoid migrating from Ingress to Gateway API even for a new project starting today?
**Testing:** the senior "when NOT to" call against a genuinely trending recommendation.
**Answer:** When the routing needs are simple (basic host/path HTTP routing, no traffic splitting or complex header logic needed), the team already has deep operational familiarity with a specific, actively-maintained Ingress controller (not ingress-nginx specifically, which has the retirement forcing function), and there's a non-HTTP protocol requirement that depends on TCPRoute/UDPRoute, which remain experimental in Gateway API and don't yet have the same production-hardening as core Ingress's simpler but broader protocol support.
**Follow-up trap:** *"Isn't 'the team is familiar with the old way' a weak justification, given Gateway API is clearly the future?"* â€” it's weak in isolation, but paired with "the current setup has no concrete limitation actually being hit" it's exactly SIG-Network's own stated migration guidance â€” the cost of unforced migration churn (new failure modes, new debugging muscle memory needed, real engineering time) is a legitimate thing to weigh against being on the newer standard for its own sake, and a staff-level answer should be able to articulate that tradeoff rather than reflexively recommending the newest tool.

---

## Red flags that fail you

- Claiming NetworkPolicy is enforced by Kubernetes itself regardless of CNI choice.
- Writing (or describing) an ingress-only NetworkPolicy and believing egress is now also restricted.
- Not knowing that IPVS is deprecated (1.35) or that nftables, not IPVS, is the intended kube-proxy replacement.
- Dismissing `ndots:5` DNS latency as negligible or not knowing what it is at all.
- Claiming the Ingress *API* is being deprecated rather than correctly scoping the ingress-nginx retirement to that specific controller.
- Recommending `LoadBalancer` Service type as the default for every microservice without acknowledging the per-Service cloud LB cost.
- Confusing "the CNI plugin" with "kube-proxy" as if they're the same layer â€” CNI handles pod-to-pod L3 connectivity, kube-proxy (or its eBPF replacement) handles Service virtual-IP translation, genuinely separate concerns even though both sit in the networking stack.

---

## Cheat card

```
SERVICE TYPES: ClusterIP (internal VIP, default) | NodePort (30000-32767 range, every
  node, DNAT'd, extra hop unless externalTrafficPolicy: Local) | LoadBalancer (NodePort +
  cloud LB, real $ per Service) | ExternalName (pure CNAME) | Headless (clusterIP: None,
  per-pod IPs + SRV records, required for StatefulSet)

KUBE-PROXY MODES: iptables (DEFAULT, O(n) chain walk, slow at scale, non-atomic reload)
  IPVS (O(1) hash table, DEPRECATED as of 1.35)
  nftables (stable since 1.33, atomic replacement, intended long-term default, NOT
    default yet â€” compatibility reasons)
  eBPF (Cilium) bypasses kube-proxy entirely, different architecture not just a mode

NETWORKPOLICY: default = allow-all until ANY policy selects a pod for a DIRECTION
  then default-deny for that direction only. Additive/OR'd, no explicit "deny" rules.
  #1 mistake: ingress-only policy, egress stays wide open (forgot policyTypes: Egress)
  ENFORCEMENT DEPENDS ON CNI â€” plain Flannel enforces NOTHING, policies silently inert

DNS: CoreDNS default since 1.13. ndots:5 default -> names w/ <5 dots try EVERY search
  suffix (namespace.svc.cluster.local, svc.cluster.local, cluster.local) BEFORE absolute
  lookup -> external API calls: up to 4 wasted round trips before correct 5th lookup
  FIX: trailing dot on FQDNs in code, tune dnsConfig ndots, or NodeLocal DNSCache

INGRESS vs GATEWAY API: Ingress = thin (host/path/TLS), rest = non-portable annotations
  Gateway API = GA, role-split (Gateway=infra-owned, HTTPRoute=app-owned), native
  traffic-split/header routing. ingress-nginx: best-effort only til Mar 2026, then
  archived. Core Ingress API itself: SIG-Network says maintained indefinitely, NOT dying.
  TCPRoute/UDPRoute still experimental â€” non-HTTP parity gap remains

EndpointSlices replaced single Endpoints object: shard ~100 endpoints/slice, avoids
  rewriting one giant object on every pod IP churn at scale

CNI (2017, CNCF): exec-based ADD/DEL contract, allocates pod IP + wires routing/overlay
  Cilium (eBPF) overtook Flannel/Calico as most-used CNI in prod, CNCF 2025 survey (+47% YoY)
```

## Sources

- [NFTables mode for kube-proxy â€” Kubernetes Blog](https://kubernetes.io/blog/2025/02/28/nftables-kube-proxy/) â€” accessed 2026-08-02
- [Kubernetes Ingress vs Gateway API: What to Use in 2026 â€” OneUptime](https://oneuptime.com/blog/post/2026-02-20-kubernetes-ingress-vs-gateway-api/view) â€” accessed 2026-08-02
- [Is It Time to Migrate? A Practical Look at Kubernetes Ingress vs. Gateway API â€” Tigera/Calico](https://www.tigera.io/blog/is-it-time-to-migrate-a-practical-look-at-kubernetes-ingress-vs-gateway-api/) â€” accessed 2026-08-02
- [Cilium vs Calico vs Flannel: Kubernetes CNI Comparison 2026](https://sanj.dev/post/cilium-calico-flannel-cni-performance-comparison/) â€” accessed 2026-08-02
- Kubernetes documentation â€” Service, EndpointSlices, NetworkPolicy, DNS for Services and Pods (`kubernetes.io/docs/concepts/services-networking/`)
- Gateway API official documentation, `gateway-api.sigs.k8s.io` â€” resource model and GA status
- CNCF Annual Survey 2025 â€” CNI adoption figures

## Changelog
- 2026-08-02 â€” created
