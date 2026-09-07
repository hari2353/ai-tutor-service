# Production notes — graphs in the wild

## The four real systems you just reimplemented (a slice of)

| Your lab | The real thing | What it adds |
|---|---|---|
| `resolve_packages` | pip (Resolvelib), Cargo (PubGrub), npm (Arborist) | backtracking, SAT-style search, preferences (opt-in features, extras), locking |
| `graph_rag_answer` | Microsoft GraphRAG, LlamaIndex KnowledgeGraphIndex | entity extraction, entity resolution, community detection + summaries, query routing |
| `pagerank` | Google Search (1998), crawl prioritization, Spark GraphFrames | damping per edge, personalized/weighted variants, sparse matrix power iteration at web scale |
| `critical_path_dag` | Bazel, Buck, Pants, Gradle | remote caching, dynamic (estimated) durations, incremental re-analysis, critical-path *scheduling* |

## Dependency resolution is NP-hard in general

Your resolver walks the graph once and never revises a choice — and that is
fine for single-level deps. Real resolution is **constraint satisfaction**:
`A needs B>=2.0` while `C needs B<2.0` may still have a solution *if A can
drop to a version that accepts B<2.0*. Finding it requires backtracking
through the exponential space of version combinations — the general problem
is NP-hard (it encodes SAT), which is why:

- **pip** moved to Resolvelib (2020, pip 20.2+): backtracking over candidate
  sets with constraint narrowing — and became notoriously slower on conflict-
  heavy trees, exactly the cost of correctness. The old resolver greedily
  took the first satisfiable version and produced broken environments.
- **Cargo** uses **PubGrub** (the Dart/Flutter algorithm): it tracks, for
  each version ever excluded, *why* it was excluded, so when resolution
  fails it can report "X requires Y>=2, but Z requires Y<2" — an incompatibility
  *derivation tree* rather than "no solution found". Debuggability is a
  first-class design goal, not an afterthought.
- **npm** (Arborist) similar; the ecosystem-level pain moved from
  resolution-time to dedup/time.

The follow-up you will get: *"Why does pip sometimes fail even though a
human can find a solution?"* — because greedy/no-backtrack (or
bounded-backtrack) resolution trades completeness for speed; the honest
answer names the tradeoff instead of claiming the tool is buggy.

## GraphRAG at Microsoft — why traversal answers what recall can't

The 2024 Microsoft Research paper ("From Local to Global: A Graph RAG
Approach to Query-Focused Summarization", arXiv:2404.16130) built exactly
the two stages your `graph_rag_answer` lives inside:

1. **Extraction** — LLM pulls (entity, relation, entity) triples from every
   chunk, resolves coreferences so "Guido" and "van Rossum" are one node,
   then Leiden community detection partitions the graph and an LLM writes a
   summary per community. This stage is the dominant cost and the dominant
   error source: wrong extraction means a wrong graph, and no traversal
   logic recovers from a wrong graph.
2. **Retrieval** — *local* queries do vector search from matched entities
   then expand over graph neighborhoods; *global* ("how do these relate
   across the corpus?") queries fetch and reduce the community summaries
   instead of any individual chunk.

Your two-hop chain traversal is the local-search slice. The structural
point the lab encodes: a query like "python → guido → microsoft" has an
answer only if you can *join facts across documents* — top-k similarity
recall ranks documents one at a time and never composes them, so it
structurally cannot return "created_by, works_at" no matter how good the
embeddings are. Production risk: unbounded multi-hop expansion explodes
(dense graph → whole-graph traversal flooding the context window), which
is why real deployments cap hops and prune by relevance.

## PageRank in production — ranking, crawling, and priors

- **Search:** Google's original ranking. Today pure PageRank is one feature
  among hundreds inside learned-to-rank models — naming it "what Google
  still uses, unchanged" is an interview red flag.
- **Crawl prioritization:** page importance under a crawl budget — which
  URLs to fetch first. Personalized PageRank (jump distribution biased to
  your own site/app graph) is the standard "importance relative to *me*".
- **RAG/agents:** entity-importance priors over knowledge graphs, so
  traversal and summarization spend their budget on important subgraphs.

Your dangling-node redistribution matches the standard formulation: a
dangling page is a surfer who teleports to a uniformly random page next
turn. Without damping (d=1) a sink swallows probability mass and
disconnected components never mix — the unique stationary distribution
that power iteration relies on stops being guaranteed. d≈0.85 balances
"trust the link graph" against "escape traps", and convergence speed is
governed by the spectral gap, not a fixed iteration count — which is why
you take a `tol` and a `max_iter`, not a hardcoded "20 is always enough".

## Build systems — the critical path IS your wall time

Bazel computes the critical path of the target graph (action graph, with
*estimated* action durations) and reports it as the "critical path" in its
profile output — because with enough parallel workers and warm caches,
build wall time converges to the critical path, and every cycle spent
optimizing anything *off* that path is wasted. Real uses:

- **Why is my build slow?** — Bazel's `--profile` shows the critical path;
  the fix is either shortening a path action (sharding tests, splitting a
  codegen step) or adding workers if the path is worker-saturated.
- **CI pipeline design** — the same DP over your CI stage DAG; the
  "critical path" of your yaml pipeline is what blocks the merge.
- **Scheduling** — critical-path scheduling orders ready work to minimize
  makespan on a fixed worker pool (the classic list-scheduling heuristic).

Your Kahn + longest-to-here DP + parent pointers is exactly the shape;
production adds remote caching (previous durations observed, not
estimated), incremental analysis (only re-plan the dirty subgraph), and
execution-driven re-planning when estimates turn out wrong.

## The 3 questions an interviewer asks next

1. *"Your resolver returns None on the shared-dep conflict — how does pip
   find a solution anyway?"* — backtracking over already-chosen versions,
  and PubGrub-style conflict derivation for the error message. The general
   problem is NP-hard; solvers bound the search and may still give up.
2. *"Why does GraphRAG need two stages, and which one usually fails?"* —
   extraction then retrieval; extraction (entity resolution) dominates
   error, retrieval is comparatively easy once the graph is right.
3. *"When does the critical path stop being the build time?"* — when
   workers or cache bandwidth saturate first; wall time is
   max(critical path, resource-saturated makespan), and the profile tells
  you which regime you are in.
