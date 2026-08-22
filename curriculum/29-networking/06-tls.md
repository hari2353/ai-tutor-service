# TLS 1.3: Handshake, Certificates, SNI, ALPN, mTLS, Cipher Suites, Debugging with openssl

> **Track:** T29 Networking & Protocols · **Time:** 2.5h · **Prereqs:** T29-tcp-deep · **Updated:** 2026-07-26
> **Module id:** `T29-tls` · **Tags:** security, critical

## The 30-second version

TLS 1.3 completes a full handshake in 1 RTT by having the client guess the server's preferred key-exchange group and send a key share speculatively in the ClientHello, so the server can reply with its own key share, certificate, and Finished message in one flight. TLS 1.2 needed 2 RTTs because key exchange and cipher negotiation happened as separate round trips. Certificate validation walks the chain from leaf to a trusted root, verifying each signature and the hostname/SAN match; revocation is checked via OCSP, ideally stapled by the server so the client doesn't make a separate blocking call. SNI puts the target hostname in the ClientHello in plaintext so a server can pick the right certificate before decryption is even possible — which is also a metadata leak that Encrypted ClientHello (ECH) is rolling out to close. mTLS flips the CertificateRequest around so the server also authenticates the client, standard for service-mesh zero-trust internal traffic. 0-RTT resumption is fast but replayable by a network attacker, so it's restricted to idempotent requests only.

## Why this gets asked

Because TLS is the layer where "it works on my machine" turns into "it works everywhere except this one enterprise proxy that MITMs traffic," and every senior engineer eventually debugs a cert-chain, SNI, or cipher-negotiation failure at 2am with nothing but `openssl s_client` output. The interviewer has lived through an expired intermediate cert that passed every internal test because the leaf and root were both still valid, or a client library that silently fell back to TLS 1.0 because it didn't send the right extensions. They want to see you reason from the actual bytes on the wire, not from "HTTPS means encrypted."

---

## Lineage: past → present → future

**What came before.** SSL 2.0 (1995) and 3.0 (1996) were the first attempts and both had cryptographic design flaws serious enough to be fully deprecated (SSLv3 killed off by the POODLE attack, 2014). TLS 1.0/1.1 (1999/2006) patched forward but inherited weak defaults — CBC-mode ciphers vulnerable to BEAST and Lucky 13, RC4 as an allowed (later mandatory-to-avoid) cipher, and no forward secrecy by default since static RSA key exchange was common. TLS 1.2 (2008) added AEAD ciphers (GCM) and made forward-secret key exchange available, but kept renegotiation (a real attack surface — CVE-2009-3555) and required 2 full round trips: one to negotiate the cipher suite and exchange randoms, a second to actually exchange keys and authenticate. The specific pain: every new HTTPS connection paid 2 RTTs of pure handshake latency on top of the TCP handshake's own RTT, which on mobile networks with 100-300ms RTTs was hundreds of milliseconds before a single byte of the actual page loaded.

**Where it stands now.** TLS 1.3 (RFC 8446, 2018) is the current standard: 1-RTT handshake by having the client speculatively send a key share for its guessed-preferred group, removal of static RSA key exchange entirely (every 1.3 handshake is forward-secret), removal of renegotiation and compression (both were attack surfaces, not features anyone needed), and a radically simplified cipher suite list — five suites total, all AEAD, versus dozens of combinatorial TLS 1.2 suites. Browsers and major CDNs default to 1.3 now; TLS 1.0/1.1 are formally deprecated (RFC 8996, 2021) and most modern stacks refuse to negotiate them. The live disagreement is around **0-RTT data**: it's specified and shipped (used heavily by Cloudflare and others for resumed connections) but its replay exposure means it's restricted to idempotent operations, and plenty of security teams disable it entirely rather than audit every endpoint for idempotency. A second live area: **Encrypted ClientHello (ECH)**, which hides SNI (and other ClientHello metadata) from network observers — deployed by Cloudflare and reaching broader browser support, but not universal, partly because it requires DNS-based key distribution (HTTPS/SVCB records) that not every resolver and CDN path supports yet.

**Where it's heading.** Post-quantum key exchange is the clearest direction of travel — hybrid key exchange combining classical ECDHE with a post-quantum KEM (ML-KEM/Kyber) is already deployed by Chrome and Cloudflare for a meaningful fraction of TLS 1.3 connections as of the last two years, driven by "harvest now, decrypt later" threat modeling. Confidence: high that hybrid PQ key exchange becomes default within a few years; lower on exact timeline for classical-only key exchange being fully retired. ECH becoming ubiquitous is directional but gated on DNS ecosystem support — treat "ECH is standard everywhere" as not yet true in mid-2026. Certificate lifetimes are also compressing (the CA/Browser Forum has been steadily shortening maximum validity, with proposals to reach 47 days by 2029), pushing the industry hard toward fully automated issuance (ACME/Let's Encrypt-style) as a prerequisite rather than an option.

---

## Mental model

```
CLIENT                                                          SERVER
  |--- ClientHello ---------------------------------------------->|
  |     + supported_versions (TLS 1.3)                            |
  |     + key_share (client's guess: e.g. X25519 public value)     |
  |     + SNI (hostname, PLAINTEXT)                                |
  |     + ALPN (h2, http/1.1)                                      |
  |     + signature_algorithms, supported_groups                   |
  |                                                                 |
  |<-- ServerHello -------------------------------------------------|
  |     + key_share (server's public value)                        |
  |<-- {EncryptedExtensions} ----------------------------- 1 flight |
  |<-- {CertificateRequest}   (only for mTLS)                       |
  |<-- {Certificate}          (server's chain)                      |
  |<-- {CertificateVerify}    (signature proving key possession)    |
  |<-- {Finished}                                                   |
  |                                                                 |
  |--- {Certificate}          (only for mTLS, client's chain) ----->|
  |--- {CertificateVerify}    (only for mTLS) ----------------------|
  |--- {Finished} -------------------------------------------------->|
  |                                                                 |
  |=== Application Data (1-RTT total before this point) ===========|

{ } = encrypted under handshake traffic keys, derived right after key_share exchange
```

The one thing to internalize: everything after `ServerHello` is already encrypted, because both sides can derive traffic keys the instant they see each other's key shares. TLS 1.3 moved authentication (certificates) *inside* the encrypted channel — TLS 1.2 sent the certificate in the clear.

---

## How it actually works

### 1-RTT vs TLS 1.2's 2-RTT, precisely

TLS 1.2's first round trip negotiated *which* cipher suite and key-exchange method to use (`ClientHello` → `ServerHello` choosing from the client's offered list); only the second round trip actually exchanged key material and authenticated. TLS 1.3 collapses this by having the client send a `key_share` for its best-guess group (almost always X25519 in practice, since that's what nearly every server supports) in the very first message. If the server supports that group, one round trip suffices. If the server doesn't support the client's guessed group, the server sends a `HelloRetryRequest` naming the group it wants, and the client resends — that specific case falls back to effectively 2 RTTs, so "1-RTT" assumes the common case, not a universal guarantee.

### What TLS 1.3 removed, and why each removal matters

- **Static RSA key exchange** — removed entirely. In TLS 1.2, a client could encrypt a premaster secret directly with the server's RSA public key; if that private key was ever compromised, every past session recorded off the wire could be decrypted retroactively. TLS 1.3 mandates ephemeral Diffie-Hellman (ECDHE) for every handshake, so every session is forward-secret by construction — compromising the server's long-term key doesn't expose past traffic.
- **Renegotiation** — removed. TLS 1.2 allowed renegotiating parameters mid-session; CVE-2009-3555 showed an attacker could inject data across a renegotiation boundary. TLS 1.3 has `KeyUpdate` for rotating keys within a session instead, which doesn't reopen the same attack surface.
- **Compression** — removed. Compression before encryption enabled CRIME/BREACH-style attacks that recover secrets by observing compressed-length side channels.
- **Cipher suite simplification** — TLS 1.2 suites bundled key exchange + authentication + cipher + hash into one name (e.g. `TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256`), producing dozens of combinations with wildly varying security. TLS 1.3 has exactly 5 suites (`TLS_AES_128_GCM_SHA256`, `TLS_AES_256_GCM_SHA384`, `TLS_CHACHA20_POLY1305_SHA256`, plus two rarely-used CCM variants), all AEAD, with key exchange and authentication negotiated as separate, orthogonal extensions.

### Certificate chain validation

A chain is leaf (the server's own cert) → zero or more intermediates → a root the client already trusts (shipped in the OS/browser trust store, never sent over the wire). Validation walks it:

1. **Signature verification, leaf to root.** Each cert's signature is verified using the *issuer's* public key (the next cert up the chain); the root's self-signature is checked against the trust store's pinned copy, not derived from anything sent by the server.
2. **Validity window.** `notBefore`/`notAfter` on every certificate in the chain — an expired *intermediate* fails validation even if the leaf and root are both still valid, which is the classic production incident: nobody rotated the intermediate because "the cert" (meaning the leaf) still shows a future expiry in the dashboard.
3. **Hostname match.** The requested hostname must match a Subject Alternative Name (SAN) entry on the leaf. `CN` (Common Name) matching is deprecated and ignored by modern clients — SAN is the only field that matters now.
4. **Key usage / extended key usage constraints.** e.g., the cert must be marked valid for `serverAuth`.
5. **Revocation.** OCSP (Online Certificate Status Protocol) asks the CA in real time "is this serial number revoked?" — but a live OCSP call per handshake is slow and a privacy leak (the CA learns every site you visit), and if the OCSP responder is unreachable, most clients "soft-fail" (proceed anyway), which defeats the point. **OCSP stapling** fixes both: the server itself periodically fetches a signed OCSP response and staples it into the handshake (`CertificateStatus` / the `status_request` extension), so the client verifies a *fresh, signed* revocation proof without an extra network round trip to the CA and without leaking its browsing to that CA. CRLs (Certificate Revocation Lists) are the older bulk-download alternative, mostly superseded for TLS but still used in enterprise PKI.

### SNI and the plaintext problem

Before SNI (RFC 6066), a server terminating TLS for multiple hostnames on one IP had no way to know *which* certificate to present until after decryption — impossible, since you need the right key to decrypt at all. SNI fixes this by putting the target hostname in the ClientHello, which is sent before any encryption keys exist, so it's necessarily plaintext. That's the tradeoff: virtual hosting for TLS requires either SNI's plaintext leak, one IP per certificate (doesn't scale), or a wildcard/SAN cert covering every hostname on that IP (works but couples unrelated domains' cert lifecycles). Any network observer — a corporate proxy, an ISP, a nation-state censor — can see exactly which hostname you're connecting to even though the rest of the handshake payload and all application data is encrypted. **Encrypted ClientHello (ECH)** is the current answer: it encrypts the "inner" ClientHello (containing the real SNI) inside an "outer" ClientHello using a public key fetched from DNS (an HTTPS/SVCB record), so an observer sees only a generic outer hostname (often a CDN's shared name). Deployed by Cloudflare and gaining browser support, but adoption is gated on DNS infrastructure and is not yet universal as of mid-2026.

### ALPN — protocol negotiation inside the handshake

Application-Layer Protocol Negotiation (RFC 7301) is a ClientHello extension listing the client's supported application protocols in preference order (e.g. `h2`, `http/1.1`); the server picks one and returns it in its own extension in the ServerHello/EncryptedExtensions. This is how a client and server agree on HTTP/2 vs HTTP/1.1 *before* a single application byte is sent — no separate upgrade request needed, unlike the old cleartext `Upgrade:` header dance for h2c. If ALPN isn't offered or the server doesn't support the client's list, they fall back to whatever's implied by convention (usually HTTP/1.1).

### mTLS — mutual authentication

Normal TLS only proves the server's identity to the client. mTLS adds the reverse: the server sends a `CertificateRequest` (naming acceptable CA roots), and the client responds with its own `Certificate` + `CertificateVerify` + `Finished`, proving it holds the private key for a cert the server trusts. This is the backbone of zero-trust internal traffic — service meshes (Istio, Linkerd) issue short-lived certs per workload identity (often via SPIFFE/SPIRE) and enforce mTLS between every service pair, so network position alone never grants trust; every call carries cryptographic proof of *which* service is calling. It's rarely used for public-facing APIs (managing client certs for arbitrary end users doesn't scale) but is close to default for service-to-service traffic inside a mesh.

### Session resumption: tickets/PSK vs the old session ID

TLS 1.2 had **session IDs**: the server cached session state server-side keyed by an ID the client could present on reconnect to skip the full handshake — but this required server-side memory per session, which doesn't scale across a load-balanced fleet without shared session storage. **Session tickets** (and TLS 1.3's unification of this into **PSK — pre-shared key — resumption**) flip this: the server encrypts its own session state into an opaque ticket and hands it to the client; the client presents the ticket on reconnect, and the server decrypts it with a key only it holds — no server-side storage needed, any server behind the load balancer that shares the ticket-encryption key can resume the session. TLS 1.3 resumption via PSK can be combined with a fresh key exchange (PSK + (EC)DHE, still forward-secret) or used alone for the fastest possible reconnect, which is where 0-RTT comes in.

### 0-RTT and its replay risk

With a valid PSK from a prior session, a TLS 1.3 client can send **application data in its very first flight**, before any handshake confirmation — zero round trips before real data moves. The catch: this "early data" isn't protected against replay the way the rest of the handshake is. A network-positioned attacker can capture that first flight and resend it verbatim to the server, and the server (which hasn't yet distinguished a replay from a genuine retry at that layer) may process it again. The spec's mitigation is explicit: **0-RTT data must only be used for idempotent requests** — a repeated GET is harmless, a repeated POST that transfers money or creates an order is not ([Trail of Bits — What Application Developers Need To Know About TLS Early Data](https://blog.trailofbits.com/2019/03/25/what-application-developers-need-to-know-about-tls-early-data-0rtt/) — accessed 2026-07-26). Servers can add their own anti-replay defenses (single-use tickets, a shared nonce cache) but the simplest safe policy is refusing 0-RTT for anything mutating.

### Debugging with `openssl s_client`

```
openssl s_client -connect example.com:443 -servername example.com
```

What to actually read in the output:

- **Certificate chain** — the `Certificate chain` block lists each cert in order with its subject and issuer; verify the chain is complete (no missing intermediate) and check `Verify return code: 0 (ok)` at the bottom — anything else (e.g. `20 (unable to get local issuer certificate)`) means a broken or incomplete chain.
- **Negotiated protocol version** — `SSL-Session: Protocol : TLSv1.3` (or whatever was negotiated) — if you expect 1.3 and see 1.2, either the server doesn't support 1.3 or something downgraded the negotiation.
- **Cipher negotiated** — `Cipher : TLS_AES_128_GCM_SHA256` — confirms which of the 5 TLS 1.3 suites was chosen.
- **`-servername`** is what actually populates the SNI extension — omit it and a multi-tenant server may present the wrong (often default/first-configured) certificate, which looks like a cert mismatch bug but is actually a test-harness mistake.
- Add `-alpn h2` to force/verify ALPN negotiation, and `-tls1_2` / `-tls1_3` to pin the version being tested when diagnosing a downgrade.

---

## Build it from scratch

You don't hand-roll TLS (never implement your own crypto primitives), but reasoning about the handshake state machine is fair game and shows up as a whiteboard exercise:

```python
# untested sketch — models handshake STATE, not real crypto
from enum import Enum, auto

class State(Enum):
    START = auto()
    WAIT_SH = auto()          # sent ClientHello, waiting for ServerHello
    WAIT_EE = auto()          # got ServerHello, waiting for EncryptedExtensions
    WAIT_CERT_CR = auto()     # waiting for CertificateRequest (mTLS) or Certificate
    WAIT_CV = auto()          # waiting for CertificateVerify
    WAIT_FINISHED = auto()
    CONNECTED = auto()

def client_handshake_step(state: State, msg_type: str, mtls: bool) -> State:
    transitions = {
        (State.START, "send_client_hello"): State.WAIT_SH,
        (State.WAIT_SH, "server_hello"): State.WAIT_EE,
        (State.WAIT_EE, "encrypted_extensions"): State.WAIT_CERT_CR,
        (State.WAIT_CERT_CR, "certificate_request"): State.WAIT_CERT_CR,  # mTLS: note it, keep waiting
        (State.WAIT_CERT_CR, "certificate"): State.WAIT_CV,
        (State.WAIT_CV, "certificate_verify"): State.WAIT_FINISHED,
        (State.WAIT_FINISHED, "finished"): State.CONNECTED,
    }
    return transitions.get((state, msg_type), state)  # unrecognized transition: hold
```

This is the shape an interviewer wants on a whiteboard: named states, the branch for `CertificateRequest` only appearing under mTLS, and `Finished` as the terminal event before `CONNECTED`. Real implementations (BoringSSL, OpenSSL, rustls) enforce this as a strict state machine and reject out-of-order messages — a classic historical vulnerability class (state-machine confusion bugs like "goto fail") came from *not* enforcing this rigorously.

---

## How it's done in production

| Component | What it adds |
|---|---|
| **Load balancer / edge TLS termination** (ALB, Envoy, nginx, Cloudflare) | Terminates TLS at the edge, handles cert rotation via ACME, offloads crypto from application servers |
| **Certificate automation** (Let's Encrypt / ACME, AWS ACM, cert-manager on k8s) | Issues and auto-renews short-lived certs; removes manual rotation as a failure mode entirely |
| **Service mesh mTLS** (Istio, Linkerd, SPIFFE/SPIRE) | Issues per-workload short-lived certs, enforces mTLS between every pod, rotates on a schedule of hours not months |
| **HSM / KMS-backed private keys** (AWS CloudHSM, Google Cloud KMS) | Private key never leaves hardware/managed boundary; TLS termination signs via an API call instead of holding the raw key in process memory |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Handshake fails only for some clients, works in browser | Client library sending outdated `supported_versions`/missing SNI, or an old TLS stack that can't negotiate 1.3 | Reproduce with `openssl s_client -tls1_2` / `-tls1_3` to isolate which version is actually negotiated |
| Intermittent cert errors that "fix themselves" | Load-balanced fleet where one node has a stale/un-rotated cert while others rotated correctly | Verify all nodes serve identical chain; automate rotation (ACME) so it's atomic across the fleet, not manual per-node |
| Cert valid per browser dashboard but client library rejects it | Missing or expired **intermediate** cert — leaf and root both fine, but the chain has a gap | Serve the full chain (`fullchain.pem`, not just the leaf); check with `openssl s_client` for `Verify return code` |
| Wrong certificate served on a multi-tenant TLS terminator | SNI not received or not matched — server fell back to its default vhost cert | Confirm client actually sends SNI (`-servername` in openssl); check server SNI routing config |
| Revocation check adds 200-500ms to first connection, or fails open silently | Live OCSP lookup to a slow/unreachable responder, most clients soft-fail | Enable OCSP stapling so the client verifies a stapled, signed response instead of a live network call |
| Replayed request causes a duplicate order/charge on a "fast" endpoint | 0-RTT enabled for a non-idempotent POST | Disable 0-RTT for mutating endpoints, or add server-side single-use anti-replay tokens |
| mTLS rollout breaks calls from outside the mesh | STRICT mTLS enforced before all callers were migrated to mesh identities | Roll out PERMISSIVE mode first (accept both plaintext and mTLS) and flip to STRICT only once telemetry confirms 100% of traffic is already mTLS |

---

## Tradeoffs & when NOT to use it

- **Don't enable 0-RTT indiscriminately.** It's a genuine latency win only for resumed connections, and the replay risk is real and exploitable by anyone on-path, not a theoretical footnote. Either scope it to strictly idempotent endpoints or don't turn it on.
- **Don't skip OCSP stapling to "simplify config."** Without it you're either doing a live OCSP round trip per handshake (latency + privacy leak to the CA) or soft-failing revocation checks entirely (a revoked cert gets accepted).
- **mTLS everywhere is not free.** It requires a working PKI (issuance, rotation, revocation) for every workload, and a botched rollout (flipping to STRICT before every caller is migrated) is a self-inflicted outage. Roll out permissive-then-strict.
- **Don't hand-roll certificate validation logic.** Custom chain-walking code is a recurring source of critical vulnerabilities (accepting a self-signed cert as if it were CA-signed, skipping hostname checks) — always use the platform's TLS library's verification path, never write your own.
- **ECH is not yet a universal privacy guarantee.** If your threat model depends on hiding SNI from a network observer today, verify actual deployment on your specific client/server/CDN combination rather than assuming it's on by default.

---

## Interview questions

### Q1 — Walk me through the TLS 1.3 handshake, message by message.
**Testing:** whether you actually know the mechanism or just "it's encrypted now."
**Answer:** ClientHello (with a speculative `key_share`, SNI, ALPN, supported groups/algorithms) → ServerHello (server's own key_share) — at this point both sides derive handshake traffic keys — then the server sends EncryptedExtensions, optionally CertificateRequest (mTLS only), Certificate, CertificateVerify, and Finished, all encrypted. The client replies with its own Certificate/CertificateVerify/Finished only if mTLS was requested, otherwise just Finished. Application data flows after that — one round trip total in the common case.
**Follow-up trap:** *"What if the server doesn't support the client's guessed key-exchange group?"* — `HelloRetryRequest`: the server names the group it wants, the client resends ClientHello with a matching key_share, costing an extra round trip. "1-RTT" is the common case, not a hard guarantee.

### Q2 — Why is TLS 1.3 one round trip faster than 1.2?
**Answer:** TLS 1.2 split negotiation (which cipher suite, which key exchange) from key exchange itself into two sequential round trips. TLS 1.3 has the client speculatively send a key share for its likely-supported group in the very first message, collapsing negotiation and exchange into one flight.
**Follow-up trap:** *"What's the cost of that speculation being wrong?"* — A HelloRetryRequest round trip, functionally reverting to 2-RTT for that one connection — this is why server/client group-list alignment (almost universally X25519 now) matters for actually realizing the 1-RTT benefit at scale.

### Q3 — What did TLS 1.3 remove, and why does each removal matter?
**Answer:** Static RSA key exchange (removed non-forward-secret handshakes entirely — every 1.3 session is forward-secret by construction), renegotiation (closed the CVE-2009-3555 injection surface, replaced by KeyUpdate for in-session key rotation), compression (closed CRIME/BREACH-style side channels), and simplified cipher suites from dozens of combinatorial TLS 1.2 names down to 5, all AEAD.
**Follow-up trap:** *"If a client only supports static RSA key exchange, what happens with a 1.3-only server?"* — The handshake fails outright; there's no negotiated fallback path within TLS 1.3 itself for that key-exchange mode, which is deliberate — it's not a supported option to disable.

### Q4 — How does certificate chain validation actually work?
**Answer:** Verify each certificate's signature using the next certificate up the chain's public key, ending at a root already present in the trust store (never transmitted). Check validity dates on every certificate in the chain, not just the leaf. Match the requested hostname against the leaf's SAN entries (CN is deprecated/ignored). Check revocation, ideally via a stapled OCSP response.
**Follow-up trap:** *"The leaf and root are both valid, connection still fails. Why?"* — An expired or missing **intermediate**. This is the single most common real-world cert outage, precisely because dashboards tend to surface only the leaf's expiry.

### Q5 — What's OCSP stapling and why is it better than a plain OCSP check?
**Answer:** A plain OCSP check means the client calls the CA directly during the handshake — adding a round trip and leaking every site visited to that CA, plus most clients soft-fail if the CA is unreachable, silently accepting a possibly-revoked cert. Stapling has the *server* periodically fetch a signed OCSP response and attach it to the handshake, so the client verifies freshness and validity locally without an extra network call or a privacy leak.
**Follow-up trap:** *"What if the server serves a stale stapled response?"* — Clients check the response's own validity window (`thisUpdate`/`nextUpdate`); a stapled response past that window is treated as if stapling weren't used at all, falling back to the client's configured OCSP policy (soft or hard fail).

### Q6 — Why does SNI leak the hostname, and what fixes it?
**Answer:** SNI must be readable before decryption is possible, because the server needs it to pick the right certificate — the ClientHello containing it is necessarily unencrypted. Any network observer sees the target hostname even though the payload afterward is fully encrypted. Encrypted ClientHello (ECH) fixes it by encrypting the real (inner) ClientHello using a key fetched from DNS, exposing only a generic outer name to observers.
**Follow-up trap:** *"Is ECH deployed everywhere already?"* — No — it's live on some CDNs (Cloudflare notably) and gaining browser support, but adoption depends on DNS infrastructure (HTTPS/SVCB records) that isn't universal, so don't claim it as a default guarantee in mid-2026.

### Q7 — Explain ALPN and how HTTP/2 negotiation actually happens.
**Answer:** ALPN is a ClientHello extension listing supported application protocols in preference order; the server picks one from that list and returns its choice inside the encrypted handshake extensions. This is how a client and server agree on `h2` vs `http/1.1` as part of the TLS handshake itself, with zero extra round trips — no cleartext `Upgrade:` header dance is needed (that's the older h2c/HTTP-only mechanism, not used over TLS).
**Follow-up trap:** *"What if the client offers h2 but the server only supports http/1.1?"* — The server returns http/1.1 in its ALPN response (or omits the extension), and the client proceeds with HTTP/1.1 over that same TLS connection — no separate negotiation attempt or reconnection needed.

### Q8 — What is mTLS, and when do you actually deploy it versus normal one-way TLS?
**Answer:** The server also requests and verifies a client certificate (`CertificateRequest` → client's `Certificate`/`CertificateVerify`/`Finished`), proving the client's identity cryptographically rather than by network position. Standard for service-to-service traffic inside a zero-trust mesh (Istio/Linkerd with SPIFFE/SPIRE identities), rare for public consumer-facing APIs because managing client certs for arbitrary end users doesn't scale operationally.
**Follow-up trap:** *"How do you roll out mTLS without an outage?"* — Permissive mode first (accept both plaintext and mTLS while the mesh is populated), verify via telemetry that 100% of real traffic is already mTLS, then flip to STRICT. Going straight to STRICT is how you break every caller that hasn't yet been onboarded to the mesh.

### Q9 — Session tickets/PSK vs the old session ID mechanism — what changed and why?
**Answer:** Session IDs required server-side session state, cached and looked up by ID — doesn't scale cleanly across a load-balanced fleet without shared session storage. Session tickets invert it: the server encrypts its own session state into an opaque ticket handed to the client, so any server sharing the ticket-encryption key can resume the session with zero server-side storage. TLS 1.3 unifies this as PSK-based resumption, optionally combined with a fresh (EC)DHE exchange to keep forward secrecy on resumed connections too.
**Follow-up trap:** *"Is a PSK-only resumption (no fresh DHE) still forward-secret?"* — No — pure PSK resumption reuses key material derived from the original handshake, so if that original session's keys are ever compromised, resumed sessions using the same PSK are exposed too. PSK + (EC)DHE ("PSK-DHE") restores forward secrecy at the cost of the fresh key exchange, which is why some implementations require it rather than allowing pure PSK.

### Q10 — What is 0-RTT and why is it dangerous?
**Answer:** With a valid PSK from a previous session, the client can send encrypted application data in its very first flight, before the handshake completes — genuinely zero round trips before real data. The risk: that first flight isn't protected against replay, so an attacker positioned on the network path can capture and resend it, and the server may process it a second time. The mitigation is restricting 0-RTT to idempotent requests only.
**Follow-up trap:** *"A team wants 0-RTT for a login endpoint 'because it's just reading a session, not writing.'"* — Push back: login endpoints typically have side effects (rate-limit counters, audit logs, sometimes token issuance) even if they look read-only, so "idempotent" needs to be verified as a property of the actual server-side handler, not assumed from the HTTP verb.

### Q11 — You run `openssl s_client -connect host:443 -servername host` and see `Verify return code: 21 (unable to verify the first certificate)`. Diagnose it.
**Answer:** Code 21 specifically means the server didn't send a complete chain — likely missing the intermediate certificate(s) needed to walk up to a root the client trusts. Fix: confirm the server is configured to serve the full chain file (leaf + intermediates), not just the leaf.
**Follow-up trap:** *"The cert works fine in Chrome but fails in this openssl call and in your Python service. Why the discrepancy?"* — Browsers often cache and reconstruct missing intermediates from prior connections or built-in AIA (Authority Information Access) chasing; a bare `openssl s_client` or most language HTTP libraries do not, and neither does most production code, so this is exactly the gap that causes "works in browser, fails in service" incidents.

### Q12 — Why does `-servername` matter when using `openssl s_client` against a multi-tenant server?
**Answer:** It's what populates the SNI extension in the ClientHello; without it, a server hosting multiple certificates on one IP has no signal for which cert to present and typically falls back to a default (often the first-configured) vhost's certificate — producing a hostname/cert mismatch that looks like a server misconfiguration but is actually a testing mistake.
**Follow-up trap:** *"You add `-servername` and now get a different, correct cert but a downgrade to TLS 1.2. Why might that happen?"* — The specific SNI-matched virtual host may have a separate, older TLS config (e.g. a legacy backend behind the same load balancer) than the default vhost — worth checking per-hostname config rather than assuming one global TLS policy for the whole terminator.

### Q13 — Design the TLS strategy for a service mesh handling both internal service-to-service calls and public ingress traffic.
**Testing:** applying every mechanism above coherently in one system.
**Answer:** Public ingress: one-way TLS 1.3 terminated at the edge (load balancer/Envoy), certs from ACME with automated rotation, OCSP stapling on, 0-RTT disabled or scoped strictly to idempotent GETs, ECH enabled if the CDN/client stack supports it. Internal service-to-service: mTLS enforced via the mesh, short-lived (hours, not months) per-workload certs issued by SPIFFE/SPIRE, rolled out permissive-then-strict, with a separate root of trust from the public-facing cert chain so a public CA compromise doesn't implicate internal identity.
**Follow-up trap:** *"Why not just use the same public CA and certs for both?"* — Different threat models and rotation cadences: public certs answer to external CA/Browser Forum policy (validity periods, revocation publicly auditable) while internal workload identity benefits from much shorter lifetimes and mesh-controlled issuance that would be impractical (and unnecessary) to expose to a public CA.

### Q14 — A client reports intermittent TLS handshake failures that correlate with deploys. What do you check first?
**Answer:** Whether the deploy rotates certificates and whether that rotation is atomic across the fleet — a classic cause is a rolling deploy where some instances behind the load balancer are serving a new cert/chain and others are still on the old one, and a client that pinned or cached the old chain (or hit a node with a broken intermediate mid-rotation) fails intermittently depending on which backend it lands on.
**Follow-up trap:** *"Rotation was atomic — cert is identical everywhere. What else?"* — Check whether the rotation changed the *signing CA* or intermediate chain itself (not just renewed the same leaf), since clients or proxies that cached/pinned the old intermediate's public key (HPKP-style pinning, or an internal trust store that wasn't updated) will reject an otherwise valid new chain.

---

## Red flags that fail you

- Describing TLS 1.3 as "just TLS 1.2 but faster" with no mechanism for *why*.
- Not knowing static RSA key exchange was removed, or why forward secrecy matters.
- Saying certificate validation only checks the leaf's expiry.
- Confusing CN matching with SAN matching (CN is deprecated).
- Claiming OCSP is inherently a live network call with no mention of stapling.
- Enabling or recommending 0-RTT without mentioning the replay risk.
- Not knowing SNI is sent in plaintext, or why it has to be.
- Treating mTLS as "TLS with more steps" rather than mutual authentication with a real rollout risk.

---

## Cheat card

```
TLS 1.3 HANDSHAKE (1-RTT common case):
  ClientHello(key_share guess, SNI plaintext, ALPN, groups)
  → ServerHello(key_share) [keys derived here] → {EE, CertReq?, Cert, CertVerify, Finished}
  → client {Cert?, CertVerify?, Finished} (? = mTLS only) → app data
  Wrong key_share guess → HelloRetryRequest → back to 2 RTTs for that connection

TLS 1.2 vs 1.3: 1.2 = 2 RTT (negotiate, then exchange). 1.3 removes: static RSA
  key exchange (no more non-forward-secret sessions), renegotiation (→ KeyUpdate),
  compression, and cuts cipher suites from dozens to 5 (all AEAD).

CERT CHAIN: leaf→intermediate→root(trust store, never sent). Verify signatures
  up the chain + validity dates on EVERY cert + SAN hostname match (CN deprecated)
  + revocation. Classic bug: expired INTERMEDIATE, leaf/root both fine.

REVOCATION: OCSP = live call to CA (latency + privacy leak + soft-fail risk).
  OCSP STAPLING = server pre-fetches signed response, client verifies locally.

SNI: hostname sent PLAINTEXT in ClientHello (needed pre-decryption for vhost
  cert selection) → metadata leak. ECH = encrypts real SNI via DNS-fetched key.
  Not universal yet (mid-2026).

ALPN: protocol list in ClientHello → server picks h2/http1.1 inside the
  handshake itself. No cleartext Upgrade: dance needed over TLS.

mTLS: server sends CertificateRequest, client proves identity too. Zero-trust
  mesh default (SPIFFE/SPIRE short-lived certs). Rollout: PERMISSIVE → STRICT,
  never straight to STRICT.

RESUMPTION: session ID (old, server-side state) → session ticket/PSK (server
  encrypts state INTO the ticket, no server storage). PSK alone = not forward
  secret; PSK+(EC)DHE = forward secret resumption.

0-RTT: data in client's FIRST flight, before handshake completes. REPLAYABLE
  by network attacker → idempotent requests ONLY, or disable it.

DEBUG: openssl s_client -connect host:443 -servername host
  read: Certificate chain, Verify return code (0=ok, 21=missing intermediate),
  Protocol (TLSv1.3?), Cipher. Add -alpn h2 to test ALPN.
```

## Sources

- RFC 8446 (TLS 1.3) — IETF datatracker, accessed 2026-07-26
- RFC 8996 (Deprecating TLS 1.0/1.1) — IETF datatracker, accessed 2026-07-26
- RFC 6066 (TLS Extensions incl. SNI) — IETF datatracker, accessed 2026-07-26
- RFC 7301 (ALPN) — IETF datatracker, accessed 2026-07-26
- [What Application Developers Need To Know About TLS Early Data (0-RTT) — Trail of Bits](https://blog.trailofbits.com/2019/03/25/what-application-developers-need-to-know-about-tls-early-data-0rtt/) — accessed 2026-07-26
- [The danger of TLS Zero RTT — Hussein Nasser](https://medium.com/@hnasr/the-danger-of-0-rtt-a815d2b99ac6) — accessed 2026-07-26
- [Zero trust, mTLS, and the service mesh explained — Buoyant.io](https://www.buoyant.io/blog/zero-trust-mtls-and-the-service-mesh-explained) — accessed 2026-07-26
- [Cloudflare Software Engineer Interview Guide 2026](https://dataford.io/interview-guides/cloudflare/software-engineer) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
