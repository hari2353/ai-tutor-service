# Production notes — SPIFFE / SPIRE / mTLS in real systems

## What you'd actually use

| Layer | Tool |
|---|---|
| Identity issuance | **SPIRE** (agent + server), or the platform's built-in CA: Istiod in Istio, cert-manager in Kubernetes, AWS PCA / GCP CAS |
| Identity format | **X.509-SVID** (the common case) or JWT-SVID (for L7 hops that can't do TLS, e.g. through an LB that terminates TLS) |
| Handshake enforcement | Envoy sidecars (Istio), or native: Go's `crypto/tls` `VerifyPeerCertificate`, `spiffe-go` workload API |
| Policy | OPA / SPIFFE-friendly authz (e.g. SPIRE's `spire-server` entries + your policy engine), or Istio `AuthorizationPolicy` with SPIFFE-id principals |

**Do not roll your own TLS.** You implement the *authorization logic* (as in this lab); the cryptography is a library's job.

## What production adds over your simulation

- **Workload attestation.** The hard part isn't the handshake — it's deciding *who gets an identity in the first place*. SPIRE agents attest workloads via selectors that are hard to forge: Kubernetes service account token + pod namespace, X.509 node attestation, Unix UID/GID, AWS instance identity documents, GCP instance metadata tokens. A pod claiming to be `payments` must *prove* it — the agent checks, then the SPIFFE id is minted. Your lab starts after this step; production lives and dies by it.
- **SVIDs are short-lived X.509s — not service certs.** What replaces the long-lived cert in `/etc/ssl/certs/service.pem` (valid 1 year, private key on disk, rotated by a cron nobody monitored) is an SVID with a lifetime typically around **1 hour**, auto-rotated by the agent *before* expiry, with the private key generated in memory and never written to disk. A leaked SVID is useful to an attacker for minutes, not quarters — and there is no "rotate the cert" runbook because rotation is the steady state.
- **mTLS in the mesh is mostly sidecar work.** In Istio, the sidecar proxies present and verify SVIDs on every service-to-service connection (PeerAuthentication `mTLS` mode), so a compromised pod *inside* the mesh still can't impersonate another service. Your application-level `AuthorizationPolicy` then matches on the peer's SPIFFE id (Istio exposes it as the source principal) — exactly the prefix rules from this lab, but enforced at L4/L7 boundary by the proxy.
- **Federation between trust domains.** Cross-domain trust in production means **bundle exchange**: each SPIRE server publishes its trust bundle (the CA public keys) at a bundle endpoint, and the other side configures it as a federated bundle. Then a `spiffe://partner.io/...` SVID chains to partner's CA, which you've declared you trust — the equivalent of this lab's `federates_with`, but with real signature chains. Meshes approximate this: Istio multi-cluster does it by sharing root CAs or configuring explicit remote trust domains.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Service-to-service calls fail after cluster merge | Two clusters minting ids in the same trust domain with different CAs | Distinct trust domains per cluster, then federate |
| Handshake loops / retry storms after CA rotation | Bundle cached only in memory, refreshed too rarely | Bundle freshness checks + long grace overlap on CA rotation |
| mTLS on, but authz still checks API keys | Identity plumbing done, policy layer not migrated | Retire the shared secret once the principal check works — otherwise you carry both costs |
| SVID expires mid-request, connection drops | Long-lived connections outliving SVID lifetime | Keep connections short, or rotate certs on open connections (Envoy handles this) |
| "Everyone trusts everyone" federation sprawl | `federates_with` grows by ticket, never shrinks | Federation is a security decision — review it like access grants |

## The 3 questions an interviewer asks after you describe this

1. *"How does a workload prove what it is — what stops me from asking for the payments identity?"* — attestation selectors (k8s SA token, node certs, cgroups). Identity is *derived from what you provably are*, not from a secret you present; anything secret-based reintroduces the leak problem SVIDs exist to kill.
2. *"SVIDs are valid an hour — what happens to in-flight connections at expiry?"* — mTLS authenticates at handshake; established connections aren't re-challenged. Meshes rotate certs on live connections; defense in depth is short connection lifetimes.
3. *"Why is mTLS in a mesh not enough — you still wrote an AuthorizationPolicy?"* — mTLS answers *who is calling* (authentication); your policy answers *may they do this* (authorization). AuthN without AuthZ is a bouncer who checks IDs then lets everyone in.
