# curl Mastery: Every Flag That Matters, Debugging APIs From the Terminal

> **Track:** T29 Networking & Protocols · **Time:** 2h · **Prereqs:** T29-http-semantics, T29-tls · **Updated:** 2026-07-26
> **Module id:** `T29-curl-mastery` · **Tags:** tools, critical

## The 30-second version

curl is the fastest way to isolate whether a problem is DNS, TCP, TLS, or the server's application logic, and `-v` plus `-w` are the two flags that answer that split every time: `-v` shows you the handshake and header exchange line by line (`*` connection/TLS info, `>` what you sent, `<` what came back), and `-w` with a timing template breaks one request into `time_namelookup` → `time_connect` → `time_appconnect` → `time_starttransfer` (TTFB) → `time_total`, so a slow request tells you exactly which phase is slow instead of leaving you guessing. Everything else — auth, redirects, multipart uploads, mTLS, retries, and pinning a hostname to an IP with `--resolve` — is about reproducing production requests precisely enough from a terminal that you never have to say "works on my machine" without evidence.

## Why this gets asked

Because it's the fastest signal for "has this person actually operated a production API, or only read about one." Someone who's been paged at 3am for a mysterious latency spike has used `-w` with a timing template to prove it was TLS negotiation, not the database. Someone who's debugged a load balancer routing bug has used `--resolve` to hit one specific backend without touching `/etc/hosts` or DNS. The interviewer is checking for muscle memory under pressure, not flag trivia.

---

## Lineage: past → present → future

**What came before.** Before curl (Daniel Stenberg, 1996-97, originally "httpget"), debugging HTTP from the command line meant telnet-ing to port 80 and typing raw request lines by hand, or writing throwaway scripts per protocol. curl unified dozens of protocols (HTTP, HTTPS, FTP, SCP, and more) behind one flag vocabulary, and its companion library `libcurl` became the transport underneath an enormous share of HTTP clients across languages (PHP's cURL extension, Python's `pycurl`, and countless others use it directly or indirectly).

**Where it stands now.** curl is still the default terminal tool for this even with GUI alternatives like Postman and Insomnia widely used for exploratory API work, because it's scriptable, universally installed, composable with `jq`/`grep`/shell pipelines, and reproducible in a bug report in a way "I clicked around in Postman" isn't. HTTPie exists as a friendlier syntax layer but hasn't displaced curl in ops/on-call contexts, largely because curl is *already there* on every box you'll ever SSH into, and HTTPie often isn't. The live disagreement is really about workflow, not capability: some teams standardize on `.http` files or Postman collections for shareable, versioned request definitions, while others keep a directory of copy-pasteable curl commands in the runbook; both are legitimate, and the senior move is picking one and being consistent rather than arguing curl vs Postman as if it's a technology decision.

**Where it's heading.** curl keeps absorbing modern transport support — HTTP/3 (QUIC) support has been available behind build flags and is increasingly enabled by default in recent distributions, and `--http3` lets you force it for testing. The tool's core interface (flags, `-v`, `-w`) hasn't meaningfully changed in a decade because it doesn't need to; the interesting movement is elsewhere (HTTP/3 negotiation, more mTLS/HSM integration), not in the debugging workflow itself. Treat curl's flag surface as a stable, durable skill rather than something to re-learn each cycle.

---

## Mental model

```
curl -v https://api.example.com/users/42
                          │
        DNS ─────────► TCP connect ─────► TLS handshake ─────► request/response
        │                  │                    │                     │
   time_namelookup    time_connect       time_appconnect       time_starttransfer
                                         (TLS done here)         (TTFB: server's
                                                                  processing time
                                                                  is baked in here)
                                                                          │
                                                                    time_total
```

Read `-v` output as three prefixes: `*` is curl telling you about the connection itself (resolving, connecting, TLS details) — infrastructure info, not wire bytes. `>` is what curl actually put on the wire (your request line and headers) — verify this matches what you intended. `<` is what the server sent back (status line and response headers) — this is ground truth for what the server actually did, which is why `-v` beats trusting client-side library logs that might be lying about what was actually sent.

---

## How it actually works

### `-v` / `-vv`: reading verbose output line by line

```
$ curl -v https://api.example.com/users/42
*   Trying 93.184.216.34:443...
* Connected to api.example.com (93.184.216.34) port 443
* ALPN: curl offers h2,http/1.1
* TLSv1.3 (OUT), TLS handshake, Client hello (1):
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* TLSv1.3 (IN), TLS handshake, Certificate (11):
* TLSv1.3 (IN), TLS handshake, CERT verify (15):
* TLSv1.3 (IN), TLS handshake, Finished (20):
* SSL connection using TLSv1.3 / TLS_AES_128_GCM_SHA256
* ALPN: server accepted h2
* Server certificate:
*  subject: CN=api.example.com
*  start date: Jan  1 00:00:00 2026 GMT
*  expire date: Apr  1 00:00:00 2027 GMT
*  issuer: C=US; O=Let's Encrypt; CN=R3
*  SSL certificate verify ok.
* using HTTP/2
> GET /users/42 HTTP/2
> Host: api.example.com
> user-agent: curl/8.7.1
> accept: */*
>
< HTTP/2 200
< content-type: application/json
< content-length: 87
< 
{"id":42,"name":"..."}
* Connection #0 to host api.example.com left intact
```

Reading this: `*` lines confirm DNS resolved, TCP connected, and exactly which TLS version and cipher were negotiated (`TLSv1.3 / TLS_AES_128_GCM_SHA256`) plus which ALPN protocol won (`h2`) — this is your fastest way to confirm "is this endpoint actually serving HTTP/2" without a packet capture. The certificate block shows the full chain and expiry — a TLS failure shows exactly which cert in the chain failed verification here, which is the #1 use case for `-v` in an on-call TLS incident. `> ` lines are your actual request — if an `Authorization` header you expected isn't listed, your client code isn't setting it, full stop, no further debugging needed on the server side. `<` lines are the server's actual response headers — compare against what your application code claims it received to catch a proxy or middleware silently rewriting something in between.

`-vv` (or `--trace-ascii -`) goes further and dumps the raw bytes of the request/response bodies too, useful when you suspect encoding issues (chunked transfer artifacts, unexpected compression).

### `-w` / `--write-out`: timing breakdown

```
$ cat curl-format.txt
    time_namelookup:  %{time_namelookup}s\n
       time_connect:  %{time_connect}s\n
    time_appconnect:  %{time_appconnect}s\n
   time_pretransfer:  %{time_pretransfer}s\n
  time_starttransfer:  %{time_starttransfer}s\n
                    ----------\n
          time_total:  %{time_total}s\n

$ curl -w "@curl-format.txt" -o /dev/null -s https://api.example.com/users/42
    time_namelookup:  0.012s
       time_connect:  0.045s
    time_appconnect:  0.098s
   time_pretransfer:  0.099s
  time_starttransfer:  0.312s
                    ----------
          time_total:  0.315s
```

Reading the deltas, not the absolutes, is the skill: `time_connect − time_namelookup` = TCP handshake cost (here ~33ms). `time_appconnect − time_connect` = TLS handshake cost (~53ms, consistent with 1-2 RTT). `time_starttransfer − time_appconnect` = **server processing time** — this is the number that tells you it's a backend problem, not a network problem (here ~214ms, the dominant cost — this is your signal to go look at the API's own tracing, not the network). `time_total − time_starttransfer` = time to transfer the body once the server started responding (here ~3ms, body is small). A slow `time_namelookup` alone points at DNS (misconfigured resolver, slow upstream DNS); a slow `time_connect` alone points at network path or a saturated/unreachable host; a slow `time_appconnect` step points at TLS (slow OCSP stapling checks, an overloaded TLS terminator, or a client offering a cipher list the server has to negotiate expensively); a slow `time_starttransfer` with everything before it fast means the server itself is slow — go look at its logs, not the network.

### Headers, auth, methods, bodies

```bash
curl -H "Accept: application/json" -H "X-Request-Id: abc123" https://api.example.com/users

curl -I https://api.example.com/users/42          # HEAD request, headers only

curl -u alice:s3cret https://api.example.com/me                     # Basic auth
curl -H "Authorization: Bearer $TOKEN" https://api.example.com/me   # Bearer token
curl --digest -u alice:s3cret https://api.example.com/me            # Digest auth

curl -X POST -d '{"name":"new"}' -H "Content-Type: application/json" \
     https://api.example.com/users
curl -X PATCH --data-raw '{"name":"renamed"}' -H "Content-Type: application/json" \
     https://api.example.com/users/42
curl -X POST -F "file=@report.pdf" -F "note=quarterly" \
     https://api.example.com/uploads                 # multipart/form-data
curl -T bigfile.bin https://api.example.com/uploads/bigfile.bin      # raw PUT of a file
```

Gotcha worth stating out loud in an interview: `-d`/`--data` defaults `Content-Type` to `application/x-www-form-urlencoded`, not JSON — if you're sending a JSON body you must set `-H "Content-Type: application/json"` explicitly or the server's deserializer will choke on a form-encoded parse of JSON text. `--data-raw` differs from `-d` only in that it won't interpret a leading `@` as "read from this file"; use it when your payload might legitimately start with `@`.

### Redirects and the POST-to-GET gotcha

```bash
curl -L https://api.example.com/old-path              # follow redirects
curl -L --max-redirs 5 https://api.example.com/old-path
curl -L -X POST -d '{"x":1}' https://api.example.com/old-endpoint
```

The gotcha: on a 301/302 redirect, curl (matching browser behavior) converts a `POST` into a `GET` on the redirect target and drops the body, unless the original response was a 307/308 (which explicitly preserve method and body) — or unless you pass `-X POST` explicitly to force curl to keep using POST on the follow-up request regardless of the redirect status code. This trips people up in both directions: expecting a POST body to survive a 302 (it won't, by default), and forcing `-X POST` on a redirect that was *supposed* to become a GET (breaking a legitimate login-then-redirect-to-dashboard flow).

### TLS debugging

```bash
curl -k https://self-signed.example.com               # skip cert verification — DEBUGGING ONLY
curl --cacert ca-bundle.pem https://internal.example.com
curl --cert client.pem --key client-key.pem https://mtls.example.com   # mTLS
curl -v https://api.example.com 2>&1 | grep -E "SSL|TLS|subject|issuer"
```

`-k` disables certificate verification entirely — it's the right tool for confirming "is the app-layer response actually fine once you get past a cert problem," and the wrong tool for anything that runs outside a debugging session on your own machine, because it silences exactly the check that prevents a MITM. Never ship `-k` in a script, cron job, or health check that touches anything beyond localhost. `--cacert` points curl at a specific CA bundle (common for internal CAs not in the system trust store); `--cert`/`--key` present a client certificate for mutual TLS, where the server also verifies the *client's* identity — this is the exact mechanism you're debugging when a service-to-service mTLS handshake fails, and `-v` will show you which side of the chain rejected what.

### Timeouts, cookies, output, retries, resolve

```bash
curl --connect-timeout 3 -m 10 https://api.example.com/slow    # 3s to connect, 10s total ceiling
curl -c cookies.txt -b cookies.txt https://api.example.com/login   # save+send cookies
curl -o response.json -s -S https://api.example.com/users          # silent but show errors
curl -O https://cdn.example.com/artifact.tar.gz                    # save with remote filename
curl --retry 3 --retry-delay 2 https://api.example.com/flaky
curl --resolve api.example.com:443:10.0.0.5 https://api.example.com/health
curl --connect-to api.example.com:443:10.0.0.5:443 https://api.example.com/health
```

`--connect-timeout` bounds only the connection phase (useful for detecting an unreachable host fast without waiting on a slow response); `-m`/`--max-time` bounds the whole request including transfer. `-s` suppresses the progress meter (needed for scripting) but also suppresses error messages — pair it with `-S` to keep error output while still silencing the progress bar. `--retry` retries on transient transport failures and select HTTP response codes; it does not retry on every non-2xx by default, and it backs off between attempts per `--retry-delay` (or exponential backoff without the flag). `--resolve` and `--connect-to` both let you pin a hostname (and optionally port) to a specific IP for exactly one request — `--resolve` overrides DNS resolution for that host, `--connect-to` overrides which host:port the *connection* actually goes to while leaving the `Host` header, SNI, and cert validation checking against the original name. This is the tool for "hit backend #3 of my load balancer directly, without touching `/etc/hosts` or fighting DNS caching," and it's the single most useful flag for debugging a specific-node-only production issue without needing SSH access to that node's config.

---

## Build it from scratch

There's no "build curl from scratch" in the usual sense — the lab here is building the *diagnostic habit*:

1. Given a slow endpoint, produce the `-w` timing breakdown and state which phase is the bottleneck before looking at anything else.
2. Given a TLS handshake failure, use `-v` to identify whether it's a hostname mismatch, an untrusted CA, or an expired cert — the three most common causes, each showing a distinct line in `-v` output (`unable to get local issuer certificate`, `certificate has expired`, `hostname does not match`).
3. Given a suspected LB routing bug (one backend behaving differently), reproduce it with `--resolve` pinned to each backend IP in turn, without needing SSH access to any of them.
4. Reproduce a bug report that only includes a Postman screenshot: convert it to an equivalent curl command (headers, method, body) so it's pasteable into a ticket and re-runnable by anyone.

---

## How it's done in production

Most teams don't hand-type these commands from memory every time; they keep a runbook of parameterized curl commands (often behind a Makefile target or shell alias) per critical endpoint, specifically because reproducibility during an incident matters more than cleverness. `curl -w` is also frequently wrapped into synthetic monitoring (a cron job hitting `-w` timing into a metrics pipeline) as a cheap, dependency-free alternative to a full APM agent for a handful of critical external dependencies.

| Symptom | Cause | Fix |
|---|---|---|
| `curl: (60) SSL certificate problem: unable to get local issuer certificate` | Missing intermediate CA in the trust chain, or client trust store doesn't include a private/internal CA | `--cacert` pointing at the correct bundle; fix server to send the full chain including intermediates |
| `curl: (28) Connection timed out after Xms` on `--connect-timeout` | Host unreachable, firewall dropping SYN, or DNS resolving to a dead IP | Check `--resolve` against a known-good IP to isolate DNS vs network vs host issue |
| POST body silently missing after a redirect | 301/302 converts method to GET and drops body by default | Server should return 307/308 if method+body must be preserved; client can force `-X POST` if intentional |
| `-d` payload rejected with a JSON parse error server-side | Default `Content-Type: application/x-www-form-urlencoded` sent instead of JSON | Explicit `-H "Content-Type: application/json"` |
| Script works interactively but hangs in cron/CI | No `-m`/`--max-time` set; inherited an effectively infinite default | Always set both `--connect-timeout` and `-m` in any scripted/unattended curl call |
| `-k` used in a supposedly "temporary" debugging script that shipped to prod | Cert verification silently disabled; MITM risk with no alert | Never allow `-k` past a local debugging session; lint/grep CI for it in shipped scripts |
| Intermittent 200 vs 500 hitting the "same" endpoint | Load balancer routing to an unhealthy backend node inconsistently | `--resolve`/`--connect-to` to hit each backend IP directly and isolate the bad node |

---

## Tradeoffs & when NOT to use it

- **Don't use curl for anything requiring a persistent session UI, request history browsing, or team-shared collections.** Postman/Insomnia genuinely win there; curl is a point tool, not a workspace.
- **Don't use `-k` or skip cert verification anywhere near production traffic.** If you find yourself wanting to, the actual problem is a broken trust chain that needs fixing, not a flag to suppress the symptom.
- **Don't rely on curl's timing breakdown for anything requiring true concurrency modeling.** It measures one request end-to-end; for connection-pooling behavior, keep-alive reuse across many requests, or concurrent load, use a real load-testing tool (k6, wrk, vegeta) instead.
- **Don't script complex JSON body construction by hand-concatenating strings in shell.** It's an injection and escaping hazard; build the payload with `jq -n` or a real templating step, then pass it to `-d @-` or `--data-raw`.

---

## Interview questions

### Q1 — A GET request is slow. How do you find out why with curl?
**Testing:** whether `-w` timing is muscle memory.
**Answer:** `curl -w "@curl-format.txt" -o /dev/null -s <url>` and read the deltas: `time_connect - time_namelookup` = DNS, `time_appconnect - time_connect` = TLS, `time_starttransfer - time_appconnect` = server processing (the usual culprit), `time_total - time_starttransfer` = body transfer.
**Follow-up trap:** *"It says DNS is slow. Now what?"* — check whether it's resolver latency (try `--resolve` to bypass DNS and hit the known IP directly, confirming the rest of the timing is normal) versus a genuinely slow/misconfigured upstream DNS server, and whether the client is caching resolutions at all.

### Q2 — Walk me through reading `curl -v` output.
**Answer:** `*` lines are connection/TLS metadata from curl itself — DNS resolution, TCP connect, negotiated TLS version/cipher, ALPN result, certificate chain. `>` lines are the literal bytes curl sent — verify your intended headers actually went out. `<` lines are the literal response headers from the server — ground truth for what actually came back, which can catch a proxy silently stripping or rewriting a header in between.
**Follow-up trap:** *"The `Authorization` header you expected isn't in the `>` block. Where's the bug?"* — in the client that built the curl command or the application code that generated it, not the server or the network; `-v` shows what was actually sent, so its absence is definitive, not something to keep debugging server-side.

### Q3 — Why doesn't your POST body survive a redirect?
**Answer:** curl (like browsers) converts a POST to a GET and drops the body on a 301/302 by default, matching long-standing (if debatable) HTTP client convention; only 307/308 explicitly instruct the client to preserve method and body.
**Follow-up trap:** *"How do you force POST through a 302 anyway?"* — pass `-X POST` explicitly, but be deliberate: this overrides the semantic hint the server gave you, and if the server actually intended GET-after-redirect (e.g., post-login-then-dashboard), forcing POST can break the flow or resubmit a form unexpectedly.

### Q4 — Why does your JSON POST fail with a parse error on the server even though the JSON is valid?
**Answer:** `-d`/`--data` defaults to sending `Content-Type: application/x-www-form-urlencoded`; the server's JSON deserializer is trying to parse form-encoded data. Fix: explicit `-H "Content-Type: application/json"`.
**Follow-up trap:** *"What's the difference between `-d` and `--data-raw`?"* — `-d` interprets a leading `@` in the payload as "read from this file"; `--data-raw` sends the literal string even if it starts with `@`. Functionally identical otherwise.

### Q5 — How do you debug a TLS handshake failure?
**Answer:** `curl -v` against the endpoint and read the certificate block: `unable to get local issuer certificate` means a missing intermediate in the chain or an untrusted private CA (fix with `--cacert`); `certificate has expired` is exactly what it says; a hostname mismatch shows as the cert's `subject`/SAN not matching the requested host. All three produce visibly different error text in `-v`, so you don't have to guess.
**Follow-up trap:** *"`-k` makes it work. Is the bug fixed?"* — no, `-k` just stopped checking; you've confirmed the app layer is fine past the handshake, but the underlying trust-chain problem is still there and will still fail for every real client that correctly validates certificates.

### Q6 — Difference between `--connect-timeout` and `-m`/`--max-time`?
**Answer:** `--connect-timeout` bounds only how long to wait for the TCP/TLS connection to establish; `-m` bounds the entire request lifecycle including waiting for the response and transferring the body. A slow-to-connect host is caught by the first; a host that connects instantly but then hangs mid-response is caught only by the second.
**Follow-up trap:** *"You set `-m 5` but the request still hangs 30s. Why?"* — `-m` wasn't actually applied (common when wrapping curl in another tool/library that has its own timeout config overriding or ignoring the CLI flag), or DNS resolution itself hung before either timer started in some older curl/resolver combinations — worth checking `--connect-timeout` is also set, since the two guard different phases.

### Q7 — How do you hit one specific backend behind a load balancer without SSH access to it?
**Answer:** `--resolve api.example.com:443:<backend-ip>` (overrides DNS resolution for that host) or `--connect-to api.example.com:443:<backend-ip>:443` (routes the TCP connection there while keeping the original `Host` header, SNI, and cert validation against the original hostname). Either lets you isolate "is backend #3 specifically misbehaving" without touching `/etc/hosts` or waiting on DNS cache expiry.
**Follow-up trap:** *"What's the actual difference between `--resolve` and `--connect-to`?"* — `--resolve` fully overrides what the hostname resolves to (as if you'd changed DNS); `--connect-to` only redirects the connection target while leaving resolution and all cert/SNI/Host-header behavior tied to the original name — useful when you specifically want the cert validation to still check against the real hostname rather than the IP you're forcing the connection to.

### Q8 — What's wrong with using `-k` in a production health-check script?
**Answer:** It disables certificate verification entirely, silently accepting an expired cert, a wrong hostname, or an active MITM without any error — exactly the failure modes TLS exists to catch. A health check using `-k` will report "healthy" even when the certificate has expired and every real client is failing.
**Follow-up trap:** *"How do you catch that the flag snuck into a shipped script?"* — grep/lint CI for `-k` or `--insecure` in any committed shell script, and treat a match as a build failure, not a warning.

### Q9 — How do you send a file as a multipart upload versus a raw PUT?
**Answer:** `-F "file=@report.pdf"` builds a `multipart/form-data` body (what a browser `<form>` upload sends, supports multiple fields plus the file). `-T bigfile.bin` does a raw PUT of the file's bytes as the entire request body with no multipart framing — the right choice when the API expects the raw file content directly (e.g., an S3-style PUT-to-URL upload).
**Follow-up trap:** *"Your `-F` upload works for a 1KB file but chokes on a 2GB one. Why?"* — likely the server's max body size / multipart buffer limit, or the client library's default in-memory buffering of the multipart body rather than streaming it; curl itself streams from disk with `@filename`, so check the server/proxy limits first, not curl's behavior.

### Q10 — Explain `--retry` — does it retry every failure?
**Answer:** No. It retries on transient transport-level failures (connection refused/reset, timeout) and a defined set of HTTP response codes indicating a possibly-transient server issue, with `--retry-delay` (or exponential backoff by default) between attempts. It does not blindly retry every 4xx/5xx — that would retry a 400 or 404 pointlessly.
**Follow-up trap:** *"Should you always add `--retry` to scripts calling a payment API?"* — no, not without checking idempotency first; retrying a POST that isn't idempotent risks duplicate side effects (double charge). curl's retry doesn't know or care about your endpoint's idempotency semantics — that's your responsibility to reason about before adding the flag.

### Q11 — What does `-I` do and when would you use it over a full GET?
**Answer:** Sends a HEAD request and shows only response headers, no body — useful for checking whether a resource exists, its size (`Content-Length`), caching headers, or last-modified time without downloading potentially large content.
**Follow-up trap:** *"A server returns different headers for HEAD vs GET on the same URL. Is that a bug?"* — it can legitimately happen (some servers compute `Content-Length` only when actually generating the body) but per HTTP semantics HEAD should return headers identical to what GET would return; if they diverge in ways that matter (a different `Content-Type`, a missing `ETag`) that's worth flagging as a genuine server-side inconsistency, not something to shrug off.

### Q12 — Design a curl-based synthetic check for a critical external dependency.
**Testing:** whether you can compose these flags into something operationally real.
**Answer:** `curl -s -o /dev/null -w "%{http_code} %{time_starttransfer} %{time_total}\n" --connect-timeout 3 -m 10 <url>`, run on a schedule, piping the write-out fields into a metrics system, alerting on non-2xx status or `time_starttransfer` exceeding an SLO threshold. Keep `--connect-timeout` tight to fail fast on unreachability distinctly from a slow-but-alive server, and log both status code and timing so an alert immediately tells you whether it's a connectivity or a latency problem.
**Follow-up trap:** *"This runs from one region. What's the blind spot?"* — you only observe network conditions from that one vantage point; a regional network issue or DNS resolver problem specific to another region/AZ won't show up. Multi-region synthetic checks (or accepting this is a coarse first-line check, not a replacement for real APM) closes that gap.

---

## Red flags that fail you

- Not knowing the difference between `time_starttransfer` and `time_total`.
- Suggesting `-k` as a fix rather than a temporary diagnostic step.
- Not knowing `-d` defaults to form-urlencoded, not JSON.
- Adding `--retry` to a non-idempotent write without mentioning idempotency.
- Confusing `-I` (HEAD) with `-i` (include response headers in a normal GET's output).
- Not knowing `--resolve`/`--connect-to` exist when asked how to hit a specific backend.

---

## Cheat card

```
VERBOSE      -v / -vv         * = connection/TLS info · > = sent · < = received
TIMING       -w "@curl-format.txt" -o /dev/null -s <url>
             namelookup -> connect -> appconnect(TLS) -> starttransfer(TTFB) -> total
             big delta before starttransfer = server processing, not network

HEADERS      -H "K: V"  (repeatable) · -I = HEAD only
AUTH         -u user:pass (Basic) · -H "Authorization: Bearer $TOK" · --digest
METHOD/BODY  -X POST -d '{"k":"v"}' -H "Content-Type: application/json"
             (-d alone defaults form-urlencoded, NOT json)
             -F "file=@x.pdf"  multipart   ·   -T file.bin  raw PUT of a file
REDIRECTS    -L  --max-redirs N
             301/302: POST -> GET, body dropped, UNLESS 307/308 (method+body kept)
             force with explicit -X POST if you really mean it

TLS          -k  skip verify — DEBUG ONLY, never in prod/scripts
             --cacert bundle.pem   (custom/internal CA)
             --cert c.pem --key k.pem   (mTLS, client presents its own cert)
TIMEOUTS     --connect-timeout Ns   (connect phase only)
             -m / --max-time Ns    (whole request incl. transfer)
COOKIES      -c file (save)  -b file (send)
OUTPUT       -o file  -O (remote name)  -s (silent)  -S (still show errors)
RETRY        --retry N --retry-delay S   (transient errors + select codes only,
             NOT blanket retry-everything; check idempotency before enabling)
PIN HOST     --resolve host:port:IP        override DNS for one request
             --connect-to host:port:IP:port  redirect connection, keep Host/SNI/cert check
```

## Sources

- [curl(1) man page — everything.curl.dev](https://everything.curl.dev/) — accessed 2026-07-26
- [Timing Details With cURL — Joseph Scott](https://blog.josephscott.org/2011/10/14/timing-details-with-curl/) — accessed 2026-07-26
- [HTTP Transaction Timing with Curl — NetBeez](https://netbeez.net/blog/http-transaction-timing-breakdown-with-curl/) — accessed 2026-07-26
- [What is cURL? A complete guide — IBM Developer](https://developer.ibm.com/articles/what-is-curl-command/) — accessed 2026-07-26
- [A Question of Timing — Cloudflare Blog](https://blog.cloudflare.com/a-question-of-timing/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
