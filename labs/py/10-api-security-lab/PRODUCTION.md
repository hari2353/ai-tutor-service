# Production notes — API security

## What you'd actually use

| Control | Production answer |
|---|---|
| BOLA/IDOR | an authorization *layer*, not scattered ifs: policy objects (Casbin, OPA, Cedar), or framework-level object scoping (`query.filter(user_id=caller)`) |
| Mass assignment | Pydantic/FastAPI request models with explicit fields (you cannot bind what the schema doesn't declare); Marshmallow `load_only`/`dump_only` for the nasty cases |
| Rate limiting | reverse-proxy first (nginx `limit_req`, Envoy local rate limit, AWS WAF), then app-level (slowapi, limits) for per-user keys |
| Enumeration | uniform errors, constant-ish timing (real defense: Argon2id on BOTH paths), plus per-IP+per-account rate limits |

## What the real systems add over yours

- **BOLA is #1 on the OWASP API Top 10 (API1:2023) for a reason**: authentication is solved by middleware; *object-level* authorization must be expressed per data access, and one missed filter is account takeover. Real fixes are structural: the ORM query itself carries the owner scope (`where(account_id = ctx.account)`) so forgetting the check is a code-review flag, not a prayer.
- **UUIDs don't fix BOLA** — they slow walking, not authorization. The test to have in CI: identity B requests A's object by ID and must get 403/404 *by ID*. (404 vs 403 is its own debate — many teams return 404 to avoid existence oracles, which is your enumeration lesson again.)
- **Mass assignment's real-world shape** is exactly your vulnerable method: `user.update(request.json)` behind a PATCH. Ruby's `mass_assignment` CVEs (2012, GitHub's 2013 `user.update` privilege escalation via `user_id` in the body) are the canonical incidents. Frameworks grew `strong parameters` / allowlists *from these incidents*.
- **Rate limiter nuances you'll be asked about**: distributed buckets need a shared store (Redis) — local buckets are per-pod and multiply your effective limit by pod count; buckets should be keyed per-endpoint-per-actor (a login brute force and a search flood are different budgets); return `429` + `Retry-After`, not 403; skip the `X-RateLimit` headers on internal endpoints if they aid recon.
- **Enumeration timing** — message uniformity is table stakes; the *timing* gap (early return for missing users) is measurable and scripted by attackers. The real fix is running the same password hash (Argon2id against a dummy record) on both paths — your `login_fixed` placeholder is that, in miniature.

## Failure table

| Symptom | Cause | Fix |
|---|---|---|
| Cross-tenant data read (the front-page breach) | object fetched by ID, owner never checked | scope every query by the caller's tenancy; CI authorization tests |
| Client sets is_admin via PATCH | whole-body binding | schema allowlists (Pydantic models); reject-unknown-fields in dev |
| Rate limiter trivially bypassed | key on connection IP behind a proxy / no per-user key | trust `X-Forwarded-For` only from your LB; key per user AND per IP; buckets in Redis |
| Limits drift at scale | per-pod local buckets | centralized limiter or per-pod limit / pod-count |
| Username dump via login errors | differential messages or timing | uniform error + identical work on both paths |
| 429s during a flash crowd | one global bucket | per-key buckets + allowlist for health checks |

## Cost & latency

Authorization checks are in-memory compares (~ns) unless you outsource to a policy engine (OPA ~1ms per decision — put it in-process with a sidecar bundle, not a network hop, or the latency line-item becomes the argument against security). Rate limiting costs one Redis `EVALSHA` per request (~0.3ms) — or do it at the proxy where it's free.

## The 3 questions an interviewer asks after you describe this

1. *"You check ownership on GET /orders/{id}. What about the list endpoint?"* — the subtle one: `GET /orders` scoped to *someone else's filter* leaks too; the object-scope must live in the query, not only the by-ID fetch.
2. *"Mass assignment is fixed by an allowlist — what's the failure mode of allowlists?"* — new model field auto-exposed if the allowlist isn't derived from the schema. Tie allowlists to the request schema (Pydantic), and review the diff when fields are added.
3. *"Your rate limiter is per-key in a dict. What happens at 10 pods and 100k rps?"* — per-pod buckets ⇒ 10× effective limit; move to a shared token bucket in Redis, accept one RTT, or shard by key-hash with sticky routing.
