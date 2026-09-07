# Production notes — union-find

## Where union-find ships

- **Network connectivity** — link-state protocols and datacenter fabric topology checks ("is every ToR reachable from every spine?") are dynamic connectivity queries: union-find over the wiring graph.
- **Kruskal MST** — every MST problem (network cabling, cluster linking, approximating metric-TSP) rejects cycle edges with union-find. Your `kruskal_mst` is the real algorithm, unmodified.
- **Single-linkage clustering / image segmentation** — merging superpixels or particles into blobs is exactly union-find over "similar-enough" edges; scikit-image and OpenCV pipelines use it per frame.
- **Git merge** — finding the merge base walks the commit DAG; reachability sets use union-find-style ancestor structures. File-rename detection across commits is union-find over blob identities.
- **Accounts / entity resolution** — the accounts-merge problem is literally how CRMs dedupe customer identities: shared emails/phones/cards union into one entity.
- **Percolation & dynamic graph property testing** — Monte Carlo grid connectivity, puzzle solvability, "will the water reach the bottom?" — union-find is the standard tool.
- **Dynamic connectivity in DSUs** — competitive programming's "DSU with rollback" backs offline algorithms in production-quality constraint solvers.

## Complexity table

| Configuration | Amortized per op | Worst-case find | Notes |
|---|---|---|---|
| No optimizations | O(n) find | O(n) | the trap |
| Path compression only | O(log n) amortized | O(log n) | fine for most cases |
| Union by rank only | O(log n) worst | O(log n) | no recursion — embeddable |
| **Both** | **O(α(n))** ≈ constant | O(log n) first-touch | α = inverse Ackermann ≤ 5 for any addressable n |
| Kruskal overall | O(E log E) sort-dominated | — | UF part is near-linear |

α(n) < 5 for any n that fits in the observable universe — interviewers accept "amortized O(1)" with that caveat.

## The 3 questions an interviewer asks

1. *"Why is union-find amortized almost-O(1) and not actually O(1)?"* — α(n) is not a constant, it's an extremely slow-growing function; a single find can still cost O(log n) before compression pays off.
2. *"Kruskal vs Prim — when and why?"* — Kruskal for sparse graphs / edges-known-ahead / streaming sorted edges (UF is cheap); Prim for dense graphs with a heap over adjacency lists.
3. *"Union-find can't delete — how do production systems handle dynamic graphs with deletions?"* — offline processing with rollback, or rebuild + bisect the timeline; deletion is the known weakness of the structure, which is why link-cut trees exist (and why nobody uses them in production).
