# Lab 04: K8s Networking — Services, kube-proxy, DNS, Policy

**Track:** T12 DevOps, Infra & Security · **Time:** 3h · **XP:** 50
**Module:** `T12-k8s-networking`

**You will build:** an in-memory cluster network — pods, Services with label selectors, ClusterDNS name resolution, a deterministic kube-proxy chain renderer, and a default-allow NetworkPolicy enforcer — pure stdlib, no cluster, no node.

**You will be able to answer:** *"A pod calls `http://db:5432` — walk me through every hop, and who blocks it when it suddenly stops working?"*

## Setup

```bash
cd labs/misc/04-k8s-networking
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`ClusterNetwork`** — the cluster's networking state:
   - `pods`: `{ip: {"name", "namespace", "labels"}}`
   - `services`: `{name: {"cluster_ip", "selector", "ports", "type"}}`
   - `namespaces`: `{ns_name: {"labels"}}`
   - Registrars: `register_pod(ip, name, namespace, labels)`, `register_service(name, cluster_ip, selector, ports, type="ClusterIP")`, `register_namespace(name, labels)`.
2. **Label semantics** — a selector matches a pod iff the pod's labels are a **superset** of the selector (every `key:value` in the selector appears in the labels). An empty selector matches every pod. This one rule powers Services, endpoints, and NetworkPolicy alike.
3. **`dns_name(service, namespace="default")`** → `"<service>.<namespace>.svc.cluster.local"`.
4. **`resolve(dns_name_string)`** → `(service_dict, endpoint_pods)`:
   - parse the DNS string: first label = service, optional second label = namespace — anything after `.svc` is ignored; no namespace label means `"default"`;
   - unknown service → `LookupError`;
   - endpoints = pods whose labels superset-match the service's selector **in that namespace**, in registration order. Cross-namespace calls resolve — DNS is cluster-wide; the *endpoints* are namespace-scoped.
5. **`kube_proxy_rule(service_name, service)`** → deterministic string:
   `KUBE-SVC-<sha256(service_name)[:10]> <cluster_ip>:<port> -> [ip:port, ...]`
   with `<port>` = the first port in `service["ports"]`, one endpoint per matching pod in the service's namespace, and `[]` when there are no backends. Same state → same rule, every time — that determinism is why real kube-proxy chains are debuggable.
6. **`NetworkPolicyEnforcer(network)`** with a `policies` list of
   `{"podSelector": {...}, "ingressFrom": [{"podSelector": {...}} | {"namespaceSelector": {...}}]}`:
   - **no policy's `podSelector` matches dst → allow** (k8s is default-allow — the gotcha);
   - if any policy selects dst → allowed iff **some** ingressFrom entry matches src: a `podSelector` entry superset-matches the **src pod's** labels; a `namespaceSelector` entry superset-matches the labels of the **src's namespace**;
   - a matching policy with no matching ingress entry → **deny** (default-deny for the selected pod).

## Run the tests

```bash
python -m pytest tests -q                 # against starter/ → FAILS. Make them pass.
python -m pytest tests -q --solution      # the reference — all green
```

## Stretch goals

1. **Headless services** — `cluster_ip: None` means DNS returns the pod IPs directly, one A record per endpoint. *("When do you want a Service that load-balances nothing?")*
2. **ExternalName + FQDN loops** — a CNAME alias that can point back into the cluster; detect the loop. *("What does CoreDNS do when the alias is the name it's serving?")*
3. **Session affinity** — extend `kube_proxy_rule` with a hash-of-client-IP comment so the same client pins the same backend. *("Where does iptables `recent` match break under SNAT?")*
4. **Egress policy** — mirror the ingress rules on the src side: a pod selected by an egress policy can only talk to `egressTo` entries. *("Why is egress the one everyone forgets until the data exfil question?")*
