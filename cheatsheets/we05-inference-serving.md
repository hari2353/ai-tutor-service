# KV Cache Math, PagedAttention, Continuous Batching, vLLM/SGLang

> Sprint weekend 5 · source: `curriculum/05-llm-internals/09-inference-serving.md`

```
BOTTLENECKS     prefill = compute-bound (parallel over prompt, high arithmetic intensity)
                decode  = memory-bandwidth-bound (1 token/step, reads full KV cache + weights)
                arithmetic intensity drops ~5x prefill -> decode

KV CACHE/TOKEN  2 * n_layers * n_kv_heads * d_head * bytes_per_elem
WORKED EX       70B, 80L, GQA-8, d_head=128, bf16: 0.32MB/tok; 4k ctx=1.3GB/seq; 128k ctx=42GB/seq

PAGEDATTENTION  fixed-size KV blocks (e.g. 16 tok) + per-seq block table, OS-paging analogy
                naive contiguous alloc wastes 60-80%; paged waste <4% -> 2-4x throughput

BATCHING        static: batch waits for slowest member, idles finished slots
                continuous/in-flight: evict/admit every decode step -> near-100% utilization

CHUNKED PREFILL splits long prompt prefill into chunks (vLLM default 2048 tok)
                interleaves with others' decode -> fixes head-of-line blocking on TPOT

PREFIX CACHING  vLLM: block-content hash match, reference counted
                SGLang RadixAttention: whole-pool radix tree, automatic cross-request reuse, LRU leaves
                8B ShareGPT bench: SGLang ~16.2k tok/s vs vLLM ~12.5k (~29%); narrows to 3-5% at 70B

TTFT            queueing + prefill time -> scales with prompt length + load
TPOT (ITL)      memory-bandwidth-bound decode step time -> scales with total KV cache read/step
THROUGHPUT      aggregate tok/s across all concurrent requests
TRADEOFF        batch size UP -> throughput UP, TPOT UP, possible TTFT UP for new arrivals -- no free lunch

COST MODEL      $/M tokens = (GPU $/hr) / (tok/s * 3600) * 1e6
                batch size lowers $/M tok up to bandwidth/capacity ceiling, then preemption can raise it

NEVER FORGET    serving tricks manage whatever KV cache size the ARCHITECTURE produces (see T05-attention)
                they cannot shrink bytes/token themselves
```
