# Production notes — K8s networking

## What you'd actually use

| Layer | In-tree (default) | The thing people actually run |
|---|---|---|
| Service → endpoints | iptables kube-proxy | IPVS kube-proxy (large clusters), or eBPF (Cilium) — no kube-proxy at all |
| DNS | CoreDNS (`:53`, `cache 30`, `errors`, `ready`) | NodeLocal DNSCache to kill the 5s `ndots:5` timeout |
| NetworkPolicy | whatever the CNI implements | Cilium (L7 too), Calico (global + BGP), Amazon VPC CNI (the default on EKS — policy via a plugin) |

**The single most important fact:** NetworkPolicy is implemented **entirely by the CNI plugin**. The API server happily stores your policy; if the CNI doesn't enforce it, nothing happens. Kubernetes ships no default CNI enforcement.

## iptables vs IPVS vs eBPF

- **iptables kube-proxy** — O(n) linear rule walk per packet-path, and every Service change rewrites a chunk of the ruleset: tens of thousands of Services → multi-second `iptables-restore` storms and 503s during churn. But it's what's in-tree, and it's `iptables-save | grep KUBE-SVC` debuggable. That grep is why the lab's rule format mimics the chain naming.
- **IPVS mode** — hash-table lookup instead of linear walk, native load-balancing algorithms (rr, lc, sh). Needs the `ip_vs` kernel modules. Switch when Service count hurts (~5k+), not before.
- **eBPF (Cilium)** — per-pod socket-level load-balancing, kube-proxy eliminated, DDoS-grade policy at L3-L7. The cost: your networking team must now know eBPF, and debugging is `cilium monitor` instead of a tool everyone has run for 20 years.

## CoreDNS in practice

- The pod's `/etc/resolv.conf` search list has **`ndots:5`** — `db` is tried as `db.default.svc.cluster.local` only after failing as an FQDN, an absolute TLD. That's why an external name that misses the search path can eat 5+ seconds of DNS timeout. NodeLocal DNSCache exists almost entirely for this.
- `db.other.svc.cluster.local` resolves cluster-wide: cross-namespace calls need **no Service, policy or permission to do DNS** — but the *connection* is then judged by NetworkPolicy. DNS is allowed; traffic is not.

## The default-allow gotcha

Kubernetes NetworkPolicy is **allow-by-default**: a pod with no policy selecting it accepts traffic from anywhere. Teams "secure" a namespace by writing a policy per pod and miss one — the missed pod is the breach. The professional pattern is a **default-deny** policy (`podSelector: {}` selects every pod in the namespace) *plus* explicit allows. Your lab enforcer implements the raw semantics; production starts from default-deny and layers allows on top.

Also: policies are **additive** — multiple policies selecting a pod OR their ingress entries together, never AND. You encoded that OR when checking "some ingressFrom entry matches."

## CNI responsibilities (and nothing else)

A CNI must: allocate pod IPs, wire the veth pair into the node bridge, program routes so any node can reach any pod IP, and — if it claims the policy API — enforce NetworkPolicy. It does **not** do Service VIPs or DNS (kube-proxy/Cilium and CoreDNS own those). Naming the boundary — "CNI = pod network, kube-proxy = Service VIP, CoreDNS = names" — is a stronger interview answer than any single product.

## The 3 questions an interviewer asks after you describe this

1. *"A pod's DNS works, the Service has endpoints, and curl still fails — where do you look?"* — kube-proxy: `iptables-save | grep KUBE-SVC`, `kubectl get endpoints`, then the policy: does the CNI actually enforce? (Also `dnsutil dnstrace`, and check the annotation that pinned the wrong policy mode.)
2. *"Why does your `db` DNS call sometimes take 10 seconds to fail?"* — `ndots:5` search-list expansion: up to 4 search domains tried before the absolute name, each with a timeout, before the real lookup runs. NodeLocal DNSCache + `single-request-reopen` or an FQDN with a trailing dot.
3. *"NetworkPolicy: is your namespace secure?"* — only if you started from default-deny (`podSelector: {}`) and the CNI enforces it; otherwise "no policy matches, so allow" is still true and the first missed pod is a hole. Egress, not just ingress, when the worry is exfiltration.
