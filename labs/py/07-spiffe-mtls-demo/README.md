# Lab 07: SPIFFE Workload Identity + mTLS Authorization

**Track:** T30 Auth & Application Security · **Time:** 2.5h · **XP:** 50
**Module:** `T30-sso-federation`

**You will build:** a SPIFFE-style workload identity layer — SPIFFE id parsing, trust bundles with federation, path-prefix authorization, and a two-direction mTLS handshake simulation — all pure logic, no network and no real TLS.

**You will be able to answer:** *"How does SPIFFE workload identity replace long-lived service certs, and what exactly does each direction of an mTLS handshake validate?"*

## Setup

```bash
cd labs/py/07-spiffe-mtls-demo
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`SpiffeID.parse("spiffe://trust-domain/path")`** → object with `.trust_domain` and `.path`. Raise `ValueError` on malformed ids: missing `spiffe://` scheme, empty trust domain. A root id (`spiffe://example.org`, no path) is legal — `.path` is `""`; a non-root path **retains its leading slash** (`"/backend/payments"`). Equality/inequality is on the **full id string**: two separately-parsed identical ids are equal; anything else is not.
2. **`Workload(id, service)`** — a named service carrying a SPIFFE id (`.id`, `.service`).
3. **`TrustBundle(trust_domain, federates_with=...)`** — the keys one side trusts, abstracted to its trust domain plus a federation list. `validate(id)` → `True` iff the id belongs to **this** trust domain (locals only — federation never leaks into `validate`). `federates_with` is a set of foreign trust domains this bundle also trusts — **empty by default: foreign domains are denied until explicitly listed**. `trusts(id)` → local **or** federated.
4. **`AuthorizationPolicy(trust_domain, expected_id_prefix, allowed_prefixes)`**:
   - `match_source(workload_id, expected_id_prefix)` → workload's id path startswith the prefix.
   - `match_resource(path, allowed_prefixes)` → resource path startswith any allowed prefix.
   - `authorize(workload, resource)` → `True` iff: workload's trust domain == the policy's trust domain **AND** source prefix matches **AND** resource prefix matches.
   - `authorize_cross(workload, resource, local_bundle, federated_bundle)` — federation-aware: a **foreign** trust domain passes only if it is listed in `local_bundle.federates_with` **AND** the workload's id actually validates against `federated_bundle`. Local workloads go through `local_bundle` as usual. Prefix rules apply to foreigners too — federation grants *trust*, not blanket access.
5. **`handshake(client_workload, server_workload, client_bundle, server_bundle)`** → dict — **both directions validated**: the client must validate the server's id against a bundle it trusts (federation counts) and vice versa. One failed direction kills the whole handshake. Returns:

   ```python
   {"established": bool,        # True only if BOTH directions trust
    "reason": str,              # why it failed / "mutual trust established"
    "client_saw": "<SAN the client saw on the server's cert>",
    "server_saw": "<SAN the server saw on the client's cert>"}
   ```

   The SANs (SPIFFE ids) are recorded **even when the handshake fails**.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Segment-aware matching** — make prefix matching segment-aware so `/backend/pay` does NOT authorize `/backend/payments` (the classic prefix bug). *(Interview: "why is string prefix matching on resource paths dangerous?")*
2. **SAN pinning** — add `expected_server_id` to the client: a valid chain is not enough, the *exact* SAN must match (defense against a compromised workload inside your own domain). *(Interview: "certificate validation vs identity pinning — what's the difference?")*
3. **Expiry** — SVIDs are short-lived. Add `expires_at` plus an injectable `Clock` and reject expired ids at handshake time. *(Interview: "what does SVID rotation buy you over a 1-year service cert?")*
4. **JWT-SVID** — SPIFFE ids can also travel in JWTs (audience-bound). Sketch a `JwtSvid` with `aud` checking and write down when you'd pick it over X.509-SVID. *(Interview: "X.509-SVID vs JWT-SVID — when and why?")*
