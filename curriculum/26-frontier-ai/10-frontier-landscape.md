# The Frontier Landscape: Labs, Model Families, and Reading a Model Card

> **Track:** T26 Frontier AI · **Time:** 1.5h · **Prereqs:** T26-reasoning-models · **Updated:** 2026-08-23
> **Module id:** `T26-frontier-landscape` · **Tags:** landscape

## The 30-second version

Eight labs effectively define the 2026 frontier — OpenAI (GPT-5.x tiered family), Anthropic (Claude Opus/Sonnet/Haiku tiers), Google DeepMind (Gemini Pro/Flash), xAI (Grok), Meta (post-Llama pivot to closed Muse Spark), DeepSeek (V-series flagship + R-series reasoners, MIT-licensed), Mistral (Europe's dense/MoE/reasoning trio), and Alibaba's Qwen — with model *families* structured as capability tiers (flagship/workhorse/fast) priced from roughly **$1.25 to $50 per million output tokens** and context windows converging around 1M tokens. But knowing the roster is table stakes; the interview-differentiating skill is **reading a model card like an auditor**: which evals are cited versus omitted (disclosure runs the full gamut — one lab discloses 8/8 headline benchmarks, another 0/8), whether contamination is acknowledged with actual decontamination methodology or hand-waved, and what the license really permits — because "open weights" is not open source, community licenses carry user-count thresholds, EU carve-outs, and acceptable-use policies incorporated by reference, and cards quietly shift safety responsibility onto you as the deployer.

## Why this gets asked

Three reasons this module exists at senior level. First, architecture questions assume fluency with the landscape: "how would you choose between model families for X" requires knowing who ships what, how families tier their models, and where the open-weight escape hatches are. Second, procurement and due diligence increasingly land on engineers: when a team adopts a model, someone has to read the model card and license like a contract — spotting that evaluations were run on bf16 checkpoints but you'll deploy quantized ones, that the benchmark suite omits exactly your task category, or that training data includes platform user interactions with privacy implications. Third, it's a judgment probe: candidates who can name every model but can't say *why* disclosure asymmetry matters (vendor-reported scores are marketing until independently confirmed) read as hobbyists. The strongest answers treat the landscape as a fast-moving map plus a stable reading discipline — the map redraws quarterly, the audit method doesn't.

---

## Lineage: past → present → future

**What came before.** Through 2023-2024 the landscape legible story was two-sided: a handful of closed-API frontier labs (OpenAI, Anthropic, Google) versus the open-weights movement led by Meta's Llama line and Mistral, with Chinese labs (DeepSeek, Qwen, Moonshot) rising fast on cost efficiency. Model cards existed as a research-artifact tradition (inherited from the original model-card proposal for ML fairness reporting) but were thin: parameter counts, a handful of benchmark rows, boilerplate safety language. Licensing was already messy — Meta's "Community License" was formally rejected as open source by both OSI and FSF (failing the freedom-to-use-for-any-purpose and non-discrimination criteria, later adding an EU carve-out), while "open weights" became a marketing term doing legal work it couldn't support. Benchmark contamination was known but underweighted: GPT-3's report described 13-gram filtering against benchmarks, GPT-4's raised it to 40-grams and admitted 9 of 34 exams checked had over 20% overlap with training data.

**Where it stands now.** The 2026 landscape has four structural features. (1) **Tiered families everywhere**: each lab ships flagship/workhorse/fast tiers (OpenAI's GPT-5.x Sol/Terra/Luna pattern, Anthropic's Opus/Sonnet/Haiku, Google's Pro/Flash) spanning roughly $1.25-$50 per million output tokens, with reasoning-effort dials layered on top — model choice is now portfolio configuration, not a single pick. (2) **The open/closed line blurred**: Meta pivoted its canonical open-weights Llama line to closed API-first Muse Spark (then partially reopened with an Apache 2.0 mid-size release), while DeepSeek ships genuinely MIT-licensed frontier-class models — so "open" now describes specific licenses, not lab reputations. (3) **Disclosure asymmetry widened**: third-party trackers score labs on how many headline specs/benchmarks are actually disclosed — ranging from full disclosure (one major lab at 8/8) down to essentially zero (another at 0/8, qualitative blog copy only), with conflicting numbers across sources even for shipped flagships. (4) **Governance arrived at deployment time**: export-control suspensions have briefly pulled shipped flagships offline (one Claude-class model suspended ~22 days in mid-2026; another gated pending government safety review), making regulatory state a real availability dimension.

**Where it's heading.** High confidence: continued release-cadence compression (multiple flagships per quarter across labs, tracked by release ledgers rather than memory), continued context growth toward multi-million-token windows, and pricing pressure from efficient open competitors keeping closed-tier margins honest. Medium confidence: consolidation of evaluation around dynamic/private benchmarks (LiveBench-style monthly refreshes, held-out private test sets) as contamination accounting becomes standard procurement diligence; license simplification pressure as buyers learn to reject community-license terms. Contested: whether the open-weight frontier stays within months of closed frontier or falls behind structurally; whether export controls fragment the global model supply chain into regional stacks; whether any lab's "R&D automation flywheel" creates durable lead concentration. For interviews: hold the map loosely, hold the audit method tightly.

---

## Mental model

```
THE 2026 ROSTER (hold lightly — redrew twice this year):

  CLOSED-FIRST            OPEN-WEIGHTS (license matters!)
  ├─ OpenAI   GPT-5.x     ├─ DeepSeek  V-flagship + R-reasoners (MIT)
  │   tiers: Sol/Terra/Luna│─ Qwen      dense + Max tiers (Apache-ish)
  ├─ Anthropic Claude      ├─ Mistral   dense/MoE/reasoning trio
  │   Opus/Sonnet/Haiku    │─ Meta      post-Llama: mixed signals
  ├─ Google   Gemini       └─ Moonshot/Z.ai etc.
  │   Pro / Flash
  └─ xAI      Grok

  EVERY FAMILY SHIPS A TIER LADDER:
    flagship ($$$, hardest work) → workhorse ($$, default) → fast ($, volume)
    × reasoning dial (minimal…high) × context (100K…1M+)

MODEL CARD AUDIT LENS (the stable skill):

  ┌──────────────────────────────────────────────────────────┐
  │ 1. EVALS      cited vs omitted · vendor-run vs independent│
  │               compute tier stated? quantization match?    │
  │ 2. DATA       sources named? contamination statement?     │
  │               decon method (n-gram? none?) · cutoff date  │
  │ 3. LICENSE    OSI-open vs "community" · MAU caps · EU     │
  │               carve-outs · AUP by reference · outputs     │
  │ 4. SAFETY     red-team scope · who owns residual risk?    │
  │               (cards quietly shift it to DEPLOYER)        │
  │ 5. OPERATIONS version pinning · static-model notice ·     │
  │               compute/emissions disclosure                │
  └──────────────────────────────────────────────────────────┘

CONTAMINATION BASELINE (why evals need auditing):
  public benchmarks leak into web-scale crawls →
  MMLU ~29% items contaminated · C-Eval ~46% · multilingual up to ~92%
  n-gram filters miss paraphrase/translation leaks → inflated scores
```

The compression: **the map changes quarterly; the five-lens audit changes never.** Candidates who memorize rosters fail when the roster turns over; candidates who internalize the audit lens survive every rotation.

---

## How it actually works

### The lab-by-lab map, compressed

**Closed-first tier.** *OpenAI* ships the GPT-5.x family in named tiers (flagship "Sol"-class, mid "Terra", fast "Luna") plus realtime/voice lines; historically the widest consumer distribution and an ecosystem gravity that makes its schema conventions industry defaults. *Anthropic* structures Claude into Opus/Sonnet/Haiku capability tiers with long-horizon agentic work as the flagship positioning and the strongest recent disclosure record (full spec/benchmark publication per release); available through first-party API plus Bedrock/Vertex, which matters for enterprise cloud procurement. *Google DeepMind* leverages Gemini Pro/Flash tiers on proprietary TPUs with structural data advantages (search/video/workspace corpora) and dominance claims in image/video generation modalities. *xAI* fields Grok with aggressive compute buildout and social-data firehose integration, shipping fast but with thinner disclosure.

**Open-weight tier.** *DeepSeek* is the economics disruptor: V-series MoE flagships (trillion-parameter-class total, tens-of-billions active per token, ~1M context) under MIT license, plus the R-series reasoning line that reproduced o1-class behavior openly — training-cost disclosures forced a global repricing conversation. *Qwen* (Alibaba) ships the highest-cadence broad catalog (sizes from edge to Max) with permissive licensing, functioning as the default fine-tune base outside the US orbit. *Mistral* (Paris — the only major non-US/non-Chinese lab) splits product lines by architecture: dense Mistral, MoE Mixtral, reasoning Magistral, with modified-MIT-class licenses. *Meta* is the cautionary tale in transition: Llama 1-4 defined the open-weights era under a Community License that was never OSI-approved, and the post-Llama Muse Spark line moved frontier work closed/API-first before partial re-opening gestures (an Apache 2.0 mid-size release) — a live case study in why licenses, not press releases, define openness.

### Reading a model card like an auditor

**Lens 1 — Evals: cited versus omitted.** Start with what's measured and who measured it. Every vendor-reported number is marketing-grade until independently reproduced; third-party indexes exist precisely because disclosure is asymmetric (from one lab disclosing everything down to launch-blog prose with no quantitative claims at all). Then check the measurement *conditions*: compute tier for reasoning models (a high-effort ARC-AGI score tells you little about low-effort serving behavior), sample counts, and — the classic gap — whether reported evaluations ran on the same checkpoint precision you'll deploy (Llama 4's card explicitly states all evaluations ran on bf16 models while offering quantized deployments: the number is real, and it isn't yours). Finally note systematic omission: if a coding-focused model publishes no long-horizon agentic evals, that silence is information.

**Lens 2 — Data and contamination statements.** The card should name data sources at least taxonomically (Llama 4's does: publicly available data, licensed data, and platform user content including Instagram/Facebook posts and Meta AI interactions — with immediate GDPR/CCPA relevance for downstream commercial deployments). The contamination question is sharper: does the card describe decontamination methodology (n-gram filters — and their known weakness to paraphrase/translation leakage), or stay silent? The measured baselines justify skepticism: roughly 29% of MMLU items showed contamination signals (JHU, NAACL 2024), C-Eval around 46%, multilingual benchmarks up to ~92% as translated copies scatter through crawls; Meta's own Llama 2 report conceded 16% MMLU overlap, some items with >80% token match. Consequences are measurable too: clean-mirror rebuilds drop scores materially (a Mistral GSM8K mirror fell ~13 points), and inference-time decontamination strips ~23% of MMLU inflation. Practical rule: treat any benchmark number without a contamination statement as an upper bound, and weight dynamic/private benchmarks (LiveBench monthly refreshes, private held-out sets where GPT-4o scored 73.4% versus higher public-MMLU numbers) more heavily in decisions.

**Lens 3 — Licenses: the trap taxonomy.** "Open weights" answers a logistics question (can I download it?) and dodges the legal one (what am I permitted?). The traps, in frequency order: (1) *Community/custom licenses masquerading as open* — Meta's Llama licenses fail OSI's open-source definition (use-for-any-purpose, non-discrimination), formalized by OSI and FSF analyses; MIT and Apache 2.0 are the genuine articles. (2) *Scale thresholds* — the Llama license's 700M-monthly-active-user carve-out means the license terms differ depending on who you are; enterprises above the line need separate negotiated terms. (3) *Jurisdictional carve-outs* — EU-based users were explicitly restricted by certain Llama license versions, a compliance landmine for European products. (4) *Incorporated-by-reference policies* — Acceptable Use Policies are incorporated into the license and updatable; your permitted-use surface can change without a new model download. (5) *Output rights* — whether outputs can train competing models varies by license (Llama 4 explicitly permits synthetic-data/distillation use; some licenses don't). (6) *Attribution mechanics* — notice-file requirements riding along in otherwise-permissive licenses.

**Lens 4 — Safety section: who owns residual risk.** Modern cards increasingly structure safety as *developer responsibility*: Llama 4's card states developers deploying it bear responsibility for safety testing and application-specific tuning, designates unsupported uses (languages beyond the 12 supported — despite ~200 in pretraining — or more than 5 input images) as out-of-scope unless you mitigate, and recommends system-level guards (Llama Guard/Prompt Guard-class classifiers) as part of production deployment. Read that correctly: the vendor evaluated three critical risk categories (CBRNE, child safety, cyber enablement) via recurring red-teaming, and the card transfers everything domain-specific to you. An auditor notes both halves — what was tested, and what contractually became your problem.

**Lens 5 — Operations.** Version semantics (is the API string pinned? does the provider silently update weights behind a stable name — the voice-TTS-rotation failure mode generalized), static-vs-living model notices, knowledge cutoffs, context-window claims with output-token ceilings (1M input alongside 128K output is a real asymmetry), and compute/emissions disclosure (Llama 4: ~7.38M GPU-hours, ~1,999 tons CO2e location-based, zero claimed market-based via renewable matching — relevant for corporate sustainability reporting).

### Choosing between families, honestly

The defensible selection procedure: (1) define the task metric that matters (task completion, not leaderboard proxy); (2) shortlist by hard constraints (license/residency/deployment mode — these eliminate options faster than quality does); (3) evaluate top-3 on *your* private eval set; (4) price the portfolio (tier ladder + routing, per T26-reasoning-models); (5) negotiate exit paths (abstraction layers cost little; lock-in costs a lot). What's indefensible: choosing by brand loyalty, by last week's benchmark tweet, or assuming this cycle's rankings persist — the four-lab simultaneous-flagship window of mid-2026 (with pricing spanning $1.25-$50/M output tokens at comparable claimed capability) is the standing counterexample.

---

## Build it from scratch

**Exercise: a model-card teardown worksheet.** The deliverable is a repeatable artifact — run any candidate model through it in ~45 minutes and produce a go/no-go memo:

```python
# untested sketch — model-card teardown worksheet as executable checklist.
# Score each item 0 (absent/silent), 1 (partial), 2 (fully disclosed+method).
# Anything scoring 0 under LICENSE or EVALS blocks production adoption.

WORKSHEET = {
  "EVALS": [
    "benchmarks cited WITH sample counts and harness versions",
    "reasoning-compute tier stated for every score",
    "eval precision == offered deployment precision (bf16 vs quant)",
    ">=1 independent (non-vendor) reproduction cited",
    "omitted task categories listed explicitly by us, not them",
  ],
  "DATA": [
    "training-data taxonomy named (web/licensed/platform/user-content)",
    "knowledge cutoff dated precisely",
    "contamination statement present WITH decontamination method",
    "n-gram filter size disclosed AND paraphrase-leak caveat addressed",
    "supported languages listed vs pretrained-language reality",
  ],
  "LICENSE": [
    "OSI-approved license? (MIT/Apache=yes; 'community'=audit deeper)",
    "user-count / revenue thresholds identified",
    "jurisdictional carve-outs (EU etc.) checked against our footprint",
    "incorporated-by-reference policies versioned & archived by us",
    "output usage: synthetic data / distillation / competition allowed?",
    "attribution mechanics implementable in our distro pipeline",
  ],
  "SAFETY": [
    "red-team categories enumerated (CBRNE/child-safety/cyber...)",
    "residual-risk owner explicit: vendor vs deployer",
    "recommended system-level guards mapped to our stack",
    "unsupported/out-of-scope uses match our planned use EXACTLY",
  ],
  "OPERATIONS": [
    "version pinning: API string -> immutable weights?",
    "static-vs-living model notice present",
    "context window AND max-output stated separately",
    "compute/emissions figures disclosed",
    "provider model-rotation policy documented (silent updates?)",
  ],
}

def teardown(card_path: str) -> dict:
    """Human scores each item 0-2 in a sidecar YAML; this tallies + gates."""
    import yaml  # sidecar: {EVALS: [2,1,0,0,2], ...}
    scores = yaml.safe_load(open(card_path))
    report, blocked = {}, []
    for lens, items in WORKSHEET.items():
        got = sum(scores.get(lens, []))
        poss = 2 * len(items)
        report[lens] = f"{got}/{poss}"
        if lens in ("LICENSE", "EVALS") and got < poss * 0.6:
            blocked.append(lens)
    report["verdict"] = ("BLOCKED: " + ",".join(blocked)) if blocked else "PROCEED TO PILOT"
    return report
```

Run it against a real card end-to-end once (Llama 4's is a good stress test: it scores high on data-taxonomy and emissions disclosure, mid on evals due to the bf16/quantized gap, and forces the community-license deep-dive) and the audit instinct installs permanently. The worksheet's meta-lesson for interviews: the deliverable of landscape knowledge isn't opinions about labs — it's a *procedure* that survives the next roster turnover.

For a runnable lab automating card ingestion/diff-tracking, no lab exists yet for this module — a reasonable ask is `(lab pending)`.

---

## How it's done in production

| Concern | Typical production practice | Why |
|---|---|---|
| Model selection | Portfolio (flagship/workhorse/fast) + router, chosen on private evals | Single-model bets break on rotation and price moves |
| Procurement gate | Teardown worksheet incl. license review BEFORE pilot | License/EU/MAU traps surface after investment if unchecked |
| Disclosure tracking | Third-party trackers/ledgers for releases + disclosure scores | Vendor blogs are marketing; trackers normalize provenance |
| Benchmark hygiene | Weight dynamic/private benchmarks; demand contamination statements | Public static benchmarks carry ~29%-class contamination |
| Version management | Pin exact snapshots; archive cards/licenses at adoption time | Incorporated policies change silently; diffs matter |
| Exit strategy | Abstraction layer + second-vendor fallback tested quarterly | Flagships get suspended/gated (export control precedent) |
| Open-weight option | MIT/Apache models self-hostable for residency/cost floors | Genuine OSI licenses only; community-license models audited |
| Compliance | Map card data-disclosures to GDPR/CCPA obligations | Platform-user training data creates downstream questions |

**What breaks in production**

| Symptom | Cause | Fix |
|---|---|---|
| Model quality dropped overnight, no deploy changed | Provider rotated weights behind stable API name | Pin snapshot IDs; diff-eval on rotation; subscribe to change ledgers |
| Legal blocks launch post-integration | Community-license term discovered late (MAU threshold/EU clause) | License review is a pre-pilot gate, not a launch checkbox |
| Scores looked great, our tasks fail | Vendor benchmarks contaminated or omitted our category | Private eval set decides; treat published numbers as upper bounds |
| Deployed quantized model underperforms card claims | Evals ran on bf16; we serve int8/fp8 | Demand precision-matched evals or run our own before committing |
| EU users excluded / compliance incident | Jurisdictional carve-out in license text missed | Footprint check against license terms during teardown |
| Flagship unavailable for days | Export-control suspension / safety-review gating | Multi-vendor fallback; regulatory state tracked as availability risk |
| Sustainability report can't close | No compute/emissions figures captured at adoption | Card operations lens includes emissions disclosure |

---

## Tradeoffs & when NOT to use it

- **Don't buy lab reputation instead of running the audit.** "They're a serious lab" is not a disclosure of eval conditions, a license, or a contamination statement — all three have burned adopters of every lab.
- **Don't equate open weights with open source.** If the license isn't MIT/Apache-class, walk the community-license trap list (thresholds, carve-outs, incorporated policies, output rights) — or you've licensed constraints you haven't read.
- **Don't anchor on benchmark leaderboards for selection.** Contamination baselines (~29% MMLU-class) plus disclosure asymmetry mean public scores bound, not measure, capability; your private eval is the instrument.
- **Don't skip the precision question.** Card numbers earned at bf16 don't transfer automatically to quantized serving; require matched-condition evals.
- **Don't build single-vendor.** Mid-2026 saw four flagships ship inside a month, one suspended by export controls and another gated for government review — availability itself is now a portfolio argument.
- **When NOT to do deep teardowns:** prototypes and throwaway spikes can ride default APIs — but the moment real user data, EU traffic, or revenue touches the pipeline, the worksheet gates the pilot. Right-size rigor to exposure, never to enthusiasm.

---

## Interview questions

### Q1 — Sketch the current frontier landscape. Which labs and family structures matter?
**Testing:** whether the map is current and structured, or a stale list of model names.
**Answer:** Eight labs effectively define it: closed-first OpenAI (GPT-5.x tiered families), Anthropic (Opus/Sonnet/Haiku tiers), Google DeepMind (Gemini Pro/Flash, TPU/data advantages), xAI (Grok, aggressive compute buildout); open-weight DeepSeek (MIT-licensed V-flagship MoE + R-series reasoners), Alibaba Qwen (highest-cadence catalog), Mistral (dense/MoE/reasoning split, Europe's lab), and Meta in transition (Llama legacy → closed Muse Spark → partial Apache reopening). Structurally: every family ships a tier ladder (roughly $1.25-$50/M output tokens) plus reasoning dials and ~1M-token contexts.
**Follow-up trap:** *"Which is the best lab?"* — the question assumes persistence the record denies: leadership flipped repeatedly within single years, and the mid-2026 window saw four flagships ship in a month with conflicting benchmark claims. The strong answer gives a portfolio view plus selection procedure, refusing the ranking bait.

### Q2 — Walk through reading a model card as an auditor rather than a reader.
**Answer:** Five lenses: (1) Evals — what's cited vs omitted, vendor-run vs independently reproduced, at what compute tier and checkpoint precision (bf16-evaluated/quantized-deployed gaps are documented in real cards); (2) Data — source taxonomy, cutoff, and whether contamination gets a *methodology* (n-gram filters and their paraphrase weakness) or silence; (3) License — OSI status, scale thresholds, jurisdictional carve-outs, incorporated-by-reference use policies, output rights; (4) Safety — red-team scope AND who contractually owns residual risk (modern cards transfer it to the deployer); (5) Operations — version pinning, static-model notices, output-token ceilings, compute/emissions disclosure.
**Follow-up trap:** *"Which single omission is most disqualifying?"* — arguably missing contamination methodology, because it poisons every downstream decision: an inflated benchmark number propagates into selection, pricing, and promises. License problems block legally, but eval-integrity problems corrupt technically and invisibly.

### Q3 — Why is 'open weights' not the same as open source? Give the concrete failures.
**Answer:** Open weights answer logistics (downloadable?), open source answers rights (use/study/modify/redistribute for any purpose). Meta's Llama Community License fails OSI's definition per OSI's own analysis and FSF concurrence: purpose restrictions via an Acceptable Use Policy, discrimination against user classes (the 700M-MAU provision changes terms by who you are), field-of-endavor limits, and version-specific EU carve-outs. MIT and Apache 2.0 convey genuine freedoms; community licenses convey revocable privileges.
**Follow-up trap:** *"Does it matter practically if we're small?"* — yes, three ways: the AUP applies at every size and updates silently; the license can change between model generations, breaking continuity assumptions; and downstream products built atop your deployment inherit whatever terms you accepted. Small teams discover this when acquired or when scaling crosses thresholds they'd forgotten existed.

### Q4 — Explain benchmark contamination and quantify why it matters.
**Answer:** Web-scale pretraining crawls ingest public benchmarks — questions AND answers — so models may be graded on material seen in training. Measured: ~29.1% of MMLU items showed contamination signals (JHU/NAACL 2024), C-Eval ~45.8%, multilingual benchmarks up to ~91.8% as translations multiply copies; Meta's own Llama 2 report found 16% MMLU overlap (some >80% token match), and OpenAI's GPT-4 report admitted 9 of 34 exams exceeded 20% overlap. Impact: clean-mirror rebuilds drop scores materially (GSM8K −13 points in one study); inference-time decontamination strips ~22.9% of MMLU inflation. Filters (13-gram in GPT-3, 40-gram in GPT-4) miss paraphrase/translation leaks.
**Follow-up trap:** *"So all benchmarks are worthless?"* — no; they're upper bounds with unknown bias. Dynamic benchmarks (LiveBench refreshes monthly from post-cutoff sources), private held-out sets (where GPT-4o scored 73.4% versus higher public numbers), and contamination-resistant formats restore signal. The discipline: provenance-check every number you make a decision on.

### Q5 — A vendor card shows SOTA scores but lists no contamination methodology and no independent reproductions. Construct your assessment.
**Answer:** Treat scores as unverified upper bounds. Actions: seek third-party index results (disclosure trackers show labs ranging from full disclosure to near-zero); run the model on a private eval matching our task; check dynamic-benchmark standings less susceptible to leakage; interrogate the omission directly with the vendor (silence about decontamination is different from having none). Meanwhile the card earns negative audit credit — absence of methodology where peers provide it is a disclosure-quality signal, not neutrality.
**Follow-up trap:** *"Vendor says 'trust us, we decontaminate.' Now what?"* — proportionate trust requires artifacts: filter sizes, overlap statistics, held-out-set deltas. Labs that publish these (some do, including admitting uncomfortable overlaps) demonstrate the operational maturity the claim implies; refusal after a direct ask is decision-relevant information about the relationship, not just the number.

### Q6 — What did the mid-2026 export-control incidents teach about availability engineering?
**Answer:** That regulatory state is a first-class availability dimension: one flagship was suspended ~22 days by US export-control directive before restoration, and another was gated ~12 days pending government safety review — both post-launch, both with customers mid-dependency. Lessons: multi-vendor fallback must be tested (not theoretical), abstraction layers earn their cost, regional deployment strategies need regulatory monitoring wired into ops, and contracts should allocate suspension risk explicitly.
**Follow-up trap:** *"Isn't that a policy problem, not engineering?"* — the trigger is policy; the blast radius is engineering. Teams with pinned alternatives failed over in hours; teams without spent weeks negotiating. Treating geopolitics as out-of-scope for infrastructure design is how single-region database thinking sounded in 2010.

### Q7 — Compare DeepSeek's and Meta's positions on openness. What does each teach?
**Answer:** DeepSeek: consistent MIT licensing of frontier-class MoE flagships plus the R-series reasoners with published recipes — openness as strategy, forcing global repricing and enabling self-hosted/residency-constrained deployments. Meta: openness as instrument — the Llama line seeded an ecosystem under a non-OSI Community License with strategic carve-outs, then pivoted frontier work closed (API-only Muse Spark) before partial reopenings (Apache 2.0 mid-size release). Teachings: openness is a per-model license property, not a lab identity; and ecosystem-gravity value doesn't require permanent openness.
**Follow-up trap:** *"Which approach wins?"* — wrong frame. They serve different buyers: MIT weights win where residency/cost/self-modification dominate; closed APIs win where managed safety infrastructure and capability velocity dominate. Portfolio reality: most serious deployments mix both, which is precisely why license literacy persists as a required skill.

### Q8 — Your CFO asks why model costs vary 40x across comparable-capability tiers. Explain.
**Answer:** Multiple legitimate factors: positioning (flagship tiers carry margin and scarcity pricing; fast tiers compete on volume), inference cost structure (MoE active-parameter counts, reasoning-token burn at higher effort tiers), bundling (managed safety features, SLAs, compliance certifications), and strategic pricing against open-weight competition — the $1.25/M floor exists because MIT-licensed alternatives anchor it, and the $50/M ceiling holds where capability-at-any-price buyers concentrate. Plus market immaturity: pricing moves faster than value evidence.
**Follow-up trap:** *"So always buy cheap?"* — only when the private eval can't distinguish tiers on YOUR task. Where capability differences bind (hardest reasoning, long-horizon agents), premium tiers pay for outcomes, not brand. Price-per-task at your quality bar, per T26-reasoning-models' routing economics.

### Q9 — Which model-card sections do most engineers skip that most often bite them?
**Answer:** In observed order: (1) the license annexes — especially incorporated-by-reference use policies and jurisdictional clauses; (2) the out-of-scope/use-limitations section — deploying beyond the 12 supported languages or past input-image limits voids the vendor's own testing envelope and shifts ALL risk to you; (3) the precision/evaluation-conditions footnote (bf16 vs quantized); (4) the static-model/version-semantics notice; (5) data-source disclosures with privacy implications (platform user content) that map onto GDPR/CCPA duties downstream.
**Follow-up trap:** *"Who should own card audits — legal or engineering?"* — jointly, with engineering owning technical lenses (evals, precision, operations) and legal owning license/policy interpretation, but ONE artifact: a shared worksheet with a blocking gate, else each group reads half the document and nobody reads the interaction effects (e.g., an AUP clause with a technical-enforcement implication).

### Q10 — How do you keep landscape knowledge current without drowning?
**Answer:** Cadence + filters: track third-party release ledgers and disclosure-scored trackers (not vendor blogs alone) on a weekly scan; reserve deep reads for models passing a relevance screen (our task classes, our license constraints); maintain the teardown worksheet as living infrastructure so each new candidate costs 45 minutes, not a research project; re-run the private eval quarterly on the incumbent AND top challenger — drift happens to deployed models too. Explicitly budget ignorance: no individual tracks all eight labs deeply; portfolios and procedures absorb roster churn.
**Follow-up trap:** *"What signals tell you the map has redrawn?"* — simultaneous multi-lab flagships within a month (repricing follows), a disclosure-pattern change from any lab (strategy shift precedes product shift), suspension/regulatory events, and license-family changes within a lineage. Any one triggers a portfolio review, not just a news skim.

### Q11 — Construct the strongest case AGAINST relying on any single benchmark family for selection.
**Answer:** Four independent failure modes compound: contamination (up to ~29% of MMLU-class items leaked, worse multilingually); saturation (top models compress score differences into noise); misalignment with task reality (leaderboard categories ≠ your workload — SWE-bench rank predicts code-agent success imperfectly); and gaming pressure (teaching-to-the-test is rational when benchmarks drive valuation). Hence the standard: dynamic/private benchmarks for trend direction, private task-specific evals for decisions, published numbers as upper bounds requiring provenance checks.
**Follow-up trap:** *"Private evals have problems too — small samples, distribution drift."* — correct, and worth stating: they trade external validity for decision relevance. Mitigations: refresh eval sets periodically from real traffic, keep sample sizes honest (report intervals, not vibes), and never let the private eval become a secret benchmark the industry trains toward — which, at frontier scale, occasionally literally happens to public ones.

### Q12 — What belongs in an organization's model-adoption policy, concretely?
**Answer:** Seven clauses: (1) mandatory teardown worksheet gate before pilots touching real data; (2) license whitelist logic (MIT/Apache auto-pass; community licenses route to legal with the trap checklist); (3) private-eval minimum bar per task class with recorded results; (4) precision-matched evaluation requirements; (5) version-pinning and rotation-diff obligations on providers; (6) data-provenance mapping to privacy/regulatory obligations at adoption time; (7) exit-path requirements (tested second-vendor fallback, abstraction layer). Review cadence: quarterly, or event-triggered by the map-redraw signals.
**Follow-up trap:** *"Doesn't this bureaucracy kill iteration speed?"* — the worksheet is ~45 minutes against adoption decisions costing quarters; the real speed killer is discovering license/EU/rotation problems AFTER integration. Tier the policy by exposure (prototypes exempt, revenue-path gated) so speed survives where risk doesn't.

---

## Red flags that fail you

- Reciting model names without family/tier structure, license status, or price bands.
- Equating "open weights" with open source, or unable to name one concrete community-license restriction.
- Reading model cards as documentation rather than as partially-adversarial disclosure documents.
- No contamination awareness — treating public benchmark numbers as ground truth.
- Selecting models by brand or last week's leaderboard tweet with no private-eval mention.
- Unaware that providers rotate weights behind stable API names.
- No answer for availability risk beyond a single vendor.
- Claiming the landscape is static enough for long-term single-model bets.

---

## Cheat card

```
THE MAP (2026, redraws quarterly)
  closed: OpenAI GPT-5.x tiers · Anthropic Opus/Sonnet/Haiku ·
          Google Gemini Pro/Flash · xAI Grok
  open:   DeepSeek V(MIT)+R · Qwen catalog · Mistral dense/MoE/reasoning ·
          Meta Llama→Muse Spark transition (partial Apache reopen)
  shape:  tier ladders $1.25-$50/M out-tokens · reasoning dials ·
          ~1M ctx (128K-class out ceilings) · multiple flagships/month

CARD AUDIT — 5 LENSES
  EVALS    cited vs omitted · vendor vs independent · compute tier ·
           PRECISION MATCH (bf16-eval vs quantized-deploy gap is real)
  DATA     source taxonomy · cutoff · contamination METHOD or silence ·
           supported langs vs pretrained langs (12 vs ~200, Llama 4)
  LICENSE  MIT/Apache=OSI ✓ · "community"=audit: MAU caps (700M),
           EU carve-outs, AUP incorporated by reference, output rights,
           attribution files
  SAFETY   red-team scope (CBRNE/child/cyber) · residual risk owner =
           YOU (deployer) · out-of-scope = untested, risk transferred
  OPS      pinning vs silent rotation · static-model notice ·
           ctx-in vs ctx-out asymmetry · GPU-hours/CO2e disclosure

CONTAMINATION NUMBERS
  MMLU ~29.1% items flagged (JHU 24) · C-Eval ~45.8% · multilingual ≤91.8%
  Llama2 self-report: 16% overlap (>80% tok-match some) ·
  GPT-4 report: 9/34 exams >20% overlap · filters: 13-gram→40-gram,
  paraphrase/translation leaks pass
  IMPACT: GSM8K mirror −13pts · ITD removes ~22.9% MMLU inflation ·
  MMLU-CF private: GPT-4o 73.4%

SELECTION PROCEDURE  constraint-filter (license/residency/mode) →
  private-eval top-3 → price the tier portfolio → negotiate exits.
  NEVER: brand, leaderboard tweets, single-vendor bets.

AVAILABILITY  flagships get SUSPENDED (export control, ~22d) and
  GATED (gov review, ~12d) post-launch → tested fallbacks, abstraction,
  regulatory monitoring in ops.

DISCLOSURE ASYMMETRY  third-party scores range 8/8 → 0/8 disclosed
  specs/benchmarks across majors; conflicts across sources even for
  shipped flagships (same model, two Terminal-Bench numbers).
```

## Sources

- [Frontier AI Heats Up: Anthropic, OpenAI, Google and Meta Ship a Wave of New Models — NeuralStack](https://www.neuralstack.network/article/2026-08-01-frontier-ai-models-july-2026-roundup) — accessed 2026-08-23
- [Top Frontier AI Labs and Models in 2026 — FutureSearch](https://futuresearch.ai/blog/forecasting-top-ai-lab-2026) — accessed 2026-08-23
- [8 Frontier AI Labs Compared (2026) — Veksler Cheatsheets](https://cheatsheets.davidveksler.com/ai-frontier.html) — accessed 2026-08-23
- [The Frontier Ledger — Meta, xAI, OpenAI & Anthropic Compared](https://frontier-ai-dashboard-three.vercel.app/) — accessed 2026-08-23
- [The frontier AI models, right now — Mungomash](https://mungomash.com/ai/models/) — accessed 2026-08-23
- [LLM Benchmark Contamination: MMLU Data Leakage — Pebblous](https://blog.pebblous.ai/blog/llm-benchmark-contamination/en/) — accessed 2026-08-23
- [Investigating Data Contamination in Modern Benchmarks — arXiv 2311.09783](https://arxiv.org/abs/2311.09783) — accessed 2026-08-23
- [Meta's LLaMa license is still not Open Source — OSI](https://opensource.org/blog/metas-llama-license-is-still-not-open-source) — accessed 2026-08-23
- [Llama 4 Community License & Model Card — Meta/GitHub](https://github.com/meta-llama/llama-models/blob/main/models/llama4/LICENSE) — accessed 2026-08-23
- [Llama 4 Model Card governance analysis — ConductAtlas](https://conductatlas.com/platform/meta/llama-4-model-card/) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created