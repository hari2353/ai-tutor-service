# Power BI & Tableau: Power Query, Star Schema, DAX vs LOD, RLS, Dashboards That Answer Why

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.5h · **Prereqs:** T18-data-modeling-e2e recommended · **Updated:** 2026-09-04
> **Module id:** `T18-bi-tooling` · **Tags:** bi,critical

## The 30-second version

Power BI and Tableau are the two BI tools a data-analyst interview will make you defend, and they fail differently: Power BI is a modeling tool with a visualization layer on top (the skill is DAX and filter context — get the star schema right or every measure lies), Tableau is a visualization tool with a modeling layer underneath (the skill is Level of Detail expressions and understanding that the viz IS the query). The shared foundation is what most candidates lack: neither tool is "making charts" — both are thin clients over a semantic model whose shape (facts, dimensions, grain, relationships) determines what can be computed at all. A pass sounds like "before choosing a chart I'd fix the model — that metric needs a fact table at daily grain, not the current monthly rollup"; a fail sounds like a tour of favorite chart types. The honest positioning: Power BI owns Microsoft-shop enterprise reporting (fabric, security groups, RLS tied to AD); Tableau owns analyst-exploration cultures and is the historical standard where visualization craft is the job title.

## Why this gets asked

Because "Power BI" appears on a large fraction of analyst resumes and interviews for those roles run a fixed canon: Power BI Desktop vs Service, Import vs DirectQuery, calculated column vs measure, star schema, CALCULATE/filter context, RLS — plus the Tableau version (dimensions vs measures, discrete vs continuous, LOD expressions, table calculations) where the shop uses it. Interviewers ask because the canon separates people who've built models from people who've made dashboards: a candidate who explains that a measure is evaluated in filter context, while a calculated column is computed at refresh, has maintained a semantic model; one who says "a measure is a formula" has only watched one. The tool-specific questions are also the cheapest depth-probe an interviewer owns — no environment, no code, five minutes from "what's a slicer" to "why is my YoY number wrong."

---

## Lineage: past → present → future

**What came before.** BI was born as the OLAP cube generation: Cognos, BusinessObjects, MicroStrategy, and Microsoft's own SSAS Multidimensional in the late 1990s–2000s put "dimensions, measures, hierarchies, calculated members" into pre-built cubes that clients queried via MDX. The model-first discipline this module teaches IS that generation's idea — Tableau (Stanford spinout, 2003, VizQL patent: drag-and-drop that generates queries) and Power BI (Microsoft, 2015, built on SSAS Tabular's xVelocity/VertiPaq engine and DAX, which itself descends from Power Pivot's 2009 Excel add-in) democratized it to desktops. Both inherited the semantic-model layer: Tableau as extracts and data-source modeling, Power BI as the full tabular model with DAX outright.

**Where it stands now.** Power BI is the volume leader inside Microsoft estates — bundled into Fabric (2023+) with OneLake, Direct Lake mode (2023: query lakehouse Delta files nearly directly, bypassing the old Import/DirectQuery dichotomy), workspace/deployment-pipeline governance, and price pressure that makes it the default for Excel-Shop reporting. Tableau (acquired by Salesforce 2019 for $15.7B) holds the visualization-craft and analyst-exploration segment: VizQL is still its core, Hyper extracts are still its engine, Einstein/CRM analytics is its Salesforce-side play. The live disagreement is where the model should live: Microsoft keeps consolidating it in the service (shared semantic models, XMLA endpoint, one model many reports — Power BI is becoming the semantic layer for Excel and Fabric too), while Tableau's audience resists central models in favor of connected workbooks and exploration. Also real: both now face the notebook-tier (Evidence, Hex, plus dbt-semantic-layer + BI-as-thin-client architectures) arguing dashboards should be generated, not hand-crafted.

**Where it's heading.** Three directions with different confidence. First, semantic-layer consolidation — high confidence: one governed model, many consumers (Power BI's shared datasets + Microsoft's Fabric "OneLake" direction; dbt's semantic layer on the other side). Second, LLM-driven dashboarding — medium confidence: "describe a chart, get a viz" is shipping in both products' Copilot/Tableau Pulse forms; the analyst skill shifts toward auditing and model stewardship. Third, Direct Lake-style zero-copy (query the lakehouse in place) — real and expanding; it erodes the Extract/Import tier's reason to exist, though governance limits keep classic Import dominant for now. Speculative flag: "BI tool choice" mattering less as semantic layers standardize — the DAX/LOD skills stay, the tool lock-in loosens.

---

## Mental model

```
   source data
        │
        ▼
  ┌───────────────────────────────────────────┐
  │  THE SEMANTIC MODEL (where BI actually lives)   │
  │  Power Query: ETL      Tableau: data source/    │
  │   (clean/shape)           join/extract (Hyper)  │
  │  Model: star schema     Extract: .hyper file     │
  │   facts ←→ dimensions   live vs extract conn     │
  │   DAX measures          LOD & table calcs       │
  └──────────────┬────────────────────────────┘
                 │  (the viz layer is THIN)
        ┌────────┴─────────┐
        ▼                  ▼
   Power BI:           Tableau:
   report pages,       sheets/dashboards,
   visuals+filters,    VizQL drag-drop,
   slicers,            marks card, every
   dashboards (SVC)    viz IS a query
```

The two sentences that unlock everything: **in Power BI the model is the product and the report is a lens on it** (which is why "fix the model" is always the right first move, and why one dataset can serve ten reports), and **in Tableau the visualization is the query** (drag pills onto shelves and VizQL generates SQL — which is why the Marks card and pill colors — blue discrete vs green continuous — encode computation, not decoration).

---

## How it actually works

### 1. The shared spine: star schema and grain

Both tools want a central fact table (numeric events at a declared grain — sales rows at day×store×product) surrounded by dimensions (date, product, store), related by keys, one-to-many from dimension to fact. This is `T18-data-modeling-e2e`'s warehouse discipline applied at desktop scale, and it's the module most candidates skip: the interview question "what's wrong with my YoY?" is nine times in ten "your date dimension isn't marked as a date table / isn't related to the fact, so time intelligence has nothing to compute against." Declare the grain before building anything: a facts table at monthly grain cannot answer a question asked weekly, no matter how clever the measure — the model caps the questions, and the viz can't fix that.

### 2. Power BI: the DAX evaluation model

Three concepts, in dependency order: (1) **Calculated column vs measure** — a column is row-context, computed once at refresh, stored in the model, usable as a slicer/filter; a measure is filter-context, computed at query time, not stored, for aggregations. "Sales Amount" as a column is a modeling error; "Total Sales := SUM(Sales[Amount])" as a measure is the pattern. (2) **Filter context** — every visual's slices, filters, and slicers combine into the filter context in which each measure-cell evaluates; DAX is not Excel formulas, it's context-modified aggregation. (3) **CALCULATE, the only function that matters** — `CALCULATE(expr, filter1, filter2...)` is context-transition: it modifies filter context before evaluating the expression. `Sales YoY % := DIVIDE([Total Sales] - CALCULATE([Total Sales], SAMEPERIODYEARAGO('Date'[Date])), CALCULATE([Total Sales], SAMEPERIODYEARAGO('Date'[Date])))` is the canonical composition — CALCULATE + time-intelligence over a properly marked date table. The function canon: aggregations (`SUM`, `COUNT`, `DISTINCTCOUNT`, `DIVIDE` — the safe-division habit), context (`CALCULATE`, `FILTER`, `ALL`, `REMOVEFILTERS`, `SELECTEDVALUE`, `SWITCH`), time (YTD/MTD/QTD, SAMEPERIODYEARAGO — all requiring the marked calendar).

### 3. Power BI: storage, service, security

Import mode loads data into VertiPaq, the in-memory columnar engine (fast, offline-capable, size-bound by capacity); DirectQuery skips storage and translates DAX to source SQL on every visual (real-time, source-performance-bound; use for security-sensitive or huge datasets, expect slower interactions and a long list of DAX limitations); Direct Lake (Fabric) reads Delta files near-directly — the newest answer to the dichotomy. Power BI Desktop builds reports; the Service (app.powerbi.com) publishes, shares, and schedules refresh; dashboards-with-pin-tiles exist ONLY in Service; gateways bridge on-prem sources to cloud refresh; workspaces + apps handle distribution; deployment pipelines promote dev→test→prod. Security: **Row-Level Security (RLS)** — roles with DAX filters ("East reps see `Region = "East"`") evaluated at query time per-user via `[Username]`/`USERPRINCIPALNAME()`; effective access is the intersection of role memberships. **Object-Level Security (OLS)** restricts tables/columns from even appearing in the model. Sensitivity labels extend Microsoft Purview classification.

### 4. Tableau: the VizQL query model

Every Tableau view is a query: pills on Rows/Columns define the SELECT's dimensions/aggregations; the Marks card (color/size/shape/detail) refines grouping; filters restrict. **Dimension vs measure** (blue pill: categorical, slices; green pill: continuous, axes) and **discrete vs continuous** (blue header vs green axis) are the four-quadrant mental model that trips Tableau newcomers constantly. **Extracts (.hyper)** are Tableau's columnar store — local, fast, refreshable; live connections push every viz as SQL to the source; the performance/governance tradeoff mirrors Import/DirectQuery. **Table calculations** (running total, percent-of-total, rank) compute over the query RESULT — hence "compute using" (direction/partition) being the hard part; they're fragile to layout changes. **LOD expressions** are Tableau's answer to filter-context control: `{FIXED [region] : SUM(sales)}` computes region-sums regardless of what's on the view; `{INCLUDE}`/`{EXCLUDE}` add/remove dimensions from the view's own level. LOD vs table-calc is the Tableau interview's calculated-column-vs-measure: LOD is a model-tier computation independent of layout; table calcs are view-tier and layout-bound. Parameters (user inputs), sets (conditional subsets — "Top 10 by Sales"), actions (filter/highlight/URL cross-view linking), and dashboard objects compose the interactive layer.

### 5. The comparison the interview wants

Import vs DirectQuery ↔ live vs extract. Calculated column vs measure ↔ (Tableau's rough analog: a data-source column vs an LOD expression). RLS ↔ Tableau's user filters (a column like `[Username]` matched to a user-mapping table — genuinely clunkier than RLS, worth knowing as the honest tradeoff). Star schema ↔ identical in both. Power BI's service tier (workspaces, apps, pipelines, capacity) ↔ Tableau Server/Salesfield's sites/projects/extract schedules — the governance story, where Microsoft shops feel the bundle-price gravity. DAX is a deeper modeling language than LOD (filter-context is a real semantic-model concept; LOD is a query-computation concept) — that's the honest one-line answer to "which is harder."

---

## Practical exercise

Build the same small warehouse twice from one CSV set (sales facts + product + store dims + a hand-rolled calendar table): (1) In Power BI: load via Power Query (remove duplicates, split a combined key, change types), model the star (mark the calendar as date table!), write the measure ladder — `Total Sales`, `Sales LY := CALCULATE([Total Sales], SAMEPERIODYEARAGO('Date'[Date]))`, `YoY % := DIVIDE([Total Sales]-[Sales LY],[Sales LY])`, `Sales excl West := CALCULATE([Total Sales], REMOVEFILTERS(Store), NOT Store[Region]="West")` — then assemble a report with slicer-driven cross-filtering and publish to Service (or a workspace if licensed), define an RLS role and test with "View as." (2) In Tableau: connect, build the same date-hierarchy views, then force the three calc types apart: a table calculation (running SUM of profit, compute-using table-across), a `FIXED` LOD (region-level sales ignoring a state filter — watch it DISAGREE with the table calc, which is the lesson), and a parameter (metric switcher feeding SWITCH-like calculated fields). The exercise's payoff is the disagreement you can then explain: LOD ignores view filters, table calcs follow them, DAX CALCULATE is explicit about it — three tools, one concept, and you've now touched all three.

---

## How it's done in production

Mature BI estates treat the model as the asset and the reports as replaceable lenses: shared semantic models in the Service (one certified dataset, dozens of reports on top, XMLA/ALM tooling for deployment), certification tiers (personal → promoted → certified datasets), and a steward who owns the measure library — because a measure that means different things in two reports is an organizational incident, not a styling issue. Refresh architecture is scheduled gateways for on-prem, incremental refresh policies for big facts (partition windows, not full reloads), and query-folding awareness in Power Query (steps that fold to source SQL run on the database; steps that break folding — merges with complex transforms, index columns — run in memory; production pipelines check folding early because a "refresh" that downloads the warehouse is an outage in waiting). Performance discipline: Import-first as the default (VertiPaq is fast and cheap), DirectQuery only for real-time/security/huge-table reasons with its DAX limitations known up front; measures over calculated columns as the storage-and-correctness habit; aggregations tables (user-defined agg over big facts queried by smaller ones) for the size tier between. Tableau estates: Hyper extracts on refresh schedules, prep flows for ETL, site/project governance on Server/Cloud. The cross-cutting production failure mode is orphaned workbooks: the same 12-line DAX/LOD logic copy-pasted into forty files with no shared layer — both tools' governance features exist to prevent exactly this, and both get adopted only after the first major "two dashboards, two different YoY numbers" incident.

---

## Tradeoffs

**Import vs DirectQuery (live vs extract).** Import/extract: fast interactions, offline, refresh-latency bounded by schedule, capacity-bound storage; DirectQuery/live: real-time, no data duplication (a security/compliance feature in its own right), slower per interaction, dialect-limited DAX/table-calc pushdown. The honest default: Import/extract first; move only for real-time needs, very large facts, or row-security-at-source policies — and validate at design time, because retrofitting DirectQuery onto an Import-built model rewrites half the measures.

**Measure vs calculated column.** Storage vs flexibility: measures are computed per-query under filter context (no model bloat, correct under every slice) but can't be used as slicers/filters; columns are computed once, stored, filterable — but bloat the model and freeze logic at refresh grain. Discipline: column only for row-level attributes that must slice; measure for everything aggregate. The anti-pattern is columns-for-everything (model bloat + wrong-under-slicing).

**DAX/LOD complexity vs doing it upstream.** A monster CALCULATE can always be replaced by a warehouse-computed column or a dbt model — and should be when the same logic serves non-BI consumers. The production cut: business-specific-at-query-time (year-to-date across whatever slicing) belongs in the semantic layer; business-stable-always-the-same (net revenue definition) belongs upstream, with the semantic layer referencing it.

**Power BI vs Tableau (the honest one).** Microsoft estate, governed enterprise reporting, price bundling → Power BI is close to a default; visualization-craft culture, analyst-led exploration, Salesforce adjacency, embedded analytics → Tableau. Neither is "easier": DAX's filter context is a deeper concept than anything Tableau demands; Tableau's viz-craft (dual-axis, table-calc direction, LOD-vs-view interplay) is deeper than anything Power BI's format pane demands. Interviews reward naming the estate as the decider, not the tool as the religion.

**Dashboards vs self-serve exploration.** A dashboard answers known questions cheaply and rots as they drift; exploration culture (Tableau's origin, Power BI's "analyze in Excel" periphery) answers unknown questions at analyst cost. Mature shops fund both and treat dashboard sprawl (500 unpinned reports, nobody knows which is truth) as the governance failure it is — the fix is certified models + a much smaller dashboard portfolio, not more tooling.

---

## Interview questions

**Q1 — Calculated column vs measure?**
- **Strong:** Context (row vs filter), storage (stored vs computed-per-query), use (slicer vs aggregation), and the error direction: "Sales as a column is a modeling mistake; 'Total Sales' as a measure is the pattern; columns only for row-level attributes that must slice."
- **Weak:** "A measure is a formula like SUM; a column is added to the table."
- **Follow-up trap:** *"Why is my measure showing the same number in every row of this table visual?"* Filter context isn't differentiating rows — the measure aggregates over the whole context because no dimension from the fact is on the view; the fix is the model/grain, not a new formula.

**Q2 — Explain CALCULATE and filter context.**
- **Strong:** Filter context = the set of filters a cell inherits from slicers/axes/cross-highlighting; CALCULATE is the only function that MODIFIES it (evaluate expr under new filters, with ALL/REMOVEFILTERS clearing, filter args replacing). Walks YoY as the canonical example with SAMEPERIODYEARAGO + a marked date table.
- **Weak:** "It's like SUMIF" — the Excel mental model, wrong in both direction and mechanism.
- **Follow-up trap:** *"What's context transition?"* Row context (inside an iterator like SUMX) converting to equivalent filter context when CALCULATE evaluates — the deep-end question, and naming SUMX + row-context is the pass.

**Q3 — Import vs DirectQuery — when do you actually choose DirectQuery?**
- **Strong:** Default Import for speed/simplicity; DirectQuery for (a) real-time freshness requirements, (b) very large facts that don't fit capacity, (c) security policies requiring data never leaves source — and names the costs: slower interactions, DAX limitations, source-load responsibility. Mentions Direct Lake as the modern middle if Fabric is in play.
- **Weak:** "DirectQuery is newer/better."
- **Follow-up trap:** *"Your DirectQuery report hammers the source database — fix it."* Wants: aggregation awareness (reduce queries per visual), limiting cross-highlighting, or moving the big fact to Import/aggregations — the answer shows they know every visual is a source query.

**Q4 — What's a star schema and why does BI care?**
- **Strong:** Central fact at declared grain, surrounding dimensions, one-to-many from dims; why: filter propagation from dimensions through facts (both tools are built to fan filters across exactly this shape), time intelligence needs the date dim, and flattened single-table models produce ambiguous many-to-many relationships and wrong totals. "The model caps the questions — no viz fixes a monthly-grain fact asked weekly."
- **Weak:** "It's a best practice for performance" with no mechanism.
- **Follow-up trap:** *"Two facts tables, no common dimension, both filtered by the same slicer — what happens?"* Filters propagate through relationships; unrelated tables need a bridge/shared dim or the slicer silently filters only one — the "why is my other visual not responding" production question.

**Q5 — What is RLS? How do you test it?**
- **Strong:** Roles defined in the model with DAX row filters, evaluated per-user at query time (USERPRINCIPALNAME-based dynamic roles), effective access = intersection of roles; testing = "View as role" in Desktop + Service's test-as-user, plus the classic pitfall: RLS applies to report READERS, not workspace members (admins/members bypass RLS — a governance trap people deploy wrong).
- **Weak:** "It restricts data per user" with no mechanism or test method.
- **Follow-up trap:** *"A user sees rows they shouldn't. Walk your debugging."* Role membership vs workspace membership first (the bypass), then role DAX (the predicate logic — table-level vs column-level filters), then dynamic-role username matching — shows they've operated it, not read it.

**Q6 — Tableau: dimensions vs measures, discrete vs continuous.**
- **Strong:** Dimensions slice (blue, categorical headers); measures aggregate (green, numeric axes); discrete = headers/partitions, continuous = axes/ranges; the four-quadrant (discrete dimension, continuous dimension like a date axis, discrete measure like MIN(State) as a header, continuous measure) with an example of each — and that dragging a date pill between blue/green changes the whole viz type.
- **Weak:** "Dimensions are text, measures are numbers."
- **Follow-up trap:** *"Why did my year pill turn green and the chart become a line?"* Date defaulted to continuous/exact — the pill-color system encodes the computation; this question is the fastest possible probe of actual Tableau hours.

**Q7 — Tableau: LOD expressions vs table calculations.**
- **Strong:** LOD computes at a declared grain independent of the view — `{FIXED [region]: SUM(sales)}` stays region-level under a state filter; INCLUDE adds to view level, EXCLUDE removes. Table calcs run over the query result — partition/direction ("compute using"), layout-dependent, fragile to rearrangement. The tell: "need it stable when filters change → LOD; need it about the displayed rows → table calc."
- **Weak:** "Both are advanced calculations."
- **Follow-up trap:** *"Your FIXED sum disagrees with the sheet's percent-of-total. Why is that correct behavior?"* The region total ignores the state filter while percent-of-total respects it — explaining the disagreement cleanly is the whole point of the question.

**Q8 — Your dashboard is slow. Diagnose.**
- **Strong:** A triage order, not a shrug: (1) model tier — too many visuals per page (each is a query), calculated-column bloat, many-to-many relationship fan-out; (2) storage tier — DirectQuery per-visual source roundtrips vs Import; extract vs live in Tableau; (3) DAX/LOD tier — FILTER over whole tables where boolean filters would fold, iterator chains, the measure used as a slicer; (4) reduce queries — fewer cross-highlighting paths, aggregations tables. Names ONE concrete example from having done it.
- **Weak:** "I'd optimize the DAX" with no order.
- **Follow-up trap:** *"You cut visuals 40→12 and it's still slow — next?"* Moves to model/storage tier — the follow-up exists to catch candidates whose whole performance model is "fewer charts."

**Q9 — Power BI Service vs Desktop — what lives where?**
- **Strong:** Desktop: build (PQ transforms, model, DAX, report). Service: publish/share/refresh/govern — workspaces, apps, dashboards-with-pinned-tiles (Service-only object), gateways, RLS role testing as user, deployment pipelines dev→test→prod. Knows the crossover quirks (dashboards don't exist in Desktop; some visuals/properties differ between the two).
- **Weak:** "Service is the web version."
- **Follow-up trap:** *"Can we build a dashboard in Desktop?"* No — pinning from reports to a Service dashboard is the mechanism; the "no" separates hands-on users from tutorial-followers.

**Q10 — Why do two dashboards show different YoY for the same month?**
- **Strong:** A debugging order grounded in the semantic layer: different datasets (not shared model — the most common org failure), different calendars (fiscal vs calendar year), different date-table marking (unmarked calendar → broken SAMEPERIODYEARAGO), different filter context (one respects a region filter the other hard-filters), duplicate unshared measures drift. And the governance answer: certified shared model + measure library prevents recurrence.
- **Weak:** "Probably a bug" or immediately re-writing the measure.
- **Follow-up trap:** *"The numbers were identical last month. What changed?"* The refresh/data-side (a late-arriving fact restated the month) vs the model-side (someone republished with a new calendar) distinction — restatement awareness is the senior answer.

---

## Red flags

- **A dashboard tour with no model talk** — chart vocabulary without the semantic layer means dashboards were watched, not built.
- **"A measure is a formula"** — the single most diagnostic wrong answer in Power BI screens; it fails the entire evaluation-model follow-up chain.
- **CALCULATE unknown or described as "like SUMIF"** — the Excel mental model; DAX has not been used in anger.
- **No RLS/workspace-permissions distinction** — deployed security wrong in the past or will.
- **Tableau pill colors treated as decoration** — the four-quadrant model is Tableau's computation grammar; not knowing it means no real Tableau hours.
- **LOD vs table-calc interplay unknown** — the "advanced Tableau" line exists exactly here; candidates who can't name when a FIXED disagrees with a percent-of-total stop at intermediate.
- **Sectarian tool answer ("just use Python/Power BI/Tableau")** — BI estates are decided by the surrounding stack; ideology reads as never having operated in one.

## Cheat card

- **Model first, viz second.** Fact at declared grain + dims; the model caps the questions.
- **Measure = filter-context, computed per query, not stored** (aggregations); **column = row-context, stored, refresh-time** (must-slice attributes only).
- **CALCULATE = the context modifier**; `ALL`/`REMOVEFILTERS` clear, filter args replace; time intelligence requires a **marked date table**.
- **Import default; DirectQuery for real-time/huge/security**; Direct Lake is the Fabric-era middle. **Query folding** = PQ steps that run on the source; check it early.
- **RLS:** role DAX filters at query time, roles intersect, workspace admins/members BYPASS — test with View-As.
- **Tableau:** blue = discrete/headers, green = continuous/axes; **LOD (`FIXED`/`INCLUDE`/`EXCLUDE`) ignores/adjusts view filters**; **table calcs** run on the result (partition + direction), layout-fragile.
- **{FIXED [region]: SUM(sales)}** disagrees with percent-of-total under a state filter — correctly.
- **Slow dashboard triage:** visuals-per-page → model bloat → storage mode → DAX/LOD patterns — in that order.
- **Two dashboards, two numbers:** different datasets or different calendars first; certified shared models fix the class, not the instance.
- **Estate decides tool:** Microsoft/Fabric gravity → Power BI; viz-craft/Salesforce → Tableau. DAX is the deeper modeling language; LOD is the deeper viz-craft tool.

## Sources

- Power BI canon (Desktop/Service split, Import vs DirectQuery, calculated column vs measure, star schema, DAX CALCULATE and time intelligence, RLS/OLS, workspaces/apps/gateways): the corpus's two highest-signal Power BI clusters (×77 fresher roadmap, ×68 interview set, OCR-verified, mining/posts/DcxlnCoCZ7W/, mining/posts/DbsbO6kiUYZ/), accessed 2026-09-04, cross-checked against Microsoft Learn's Power BI documentation (data modeling, DAX, row-level security) and practitioner-observed behaviors.
- Tableau canon (dimensions/measures, discrete/continuous, LOD expressions, table calculations, extracts vs live, sets/parameters/actions): the ×26 Tableau cluster (mining/posts/DcxscO4CQmv/) plus Tableau's official LOD-expression and extract documentation.
- VertiPaq/Direct Lake and Fabric direction: Microsoft Fabric documentation and 2023–2024 release notes.
- The governance-failure patterns (two-dashboards-two-numbers, orphaned workbook sprawl, workspace-members-bypass-RLS): practitioner inference from the corpus plus community post-mortem patterns — flagged as secondary where not officially documented.

## Changelog

- 2026-09-04: First version, merging the mined Power BI and Tableau clusters into one module with the shared semantic-model spine. Standard profile.
