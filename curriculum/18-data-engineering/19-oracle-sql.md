# Oracle SQL Dialect: ROWNUM vs FETCH, NVL, Sequences, Recursive CTEs, Window Functions

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2h · **Prereqs:** T17-postgres or any SQL module · **Updated:** 2026-09-04
> **Module id:** `T18-oracle-sql` · **Tags:** sql

## The 30-second version

Oracle SQL is ANSI SQL with a dialect's worth of load-bearing anachronisms, and interviews at Oracle-shop banks, insurers, healthcare, and enterprises probe exactly those: `ROWNUM` versus `FETCH FIRST` for row-limiting (with the subquery-wrapping rule the classic Top-N question hinges on), `NVL`/`NVL2`/`DECODE` (the pre-COALESCE, pre-CASE generation of null-handling and conditional logic), sequences and the (12c+) identity columns before `GENERATED` standards caught up, `SYSDATE`/`DUAL` as the scratch-pad idiom, hierarchical `CONNECT BY` versus modern recursive CTEs, and the NULLS-sorting and empty-string-equals-NULL quirks that silently change answers. The interview-relevant divide is between candidates who know ANSI SQL and can adapt, and candidates who can explain WHY `WHERE ROWNUM <= 5` after an `ORDER BY` in the same query level returns the wrong five rows. A pass sounds like "wrap the ordered query in a subquery, filter ROWNUM outside"; a fail sounds like "ROWNUM limits rows, same as LIMIT."

## Why this gets asked

Because Oracle still runs the ledger systems of banks, insurers, telcos, and healthcare — jobs at those shops list "Oracle SQL" specifically, and their interviews test the dialect's sharp edges rather than generic SQL fluency. The questions are a deliberately cheap filter: anyone who has actually written production Oracle SQL has bled on `ROWNUM`-with-ORDER-BY (silent wrong answer), on `'' = NULL` (a predicate that matches nothing), and on NULL sort ordering flipping between ASC and DESC — and can tell the story. A candidate who has only used Postgres/MySQL writes `LIMIT` on muscle memory, which is fine, but then misses the follow-up about what happens to NULLs under ORDER BY in Oracle and the interview quietly categorizes them as "knows SQL, not Oracle." The honest self-assessment: this module is the 20% of dialect knowledge that surfaces in 80% of Oracle SQL screens.

---

## Lineage

**What came before.** Oracle V2 shipped in 1979 — pre-ANSI SQL, pre-standard — and its dialect decisions fossilized into the enterprise estate: `DUAL` (the one-row scratch table, created 1979-era for `SELECT 1+1 FROM DUAL`-style expressions), `ROWNUM` (the pre-`LIMIT` pseudo-column for row-limiting, 1980s), `DECODE` (Oracle's pre-`CASE` conditional function), `NVL` (pre-`COALESCE`), `SYSDATE` (pre-`CURRENT_TIMESTAMP`), `CONNECT BY` (recursive hierarchical queries, decades before recursive CTEs entered the standard in SQL:1999 and Oracle added `WITH RECURSIVE` in 11.2). Sequences (`CREATE SEQUENCE`, 1980s) were Oracle's answer to auto-increment because Oracle didn't add identity columns until 12c (2013) — `seq.NEXTVAL` in inserts is still everywhere.

**Where it stands now.** Modern Oracle (12c/19c/23ai) straddles both generations: it HAS the modern forms — `FETCH FIRST n ROWS ONLY`, identity columns, `COALESCE`, `CASE`, recursive CTEs, JSON/JSON-relational duality (23ai), even `LIMIT`-style syntax tolerance in some tooling — but the estate runs on the legacy idioms, so both must be known and, crucially, TRANSLATED between. 19c is the current long-support release running most production estates (premier support through 2027+); 23ai (2024) is the convergence push — vector search, `SELECT ... FROM DUAL` no longer required for many expression contexts, ANSI-default behaviors creeping in. The live interview reality: production Oracle shops ask the legacy forms and expect you to know the modern equivalents; new-build shops ask the reverse.

**Where it's heading.** Three directions. First, convergence (23ai keeps absorbing ANSI conveniences — the dialect gap narrows from the Oracle side). Second, the PL/SQL-and-database-as-app-server estate is slowly losing greenfield work to Postgres/cloud warehouses, so Oracle SQL skills consolidate into the maintenance/modernization niche — where they remain extremely well-paid precisely because fewer new engineers learn them. Third, within the Oracle world, autonomous/cloud (ADB, Exadata) shifts interview emphasis from DBA-ish tuning toward SQL correctness and APEX/duality-backed app development. Flagged as direction: this is a consolidation track, not a growth track — learn it for the estate it serves.

---

## Mental model

```
              ANSI SQL core (joins, GROUP BY, windows, CTEs)
                              │
   ┌──────────────┬───────────┴┴──────────┬───────────────┐
   ▼              ▼                        ▼               ▼
 row-limiting   null/conditional        identity/         dialect quirks
 ROWNUM (old)   NVL, NVL2, DECODE       sequences,       '' IS NULL
 FETCH (12c+)   COALESCE, CASE          identity (12c+)  NULLS FIRST/LAST
   │            SYSDATE/DUAL            MERGE upsert     date format masks
   └─ Top-N: ORDER BY in subquery,      (vs ON CONFLICT) implicit conversions
      ROWNUM filter OUTSIDE                            case-sensitivity
```

The two sentences that unlock everything: **`ROWNUM` is assigned BEFORE `ORDER BY` executes** (so a Top-N needs the sort in an inner query, the ROWNUM filter in an outer one — this one fact generates most Oracle interview questions), and **Oracle treats the empty string as NULL** (`'' IS NULL` is TRUE — no other major database does this, and it silently breaks `WHERE col <> ''`-style predicates imported from elsewhere).

---

## How it actually works

### 1. Row-limiting: the ROWNUM mechanics

`ROWNUM` is a pseudo-column assigned to rows as they enter the result set, BEFORE sorting, before the outer WHERE sees them past the count. Consequences the canon tests: `WHERE ROWNUM = 2` returns nothing (a row can only be row 2 if row 1 was already returned — equality beyond 1 is unsatisfiable); `WHERE ROWNUM <= 5` without ORDER BY is five arbitrary rows, "no guaranteed order" — five random rows, not the top five; and the classic: `SELECT ... ORDER BY salary DESC WHERE ROWNUM <= 5` — ROWNUM is applied to the pre-sort intermediate, so you get five arbitrary rows THEN sorted — the wrong five. The correct pre-12c pattern: `SELECT * FROM (SELECT ... ORDER BY salary DESC) WHERE ROWNUM <= 5`. The 12c+ form is `ORDER BY salary DESC FETCH FIRST 5 ROWS ONLY`, which sorts first by definition. `FETCH` also brings `WITH TIES` (include equal-ranked boundary rows) and `OFFSET n ROWS FETCH NEXT m ROWS ONLY` for pagination — the three-argument forms interviewers ask you to contrast: ROWNUM cannot do WITH TIES or clean offset pagination (the offset pattern needs two nested ROWNUM filters, `RN > 5 AND RN <= 10`, and even then ordering requires a third nesting level).

### 2. Null-handling and the conditional generation

`NVL(expr, value)` — substitute if null; `NVL2(expr, val_if_not_null, val_if_null)` — the two-branch form; `DECODE(expr, s1, r1, s2, r2, ..., default)` — Oracle's pre-CASE chained equality switch. All three predate `COALESCE`/`CASE` (which Oracle also supports, and which you should prefer in new code — COALESCE evaluates lazily per-argument, DECODE evaluates fully). The interview trap is the interplay with Oracle's empty-string-as-NULL: `NVL(email, 'no email')` fires for `''` too — imported MySQL data with empty strings behaves unexpectedly NULL. Sort behavior completes the picture: NULLS are treated as HIGHER than any value by default — ASC puts NULLs last, DESC puts NULLs first — and `ORDER BY x ASC NULLS FIRST / NULLS LAST` overrides per-clause. The classic question: "Oracle shows NULLs at the top of my descending salary report — fix it" → `NULLS LAST`.

### 3. Sequences, identity, and MERGE

Pre-12c auto-increment: `CREATE SEQUENCE emp_seq START WITH 100 INCREMENT BY 1;` then `INSERT INTO employees (emp_id, ...) VALUES (emp_seq.NEXTVAL, ...)`. Gaps are normal and guaranteed (rollback loses numbers, cache loses numbers on restart) — "my sequence skipped values" is a beginner question, not a bug; cache sizing (`CACHE n`) is the performance answer, `CYCLE`/`NOCYCLE` bounds the range. 12c+ identity: `emp_id NUMBER GENERATED ALWAYS AS IDENTITY` — the modern form, but sequences remain everywhere in existing schemas. Upsert: `MERGE INTO t USING s ON (join) WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...` — Oracle's native upsert since 9i, decades before Postgres added `ON CONFLICT`; Oracle has NO `ON CONFLICT` — a candidate answering with Postgres syntax in an Oracle screen has just announced their actual stack.

### 4. Hierarchical queries: CONNECT BY vs recursive CTE

`CONNECT BY` — Oracle's recursive traversal since the 1980s: `SELECT emp, manager_id FROM employees START WITH manager_id IS NULL CONNECT BY PRIOR emp_id = manager_id` — walks parent→child with automatic join; `LEVEL` pseudo-column gives depth, `SYS_CONNECT_BY_PATH` builds the materialized path, `ORDER SIBLINGS BY` sorts within subtrees. Oracle also supports standard recursive CTEs (11.2+) — `WITH sub_hierarchy AS (...)` with the anchor/recursive-UNION structure, portable to Postgres and everything else. The interview wants the tradeoff: CONNECT BY is terser and depth-native (LEVEL is free); recursive CTE is portable, composable (multiple CTEs in one WITH, joins against other tables), and the direction new code should go. Cycle protection: `NOCYCLE` + `CONNECT_BY_ISCYCLE` for dirty data.

### 5. The everyday quirks that screens probe

`DUAL` — the one-row one-column dummy table that expressions select from (`SELECT SYSDATE FROM DUAL`, `SELECT 7*6 FROM DUAL`) — historically mandatory because Oracle required a FROM clause; still the idiom, though modern Oracle tolerates bare `SELECT SYSDATE` in some contexts. `SYSDATE` (server date+time, second precision) vs `CURRENT_DATE`/`CURRENT_TIMESTAMP` (session-timezone-aware, ANSI) vs `SYSTIMESTAMP` (fractional seconds) — "SYSDATE vs CURRENT_DATE" is a real screen question: SYSDATE is server-TZ, CURRENT_DATE is session-TZ — an app with users in multiple timezones gets different answers and the bug is timezone-shaped. Date math: Oracle DATE always carries time (a `TRUNC(date)` habit is how "between Jan 1 and Jan 31" queries stop dropping Jan-31-evening rows); `MONTHS_BETWEEN`, `ADD_MONTHS`, `LAST_DAY`, `NEXT_DAY` are the date canon; `TO_DATE`/`TO_CHAR` with format masks (`'DD-MON-YYYY'`) — no `STR_TO_DATE`. Case sensitivity: unquoted identifiers are uppercased (`employees` = `EMPLOYEES`); quoted mixed-case identifiers are a lock-in trap. Window functions are fully ANSI (`RANK() OVER (PARTITION BY dept ORDER BY sal DESC)`, `ROW_NUMBER`, `DENSE_RANK`, running `SUM(... ) OVER (ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`) — one of the few places the dialect is boring.

---

## Practical exercise

Build the classic Top-N three ways against one employees table and make the failure observable: (1) `SELECT name, salary FROM employees WHERE ROWNUM <= 5 ORDER BY salary DESC` — note it returns five arbitrary rows sorted, and which five changes between runs without a stable seed order; (2) the subquery wrap — `SELECT * FROM (SELECT name, salary FROM employees ORDER BY salary DESC) WHERE ROWNUM <= 5` — correct top-5; (3) `FETCH FIRST 5 ROWS ONLY` and then `FETCH FIRST 5 ROWS WITH TIES` after inserting a salary tie at the boundary — observe WITH TIES returns six. Then the null gauntlet: insert a row with `email = ''`, test `WHERE email IS NULL` (matches — the empty string IS NULL), `NVL(email, 'none')`, and ORDER BY email DESC (NULLs surface first — fix with NULLS LAST). Then hierarchy two ways: CONNECT BY with `LEVEL` and `SYS_CONNECT_BY_PATH` for an org chart, and the same tree as a recursive CTE, side by side — read both, then rewrite a CONNECT BY query you find in a legacy schema (any public Oracle sample schema — HR) as the CTE version. The exercise's point: every failure mode here is silent — no error is raised anywhere — which is exactly why interviews probe them.

---

## How it's done in production

Production Oracle SQL is written against schemas with history, and the conventions reflect it: `NVL`/`DECODE` still dominate legacy PL/SQL codebases even where `COALESCE`/`CASE` is technically available — new work uses the ANSI forms, but reading fluency in DECODE is mandatory for maintenance interviews. Sequences with cache are the auto-increment standard everywhere pre-12c (gap-tolerance is a stated design assumption, and "fixing" gaps by rebuilding the sequence is a known anti-pattern — gap-free numbers are an accounting requirement, and those use table-level serialized counters or `ORDER` sequences, never cached sequences). MERGE is the ETL upsert workhorse for warehouse loads (deterministic keys, `WHEN MATCHED THEN UPDATE`/`DELETE` chains). Timezone-aware production code avoids SYSDATE for anything user-facing (session TZ vs server TZ) and uses `SYSTIMESTAMP AT TIME ZONE 'UTC'` discipline; the "DATE carries time" trap is institutionally solved by the `TRUNC` habit and functional indexes on `TRUNC(date_col)` for range-scan performance. Performance culture: query-folding into the CBO era — window functions for Top-N (Oracle's optimizer recognizes `ROW_NUMBER() <= n` patterns since 12c and can short-circuit) and `FETCH FIRST` mapping to the same plan as the ROWNUM-subquery idiom; the old bind-variable/`V$SQL` tuning toolkit belongs to the DBA track, but knowing that the plan for ROWNUM-wrap and FETCH is identical (verify with EXPLAIN PLAN) is the modern tuning answer interviewers accept.

---

## Tradeoffs

**ROWNUM-wrap vs FETCH FIRST.** FETCH FIRST is cleaner, sorts-then-limits by construction, and handles WITH TIES and OFFSET; ROWNUM-wrap works on every Oracle version ever shipped (real estates still run 11g — extended support ended, extended-extended support persists, the schemas remain). Production answer: FETCH FIRST for new code, ROWNUM-wrap fluency for everything written before 2013 — and in interviews, volunteer both unprompted; it signals you know the estate's age distribution.

**NVL vs COALESCE, DECODE vs CASE.** COALESCE is ANSI, short-circuits per-argument, takes heterogeneous types; NVL evaluates both arguments always (a subtle cost with expensive expressions), is Oracle-only. CASE is ANSI, composable in ORDER BY/aggregate logic; DECODE is terser for pure equality chains, handles NULL=NULL as a match (a genuine semantic difference: `DECODE(NULL, NULL, 'match')` matches, `NULL = NULL` doesn't), but evaluates all branches. New code: ANSI. Maintenance: both fluently. The NULL=NULL DECODE behavior is a legitimate reason to keep DECODE in rare cases — worth saying in an interview, it's a depth signal.

**CONNECT BY vs recursive CTE.** CONNECT BY: terse, LEVEL for free, purpose-built for trees, zero portability. Recursive CTE: portable, composable, more verbose for simple trees, requires generating depth manually. Production cut: new hierarchical work gets the CTE (portability to reporting layers and other engines); dense production org-hierarchy code keeps CONNECT BY because it works and rewriting trees risks regressions. Interview answer: name both, write both, prefer the CTE.

**Sequences vs identity columns.** Identity (12c+) is the modern answer — invisible to the app, no NEXTVAL bookkeeping; sequences remain because they're explicit (the app can pre-fetch NEXTVAL for round-trip-free batch inserts, and multiple tables can share one sequence — identity columns are per-table). Shared-sequence and pre-fetch are real reasons sequences persist; say so.

**Oracle dialect depth vs ANSI-portable habits.** The career tradeoff this module embodies: deep dialect knowledge pays in the legacy-estate niche (banks/insurers — high rates, less competition) but is non-transferable; ANSI habits transfer everywhere but read as junior in an Oracle shop. The production answer is bilingualism: write ANSI where it's available, read the legacy idiom fluently, and always know which one a given codebase is speaking.

---

## Interview questions

**Q1 — Write a Top-5-salaries query. Now explain why the version you didn't write is wrong.**
- **Strong:** Writes the subquery-wrap or FETCH FIRST immediately, unprompted; then explains the ROWNUM failure mechanically: ROWNUM is assigned as rows enter the pre-sort result set, so `WHERE ROWNUM <= 5 ORDER BY salary DESC` limits first and sorts after — five arbitrary rows, presented sorted, and the wrong five at that.
- **Weak:** Writes `LIMIT 5` (announces their actual stack), or defends the flat ROWNUM form.
- **Follow-up trap:** *"Why does `WHERE ROWNUM = 2` return nothing?"* ROWNUM is assigned incrementally as rows satisfy earlier predicates — row 2 can't be considered until row 1 is returned, so equality-to-2 is never satisfiable; only `<= n` and `= 1` work.

**Q2 — NVL vs COALESCE?**
- **Strong:** Both substitute-for-null; COALESCE is ANSI and evaluates arguments lazily (stops at the first non-null), NVL evaluates both eagerly and is Oracle-only; plus the practical detail that in Oracle, `NVL('', x)` fires because empty string IS NULL.
- **Weak:** "They're the same, NVL is Oracle's."
- **Follow-up trap:** *"When does NVL's eager evaluation actually cost you?"* Expensive second arguments — function calls, scalar subqueries — evaluated even when the first is non-null; a real production cost, not trivia.

**Q3 — What does Oracle do with empty strings?**
- **Strong:** `''` is treated as NULL — `'' IS NULL` is TRUE, `'' IS NOT NULL` is FALSE; consequences: predicates like `WHERE col <> ''` match nothing, imported MySQL/CSV data with empty strings behaves as NULL, `LENGTH('')` is NULL not 0.
- **Weak:** "Empty string is a value" — the ANSI-standard answer, which in Oracle is factually wrong.
- **Follow-up trap:** *"How do you find rows where a text column is genuinely blank-but-not-null?"* You can't distinguish them — there is no blank-but-not-null in Oracle VARCHAR2; the honest answer IS the point, and a candidate who invents a workaround is guessing.

**Q4 — NULL ordering: your DESC salary report shows NULL salaries first. Fix it and explain.**
- **Strong:** `ORDER BY salary DESC NULLS LAST` — Oracle treats NULL as higher than any value by default, so DESC puts NULLs first, ASC puts them last; `NULLS FIRST/LAST` overrides per-clause.
- **Weak:** "Filter out the nulls first" — changes the answer set, not the ordering; a WHERE-side fix to an ORDER-BY question.
- **Follow-up trap:** *"How do you get the same result in a report that must run on Oracle AND Postgres?"* Portable pattern: `ORDER BY (CASE WHEN salary IS NULL THEN 1 ELSE 0 END) DESC, salary DESC` — knowing NULLS FIRST/LAST is Oracle/Postgres-specific syntax while the CASE pattern ports is the depth answer.

**Q5 — Sequences: why are there gaps in my IDs? Is that a bug?**
- **Strong:** Not a bug by construction: rollback discards sequence numbers (they're not transactional), cache discards on shutdown; gaps are guaranteed unless you accept serialization costs — `NOCACHE` or ORDER sequences, both throughput-crippling. Gap-free numbering is an accounting/requirement problem that sequences explicitly don't solve — use a serialized counter table in the rare cases it's needed.
- **Weak:** Proposes rebuilding or resetting the sequence.
- **Follow-up trap:** *"The business needs gapless invoice numbers."* Serialized counter table (or DBMS_TRANSACTION-driven assignment) with the throughput cost named — the answer shows they know sequences are the wrong tool for that specific requirement.

**Q6 — MERGE: write an upsert of staging into target.**
- **Strong:** `MERGE INTO target t USING staging s ON (t.id = s.id) WHEN MATCHED THEN UPDATE SET ... WHEN NOT MATCHED THEN INSERT ...` — knows the MATCHED/NOT-MATCHED structure, and notes Oracle has no `ON CONFLICT` so MERGE is the only native upsert.
- **Weak:** `INSERT ... ON CONFLICT` — Postgres syntax in an Oracle interview; or cursor-based row-by-row upsert ("slow-by-slow" PL/SQL, the classic anti-pattern).
- **Follow-up trap:** *"MERGE throws ORA-30926 (unable to get a stable set of rows) — why?"* Multiple staging rows matching one target row — the deterministic-key requirement of MERGE; the fix is deduplicating staging, and knowing that error code by symptom is an experience signal.

**Q7 — CONNECT BY vs recursive CTE for an org chart — which and why?**
- **Strong:** Writes either on request: `START WITH manager IS NULL CONNECT BY PRIOR emp_id = manager_id` with LEVEL, or the anchor-UNION CTE. Prefers the CTE for new code (portable, composable); keeps CONNECT BY for terse trees and where LEVEL/SYS_CONNECT_BY_PATH come free. Mentions NOCYCLE for dirty data.
- **Weak:** Only knows one form, or calls CONNECT BY deprecated (it isn't).
- **Follow-up trap:** *"Your tree has a cycle from bad data. What happens in each form?"* CONNECT BY: ORA-01436 unless NOYCLE; recursive CTE: infinite recursion unless depth-capped — the difference tells you if they've run either against real data.

**Q8 — SYSDATE vs CURRENT_DATE — a user in Tokyo and a user in London run your report; what differs?**
- **Strong:** SYSDATE is server-timezone, CURRENT_DATE is session-timezone — both users see the same SYSDATE, different CURRENT_DATEs (same instant if CURRENT_TIMESTAMP with matching TZ settings, but calendar dates differ); the bug class is day-boundary logic (was it "today"?) shifting by session TZ; the fix is storing UTC instants (TIMESTAMP WITH TIME ZONE) and deriving local dates at the edge.
- **Weak:** "They're the same thing" or "CURRENT_DATE is the ANSI name."
- **Follow-up trap:** *"Your WHERE date_col BETWEEN SYSDATE-1 AND SYSDATE misses rows from last night. Why?"* DATE carries time: SYSDATE is now-with-time, so the range's start excludes yesterday-evening rows; the TRUNC pattern (or explicit date bounds) is the fix — the single most common Oracle date bug.

**Q9 — What's DUAL and why does it exist?**
- **Strong:** One-row dummy table, created for expression evaluation because Oracle's SELECT required FROM; the idiom persists (`SELECT SYSDATE FROM DUAL`, sequence probing, computed literals) even though modern Oracle tolerates FROM-less selects in some contexts; also the classic optimization fact: Oracle special-cases DUAL internally.
- **Weak:** "It's like a table with one row" with no why.
- **Follow-up trap:** *"Why not SELECT 1+1 FROM employees?"* Returns one row per employee-row — DUAL's one-row-ness is the whole point; the answer tests whether the FROM-clause requirement is actually understood.

**Q10 — Write a running-total and a rank-partitioned top-N per department.**
- **Strong:** ANSI windows, fluent: `SUM(salary) OVER (PARTITION BY dept ORDER BY hire_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)` and `RANK() OVER (PARTITION BY dept ORDER BY salary DESC)` in a subquery filtered `WHERE rnk <= 3` — and notes the 12c optimizer short-circuits ROW_NUMBER Top-N.
- **Weak:** Correlated subqueries per department (works, slow, pre-window-function era) or a cursor loop.
- **Follow-up trap:** *"RANK vs DENSE_RANK vs ROW_NUMBER on ties?"* RANK skips (1,1,3), DENSE_RANK doesn't (1,1,2), ROW_NUMBER is unique (1,2,3) — and which one "top 3" actually wants is the requirement question.

---

## Red flags

- **`LIMIT` in an Oracle interview** — muscle memory announcing the wrong stack; recoverable if immediately self-corrected to the ROWNUM/FETCH discussion, disqualifying if defended.
- **Doesn't know `'' IS NULL` in Oracle** — the dialect's single most distinctive fact; its absence means the dialect hasn't been used.
- **Proposes resetting a sequence to "fix" gaps** — gaps are by design; the fix reveals a mental model of sequences as counters, which they aren't.
- **Cursor-based row-by-row ETL as a first answer** — "slow-by-slow" PL/SQL; set-based MERGE exists precisely for this.
- **No NULLS FIRST/LAST reflex** — the default NULL-high behavior silently flips reports; not knowing it means never having debugged an Oracle report.
- **Calls CONNECT BY deprecated** — it isn't; the bilingual answer (write CTE, read CONNECT BY) is what production wants.

## Cheat card

- **ROWNUM assigned BEFORE ORDER BY** → Top-N = sort in subquery, ROWNUM outside; `ROWNUM = 2` returns nothing; **FETCH FIRST 5 ROWS [WITH TIES]** (12c+) sorts first.
- **`'' IS NULL` in Oracle** — `<> ''` matches nothing; NVL fires on empty strings.
- **NULLs sort HIGH by default** — ASC: nulls last, DESC: nulls first → `NULLS LAST` to fix reports.
- **NVL(eager, Oracle) vs COALESCE(lazy, ANSI)**; **DECODE**: NULL=NULL matches, all branches evaluate; **CASE/COALESCE for new code**.
- **Sequences: gaps by design** (rollback, cache); gapless = serialized counter table, never a sequence. **12c identity** = modern form.
- **MERGE = the upsert** (no ON CONFLICT); **ORA-30926** = non-deterministic join keys in staging.
- **CONNECT BY** (tree, LEVEL free) vs **recursive CTE** (portable, composable); NOCYCLE for dirty data.
- **SYSDATE = server TZ, CURRENT_DATE = session TZ**; **DATE always carries time → TRUNC habit** for day-boundary ranges.
- **DUAL** = one-row expression scratchpad; **TO_DATE/TO_CHAR masks**, no STR_TO_DATE.
- **Windows are ANSI-clean**: `RANK/DENSE_RANK/ROW_NUMBER`, running SUM with `UNBOUNDED PRECEDING`; 12c short-circuits ROW_NUMBER Top-N.

## Sources

- Dialect canon (ROWNUM mechanics, FETCH/WITH TIES/OFFSET, NVL/NVL2/DECODE, sequences, MERGE, CONNECT BY, DUAL/SYSDATE, NULL sorting, empty-string-as-NULL): the corpus's top Oracle cluster (×93 crowd-weight, "Oracle SQL Complete Notes Part 2", OCR-verified full slide deck, mining/posts/DbqES_miV6-/), accessed 2026-09-04, cross-checked against Oracle Database SQL Language Reference (19c/23ai) documentation.
- Version timing (FETCH FIRST in 12c/2013, recursive CTE in 11.2, identity in 12c, 23ai convergence): Oracle release documentation and support timelines.
- ORA-30926, sequence gap semantics, SYSDATE session-TZ behavior: Oracle documentation plus long-standing practitioner consensus — the error-code/behavior pairing flagged as practitioner-sourced where not tutorialized officially.

## Changelog

- 2026-09-04: First version, built from the mined Oracle notes deck as the spine, extended with the empty-string/NULL, timezone, and production-MERGE layers the deck touches but doesn't complete. Standard profile.
