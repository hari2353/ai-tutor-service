# Lab 04: A Small HNSW Index From Scratch

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 3h · **XP:** 50
**Module:** `T06-vector-index-internals`

**You will build:** a working HNSW (Hierarchical Navigable Small World) index --
layered graph construction, greedy search descent, `ef`-width beam search, and
`M`-capped neighbour selection -- validated against brute-force exact search on a
seeded dataset, numpy only.

**You will be able to answer:** *"Walk me through HNSW's insert and search. What do
`M` and `efSearch` each actually trade off, and how do you know your graph stayed
connected?"*

## Setup

```bash
cd labs/py/04-hnsw-index
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest numpy                          # only dependencies
```

## The spec

1. **`brute_force_knn(vectors, query, k)`** -- exact k-NN by full scan. This is the
   ground truth every recall test measures against.
2. **Layered graph** -- each inserted vector is assigned a random top layer
   (`_random_level`, the standard `-log(uniform) * mL` sampling). `self.graph[l]`
   holds the adjacency for layer `l`; every node exists at layer 0 and every layer
   up to its assigned level.
3. **Greedy descent + beam search** -- `_greedy_closest` does single-best-neighbour
   descent on the upper (sparse) layers to get close cheaply; `_search_layer` does
   an `ef`-width beam search at the target layer, the same routine used at both
   construction time (`ef_construction`) and query time (`efSearch`).
4. **Neighbour selection with `M`** -- `_select_neighbors` keeps the `M` closest
   candidates (`M_max0 = 2M` at layer 0, the standard denser base layer); `_prune`
   enforces the cap on existing nodes when a new bidirectional edge pushes them over
   it -- except it refuses to strand a node at degree 0, because staying connected
   matters more than a hard degree cap for one rare node.
5. **`search(query, k, ef_search)`** -- descend from the entry point, beam-search
   layer 0, return the `k` closest.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Neighbour diversity heuristic** -- replace "M closest" selection with HNSW's
   actual heuristic (prefer neighbours not already well-covered by an existing
   neighbour's neighbours), and measure whether recall-per-byte improves.
2. **IVF-PQ comparison** -- implement a minimal IVF (cluster + scan within
   cluster) alongside this HNSW, and compare recall/memory/build-time trade-offs
   on the same dataset.
3. **Filtered search** -- add a metadata predicate to `search()` and measure how
   naive post-filtering degrades recall as the filter's selectivity increases (the
   problem `T06-vector-index-internals` calls out as unsolved in general).
4. **Delete support** -- HNSW has no native delete. Implement tombstoning (mark
   deleted, filter at search time, periodically rebuild) and measure how recall
   degrades as the tombstone fraction grows.
