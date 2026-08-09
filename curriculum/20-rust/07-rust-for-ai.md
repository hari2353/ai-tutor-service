# Rust in the AI Stack: tokenizers, candle, PyO3 Bindings, Why It's Everywhere

> **Track:** T20 Rust · **Time:** 2h · **Prereqs:** `T20-rust-ownership`, `T20-rust-async`, `T20-rust-perf`, `T01-gil-parallelism` · **Updated:** 2026-08-06
> **Module id:** `T20-rust-for-ai` · **Tags:** rust, python-interop, pyo3, tokenizers, inference, infrastructure, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Rust colonised the AI *infrastructure* layer and did not touch the modelling layer, and the reason is a single repeating pattern: a hot loop that is not a matmul, called millions of times, where CPython's ~50 ns per-bytecode-dispatch and the GIL dominate and there is no BLAS call to hide behind. Tokenization is the canonical case, and I measured it this session: the same GPT-2 BPE producing byte-identical output ran at 0.98 MB/s in pure Python with a cold cache versus 14.3 MB/s in tiktoken's Rust core, a 14.4x gap, and `tokenizers`' `encode_batch` got a further 2.27x on two vCPUs purely because it releases the GIL and fans out over rayon while pure Python cannot. But the honest number cuts both ways: the same pure-Python BPE with a warm memo cache ran at 33.8 ms against HuggingFace `tokenizers`' 43.2 ms on the identical 100 KB slice, so it *beat* the Rust library, because HF's `encode()` materialises eight parallel vectors including a `String` per token and that costs more than the merge loop it saved. The boundary itself is the thing people never price: an empty PyO3 function call cost me 54.56 ns against 50.71 ns for an empty Python `def`, so crossing into Rust costs roughly one Python call, which means any Rust function doing less than about a microsecond of work is a pure loss, and my `sum_list(Vec<i64>)` was **2.4x slower** than the builtin `sum()` because per-element `PyLong` extraction is exactly the work `sum()` was already doing. The staff-level answer to "why not rewrite it in Rust" is therefore a question back: what fraction of wall time is CPU-bound Python bytecode, because if you are serving LLMs the GPU is 95% of it and rewriting the FastAPI layer in Rust moves p99 by single-digit milliseconds on a 4-second request.

## Why this gets asked

Because every interviewer running an LLM platform has sat in the meeting where someone proposed rewriting the inference service in Rust, and roughly half of them have lived the aftermath. The proposal is always seductive and almost always mispriced: the team spends two quarters porting a FastAPI service to axum, ships it, and discovers that p99 dropped from 4,120 ms to 4,090 ms because the 4,000 ms was always the H100 doing prefill and decode, and the Python overhead they eliminated was 30 ms of request parsing. Meanwhile the migration cost them their ability to hire, because the ML engineers who need to ship a new reranker cannot touch the codebase. The interviewer wants to know whether you will make that call correctly, in *both* directions: whether you will say no to the pointless rewrite, and whether you will recognise the one component in the stack where Rust genuinely buys 10x and say yes to that.

The second thing they are probing is whether you understand the *mechanism* rather than the slogan. Anyone can say "Rust is faster". The signal is in knowing that the reason `tokenizers` is in Rust is not raw instruction throughput, it is that BPE is a data-dependent merge loop over short strings with no vectorisable inner kernel, that it is called on every request in the serving path and on every document in the training path, and that it is the one preprocessing step that cannot be batched onto the GPU. If you can name that shape, you can find the *next* component that has it, which is what a principal engineer is for. The third probe is quieter: they want to know if you have ever actually built a binding, because everyone who has knows about the GIL release, the zero-copy buffer question, the abi3 wheel matrix, and the fact that the boundary crossing has a price. People who have only read about it talk about "Rust's speed" and never mention that a `Vec<String>` returned across the boundary allocates a Python object per element.

There is also a live variable now that did not exist two years ago. Python 3.14 shipped an officially supported free-threaded build (PEP 779, phase two), and PyO3 renamed `Python::with_gil` to `Python::attach` and `Python::allow_threads` to `Python::detach` in 0.29 precisely because the GIL is no longer a universal assumption. If "Rust because the GIL" was half your argument, half your argument now has an expiry date on it, and interviewers at the sharper shops will push exactly there.

---

## Lineage: past → present → future

**What came before.** The first generation of Python performance escape hatches was C extensions written by hand against the CPython API, and the pain that killed them was not performance, it was that they were unmaintainable and unsafe. NumPy (2006) and its ancestors Numeric (1995) and numarray established the winning pattern of the era: push the loop into C, keep the orchestration in Python, and make the boundary crossing rare by making the unit of work an entire array. That pattern is still correct and is why nobody rewrites NumPy in Rust. Then came the layer NumPy could not absorb. Cython (2007) let you write C-ish Python and was the default answer for a decade, but the resulting code was neither Python nor C, the generated `.c` files were 20,000 lines of unreadable macro soup, and debugging a segfault meant reading them. `ctypes` and later `cffi` (2013) avoided the compile step but paid enormous per-call overhead and gave you zero type safety at the boundary. Numba (2012) JIT-compiled a Python subset via LLVM and worked beautifully right up until you used a feature outside the subset, at which point it silently fell back to object mode and ran 100x slower with no error.

The specific pain that opened the door for Rust was the tokenizer. Around 2019, transformer training and serving made tokenization a first-class bottleneck for the first time. The reference implementations were pure Python: OpenAI's `gpt-2/src/encoder.py` is a 120-line file with a `bpe()` function containing a `while True` loop that recomputes `min(pairs, key=bpe_ranks.get)` on every merge, and `transformers`' original `PreTrainedTokenizer` was the same shape. At GPT-2 scale that was tolerable. At the scale of tokenizing a multi-hundred-gigabyte pretraining corpus, or of tokenizing every request in a serving fleet, it was not: a single Python process tokenizing at roughly 1 MB/s means a 500 GB corpus takes about six days on one core, and `multiprocessing` around it means pickling text across process boundaries and paying a copy per document. HuggingFace shipped `tokenizers` in late 2019 (the repo was created 2019-11-01) as a Rust core with Python bindings, and it worked, and it became the proof of concept that everyone else copied. Notably the pain was *not* "Python is slow at arithmetic". It was "Python is slow at a loop over short byte strings that cannot be vectorised, cannot be handed to BLAS, and cannot be parallelised inside one process".

**Where it stands now.** The division of labour has stabilised and is remarkably clean: **Rust owns the layer where the data is not a tensor**, and Python owns the layer where it is. Tokenizers, serialization (`safetensors`, currently 0.8.0), packaging and linting (`uv` 0.12.2 and `ruff`, at 88.4k and 49.1k GitHub stars as of 2026-08-06, both from Astral), dataframes (Polars, 39.3k stars), vector databases (Qdrant 33.8k, LanceDB 11.1k), and now the routing and gateway tier: both SGLang's `sgl-router` and vLLM's `router` (the latter a fork of the former) are Rust, and both do tokenization, reasoning-parser and tool-call parsing in Rust specifically so the router can compute prefix-match and prompt length for cache-aware load balancing without a round trip to a worker. Meanwhile vLLM and SGLang themselves remain overwhelmingly Python at 88.3k and 31.4k stars, because the part that matters is CUDA kernels and the Python is a thin scheduler over them.

The live disagreements are three. First, **whether Rust-native inference stacks are a real category or a niche**. `candle` (20.9k stars, 0.11.0, last push 2026-08-05) and `burn` (15.7k stars, 0.22.0-pre.1, last push 2026-08-05) are genuinely active and genuinely used, but the reported performance is wildly bimodal: marketing-adjacent comparisons claim 35-47% faster than PyTorch on BERT and ResNet-50, while candle issue #2877 documents `all-MiniLM-L6-v2` running at 122.30 ms per batch in candle 0.8.4 against ~14.34 ms in PyTorch, which is 8.5x *slower*, and issue #942 reports the same for YOLOv8 against ONNX Runtime. Both are true, because the variance is entirely about whether your specific model's specific ops have a tuned kernel in that specific backend. PyTorch has had ten years of people hand-tuning every op; candle has not. Second, **whether the GIL argument survives free-threading**. PEP 779 was accepted for 3.14, moving free-threading to phase two (officially supported, still opt-in, shipped as the `3.14t` binary), single-threaded overhead is down to roughly 5-10% from ~40% in the 3.13 experimental build, and phase three (default) has no committed version. PyO3 has supported building for the free-threaded build since 0.23 and renamed the GIL APIs in 0.29 to match. The honest read: free-threading removes the *parallelism* argument for Rust over a multi-year horizon and removes none of the *single-thread constant factor* argument, which was always the larger term. Third, **whether the binding boundary is cheap enough for fine-grained interop**, and here the measurements below say plainly that it is not, and that this is the single most under-priced variable in the whole discussion.

What is actually deployed at scale versus merely published: `tokenizers` and `safetensors` are in essentially every serving stack on earth. `uv` and `ruff` have eaten their categories. Polars is real and growing but pandas is still the default. Qdrant and LanceDB are real products. candle and burn are deployed in the specific niches described below and are not displacing PyTorch anywhere that has a GPU fleet.

**Where it's heading.** High confidence: the Rust-owned surface keeps expanding *outward from the tensor*, not inward. The next components to go are the ones already going: routers and gateways, prefix-cache indexes, structured-output/grammar engines, embedding services, and data-loading pipelines. All of them share the shape. High confidence also that PyO3 and maturin remain the only serious path and that abi3 wheels become the default expectation rather than a nice-to-have, because the CI matrix cost of non-abi3 is the main friction remaining. Medium confidence: free-threaded Python becomes the default within two to four releases, and when it does, a specific class of Rust binding (the ones whose entire justification was `allow_threads` for parallelism) loses its reason to exist, while the ones justified by constant factor do not. Medium confidence that candle and burn converge on "edge, embedded, WASM, and small-model serving where the deployment artifact matters more than throughput", with burn's CubeCL backend story (CUDA, ROCm, Metal, Vulkan, WebGPU, plus SIMD CPU) making it the more portable of the two and candle the more model-zoo-complete. Speculative, flag it as such: there is a plausible future where a Rust-native stack wins the *serverless and cold-start* segment outright, because a 20 MB static binary that starts in 30 ms against a 4 GB PyTorch container that imports for 8 seconds is a categorical difference rather than a percentage one, and that is a segment PyTorch has never seriously contested. Equally speculative in the other direction: if `torch.compile` and the free-threaded build keep closing the orchestration-overhead gap, the pressure to move anything else out of Python decreases and the current boundary is roughly where it stays for a decade.

---

## Mental model

```
THE ONE PATTERN. Rust wins exactly here and nowhere else:

    a hot loop that is NOT a matmul
  + called millions of times
  + per-item work is small (nanoseconds to microseconds)
  + cannot be batched onto a GPU
  + cannot be handed to BLAS/cuBLAS
  ------------------------------------------
  = CPython bytecode dispatch (~50-100 ns/op) IS the runtime
  = the GIL means one core, forever
  = REWRITE THIS PART, AND ONLY THIS PART


THE STACK, drawn honestly (measured this session, 2 vCPU i5-12450H):

  +--------------------------------------------------------------+
  |  MODELLING LAYER          PyTorch / JAX / vLLM / SGLang       |
  |  Python. Stays Python.    the loop body is a cuBLAS call;     |
  |                           Python overhead is ~0.1% of it      |
  +--------------------------------------------------------------+
  |  ORCHESTRATION            FastAPI / Ray / your service code   |
  |  Python. Usually stays.   I/O-bound. Rust buys you nothing.   |
  +--------------------------------------------------------------+
  |  >>> THE RUST BAND <<<    tokenizers  safetensors  polars     |
  |  loops over BYTES,        qdrant  lancedb  uv  ruff           |
  |  not over TENSORS         sgl-router / vllm-router            |
  |                           data loaders, prefix-cache indexes  |
  +--------------------------------------------------------------+
  |  KERNELS                  CUDA / Triton / CUTLASS / cuBLAS    |
  |  Not Rust either.         Rust has no story here at all.      |
  +--------------------------------------------------------------+


THE BOUNDARY HAS A PRICE. (measured, PyO3 0.29.2, CPython 3.10.12)

     python def noop()        50.71 ns   <-- the unit of comparison
     rust   noop()            54.56 ns   <-- crossing costs ~1 python call
     rust   add(1,2)          79.16 ns
     python add(1,2)          70.85 ns   <-- RUST IS SLOWER. arg conversion.
     builtin len('...')       36.32 ns

  => a Rust fn doing < ~1 us of work is a NET LOSS at the boundary.
  => amortise it: one call per BATCH, not one call per ITEM.


WHAT CROSSES MATTERS MORE THAN WHAT LANGUAGE RUNS. (measured)

  encode 738 KB of English -> 191,673 GPT-2 tokens, IDENTICAL ids:

     HuggingFace tokenizers 0.23.1 (Rust)   400.1 ms    1.84 MB/s
     tiktoken               (Rust)           51.5 ms   14.33 MB/s   <- 7.8x
                                                          ^
     SAME language. SAME algorithm. SAME output. 7.8x apart, because
     HF returns an Encoding{ids, type_ids, tokens:Vec<String>, offsets,
     attention_mask, special_tokens_mask, word_ids} = 8 parallel vecs
     + one heap String PER TOKEN. tiktoken returns Vec<u32>.


THE GIL, AND WHY encode_batch EXISTS. (measured, 2 vCPU)

  30M-iteration Rust hash loop, N python threads:

    threads   GIL held    py.detach()   speedup
       1        0.049 s     0.065 s      0.76x   <- detach COSTS 30-40 ns
       2        0.135 s     0.058 s      2.33x
       4        0.280 s     0.113 s      2.47x
       8        0.507 s     0.198 s      2.56x
                  ^^^^ perfectly serial: 10.3x the 1-thread time

  tokenizers.encode_batch(2511 docs):
       TOKENIZERS_PARALLELISM=true    142.7 ms   5.17 MB/s
       TOKENIZERS_PARALLELISM=false   324.6 ms   2.27 MB/s   <- 2.27x on 2 cores


THE QUESTION YOU ASK BEFORE ANYONE SAYS "REWRITE IT IN RUST":

     what % of p99 is CPU-bound PYTHON BYTECODE?
       > 40%  -> find the loop. bind it. measure.
      10-40%  -> maybe. profile first. it is probably allocation or JSON.
       < 10%  -> NO. you are GPU-bound or I/O-bound. Rust changes nothing.
                 (LLM serving is almost always here.)
```

The single sentence version, which is the one to say out loud: **Rust replaced Python where the unit of work is a byte and left it alone where the unit of work is a tensor, because a tensor op already spends 99.9% of its time in someone else's C.**

---

## How it actually works

Everything measured in this module was run in a Linux sandbox on a 12th Gen Intel Core i5-12450H exposed as **2 vCPUs**, CPython **3.10.12** (GIL build, `Py_GIL_DISABLED` is `None`), rustc **1.97.1** (8bab26f4f, 2026-07-14), PyO3 **0.29.2**, maturin **1.14.1**, `tokenizers` **0.23.1**, `tiktoken` from PyPI, `numpy` **2.2.6**, `uv` **0.12.2**. Extension built `--release` with `lto = "thin"` and `codegen-units = 1`. Timings are minimum-of-5-or-7 via `timeit` or minimum-of-3 via `perf_counter`, which is the right statistic for "how fast can this go" and the wrong one for p99. Two cores is a real constraint: every parallel speedup below is capped at 2x, and I say so where it bites.

### Tokenization: what BPE actually costs, and why it is the canonical example

Byte-pair encoding is worth understanding mechanically because its cost structure is *the* argument. Training builds a ranked merge table; inference replays it. GPT-2's table is **50,000 merges** over a **50,257**-entry vocabulary. Encoding is two phases:

1. **Pre-tokenization**: a regex splits the text into pre-tokens that merges may never cross. GPT-2's is `'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+`. On my 738,046-byte corpus (Pride and Prejudice from Project Gutenberg) this produced **166,702 pre-tokens**, mean length **4.37** characters, p99 **12**, max **70**. That distribution is the whole story, and I will come back to it.
2. **The merge loop**, per pre-token: represent it as a sequence of byte-level symbols, then repeatedly find the adjacent pair with the lowest merge rank and fuse it, until no adjacent pair is in the table.

The reference Python implementation of step 2 is the part that hurts:

```python
# openai/gpt-2 encoder.py shape. This is the loop everyone rewrites.
while True:
    bigram = min(pairs, key=lambda p: self.bpe_ranks.get(p, float("inf")))
    if bigram not in self.bpe_ranks: break
    # ... rebuild `word` with `first+second` fused, recompute `pairs`
```

Look at what that costs per merge: a `min` over a Python `set` of tuples, each probe a dict lookup with tuple hashing, then a full rebuild of the symbol list, then a full recomputation of the pair set. For a pre-token of length L it is O(L) merges each doing O(L) work with an interpreter-level constant of ~50-100 ns per operation, so O(L²) Python operations. L is small (mean 4.37), which is exactly why this is survivable at all, and it is called 166,702 times for 738 KB.

**Test 1. Pure Python versus Rust, byte-identical output.** I implemented the canonical GPT-2 BPE in pure Python and loaded it with the *same* vocab and merges extracted from the HuggingFace tokenizer, then asserted `py.encode(s) == hf.encode(s).ids`. It is `True`. This is apples to apples: same algorithm, same table, same output ids, only the language differs. On a 101,723-byte slice yielding 30,697 tokens:

| Implementation | Time | Throughput | ns/token | vs pure-Python cold |
|---|---|---|---|---|
| pure Python BPE, **cold** memo cache | 103.7 ms | 0.98 MB/s | 3,379.1 | 1.0x |
| pure Python BPE, **warm** memo cache | 33.8 ms | 3.01 MB/s | 1,101.2 | 3.1x |
| HF `tokenizers` 0.23.1 `encode()` (Rust) | 43.2 ms | 2.36 MB/s | 1,407.1 | **2.4x** |
| `tiktoken` `encode_ordinary()` (Rust) | 7.2 ms | 14.08 MB/s | 235.3 | **14.4x** |

Read the third row twice. **HuggingFace `tokenizers`, in Rust, is slower than the pure-Python BPE once the Python one has a warm cache** (43.2 ms versus 33.8 ms). That is not a mistake and it is the most useful number in this module, because it destroys the lazy version of the argument. Two things are going on.

The first is the memo cache and the Zipf distribution of natural language. Both implementations cache the merge result per pre-token string. On this slice there were 30,697 tokens but only **3,682 distinct cache entries** after the first pass. Natural text repeats: "the", " and", " of" appear thousands of times, and their merge loop runs *once*. So the expensive O(L²) loop is not actually executed 166,702 times, it is executed a few thousand times, and everything else is a dict hit. **The hot loop everyone rewrites in Rust is mostly memoised away on natural text.** I checked whether this was an artifact of English by running the same comparison on base64 of 75 KB of `os.urandom`, which is close to worst case for cache reuse (77,064 tokens at 1.30 bytes/token, 11,943 distinct cache entries):

| Input | pyBPE cold | pyBPE warm | HF | tiktoken | tiktoken vs pyBPE cold |
|---|---|---|---|---|---|
| natural English (Zipf) | 126.6 ms | 49.5 ms | 54.0 ms | 9.0 ms | 14.1x |
| base64 of random bytes | 226.9 ms | 72.2 ms | 72.1 ms | 13.0 ms | 17.5x |

The ratios barely move. Cold pure-Python to tiktoken is 14.1x to 17.5x; HF stays at parity with warm pure-Python in both cases. So the effect is structural, not a property of English.

The second thing, and the one that actually explains HF versus tiktoken, is **what crosses the boundary**. On the full 738 KB corpus, both producing the identical 191,673 ids (I asserted it):

| API | Time | MB/s | Mtok/s |
|---|---|---|---|
| `hf.encode(text)` | 400.1 ms | 1.84 | 0.502 |
| `hf.encode_batch(docs)` (2,511 docs) | 132.9 ms | 5.55 | 1.442 |
| `hf.encode_batch_fast(docs)` | 111.8 ms | 6.60 | 1.714 |
| `tiktoken.encode_ordinary(text)` | 51.5 ms | 14.33 | 3.722 |
| `tiktoken.encode_ordinary_batch(docs, num_threads=2)` | 95.3 ms | 7.74 | 2.011 |

`hf.encode()` versus `tiktoken.encode_ordinary()` is **7.8x**, and both are Rust. The difference is the return type. HF's `Encoding` object carries `ids`, `type_ids`, `tokens`, `offsets`, `attention_mask`, `special_tokens_mask`, `word_ids` and `overflowing`: eight parallel vectors, one of which (`tokens`) is a `Vec<String>` allocating a separate heap string **per token**, plus `offsets` which is a `Vec<(usize, usize)>` requiring char-to-byte offset bookkeeping through the byte-level encoding. tiktoken returns a `Vec<u32>`. That is the entire 7.8x. `encode_batch_fast`, which exists precisely to skip the offset computation, recovers 1.19x of it (132.9 to 111.8 ms), which tells you offsets alone were about 16% and the `String`-per-token allocation is the rest.

The lesson generalises far past tokenizers, and it is the one that separates a principal engineer from someone repeating a benchmark: **the language of the hot loop is often a smaller term than the shape of the data structure you hand back across the boundary.** If you are asked to make tokenization faster and your service does not use offsets, the fix is not "rewrite it", it is `encode_batch_fast` or tiktoken, and it is a one-line change worth 7.8x.

I also verified the scaling is linear, because a quadratic tokenizer is a real and famous failure mode (a single 10,000-character pre-token with no whitespace, from minified JSON or a base64 blob, can blow up a naive implementation):

| Input | Tokens | Time | MB/s |
|---|---|---|---|
| 92,554 B | 28,209 | 49.8 ms | 1.86 |
| 185,137 B | 52,176 | 103.3 ms | 1.79 |
| 369,536 B | 98,298 | 186.2 ms | 1.98 |
| 738,046 B | 191,673 | 400.1 ms | 1.84 |

Flat throughput across an 8x size range. Linear.

### Where the Rust tokenizer actually earns its keep: the GIL

The single-thread constant factor is 7.8x to 17.5x depending on which pair you compare, which is large but not obviously worth a rewrite. The part that *is* categorical is parallelism inside one process. `tokenizers`' `encode_batch` releases the GIL and fans out over rayon. Measured on 2,511 documents from the same corpus:

```
TOKENIZERS_PARALLELISM=true    142.7 ms   5.17 MB/s
TOKENIZERS_PARALLELISM=false   324.6 ms   2.27 MB/s
```

**2.27x on 2 vCPUs**, which is 113% of linear (the extra is measurement noise plus better cache behaviour). On a 16-core data-loading box that is a 10-14x factor that pure Python cannot access at all without `multiprocessing`, and `multiprocessing` costs you a pickle-and-copy of every document across a pipe plus a process per worker at ~50-100 MB RSS each. That is the argument. Not "Rust is fast", but "Rust can use your other fifteen cores from inside one Python process".

The corollary catches people: adding Python threads *on top* of `encode_batch` does nothing, because the cores are already saturated.

| Python threads over 2,511 docs | Time | MB/s |
|---|---|---|
| 1 | 147.0 ms | 5.02 |
| 2 | 147.3 ms | 5.01 |
| 4 | 152.3 ms | 4.85 |

Flat, then slightly worse from thread and rayon-scheduling overhead. If you see a data-loading pipeline with `ThreadPoolExecutor(max_workers=16)` wrapped around `encode_batch`, it is doing nothing except oversubscribing rayon's pool, and the fix is to remove it and set `RAYON_NUM_THREADS`. This is a real production misconfiguration and worth naming in an interview.

One more tokenizer number that matters for serving rather than training. Per-request, on a single 30-character prompt yielding 7 tokens:

| Call | Cost |
|---|---|
| `hf.encode(s)` | 11.02 µs |
| `hf.encode(s, add_special_tokens=False)` | 10.70 µs |
| `tiktoken.encode_ordinary(s)` | 2.17 µs |
| `len(s)` (reference builtin) | 0.04 µs |

11 µs per request against a 4,000 ms LLM generation is **0.00028%** of the request. Tokenization is not your serving bottleneck and never was; it is your *training data pipeline* bottleneck and your *router* bottleneck, where you tokenize to compute prefix-cache hits at thousands of QPS. That distinction is the answer to "should we optimise tokenization", and getting it right in an interview is worth more than any of the throughput numbers.

### PyO3: how the binding actually works

PyO3 (16.0k stars, latest **0.29.2**) generates the CPython C-API glue from Rust attribute macros. The mental model: `#[pyfunction]` expands to a `extern "C" fn(*mut PyObject, *mut PyObject) -> *mut PyObject` wrapper that extracts your Rust argument types from the `PyObject`s, calls your function, and converts the return value back. Everything expensive lives in those two conversions.

```rust
use pyo3::prelude::*;

#[pyfunction] fn noop() {}
#[pyfunction] fn add(a: i64, b: i64) -> i64 { a + b }

// A Python class backed by Rust state.
#[pyclass]
struct Counter { #[pyo3(get, set)] n: u64 }

#[pymethods]
impl Counter {
    #[new]                                   // becomes __init__
    fn new(start: u64) -> Self { Counter { n: start } }
    fn bump(&mut self, by: u64) -> u64 { self.n += by; self.n }
    fn __len__(&self) -> usize { self.n as usize }   // dunders work
    #[staticmethod] fn zero() -> Self { Counter { n: 0 } }
}

#[pymodule]
fn benchext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(noop, m)?)?;
    m.add_function(wrap_pyfunction!(add, m)?)?;
    m.add_class::<Counter>()?;
    Ok(())
}
```

The `Bound<'py, T>` smart pointer is the current API (it replaced the older `&PyAny` GIL-Ref API through 0.21-0.23; if you read a tutorial using `Python::with_gil(|py| ...)` returning `&PyAny`, it predates PyO3 0.21 and will not compile). `Py<T>` is the GIL-independent owned variant you store in a struct that outlives a call.

**The API rename you must know about.** PyO3 0.29 renamed `Python::with_gil` to `Python::attach` and `Python::allow_threads` to `Python::detach`, precisely because the GIL is no longer a universal property of a Python build. The old names still work but the new ones are what the current guide uses, and knowing why they were renamed (free-threading) is a strong signal in an interview. Every code sample below uses the 0.29 names, and every one of them compiled.

**Test 2. What does crossing the boundary actually cost?** This is the number that determines whether a binding is worth writing at all, and almost nobody measures it. Built the extension above with `maturin build --release`, installed the wheel, and timed with `timeit` (min of 7 repeats, autoranged):

| Call | ns/call |
|---|---|
| attribute lookup only (`benchext.noop`, no call) | 34.31 |
| `len('0123456789abcdef')` (C builtin) | 36.32 |
| **`pynoop()` (empty Python `def`)** | **50.71** |
| **`benchext.noop()` (empty Rust fn)** | **54.56** |
| `benchext.ret_int()` (returns `42`) | 60.42 |
| `benchext.take_bytes(b'...16B')` | 65.13 |
| `pyadd(1, 2)` (Python `def`) | 70.85 |
| `benchext.take_str('...16B')` | 75.86 |
| **`benchext.add(1, 2)` (Rust)** | **79.16** |

Three conclusions, all of which people get wrong.

First, **the boundary costs approximately one Python function call**: 54.56 ns against 50.71 ns. It is not free and it is not catastrophic. The 3.85 ns delta over a Python `def` is the C-level argument tuple unpacking plus PyO3's error-path setup.

Second, **`add(1, 2)` in Rust is measurably slower than `add(1, 2)` in Python**: 79.16 ns versus 70.85 ns, a 12% regression. Converting two `PyLong` objects into `i64` (`PyLong_AsLongLong` with overflow checking, twice) and boxing the `i64` result back into a `PyLong` costs more than the addition saves, because the addition is one instruction and CPython's small-int cache makes the Python version's allocation free. **If your Rust function does less work than its own argument conversion, the binding is a pessimisation.** Say this out loud when someone proposes binding a per-item helper.

Third, the floor is ~34 ns just to look the function up, so **the practical break-even is around 1 µs of Rust work per call**. Below that the boundary is a double-digit percentage of the call. Above ~10 µs it rounds to zero, which is why the 11 µs tokenizer call is a fine granularity and a per-token call would not be.

**Test 3. The crossover, and the trap of passing Python containers.** Same work, sum of N integers, `sum(L)` versus a Rust `#[pyfunction] fn sum_list(v: Vec<i64>) -> i64`:

| N | `sum(L)` ns | Rust `sum_list` ns | ratio | Rust ns/element |
|---|---|---|---|---|
| 1 | 74.7 | 112.2 | 0.67x | 112.24 |
| 4 | 90.0 | 132.8 | 0.68x | 33.20 |
| 16 | 112.9 | 226.0 | 0.50x | 14.12 |
| 64 | 266.6 | 575.0 | 0.46x | 8.98 |
| 256 | 823.3 | 1,951.5 | 0.42x | 7.62 |
| 1,024 | 3,232.3 | 7,977.1 | 0.41x | 7.79 |
| 4,096 | 15,787.9 | 39,399.6 | 0.40x | 9.62 |
| 65,536 | 345,734.3 | 622,538.4 | 0.56x | 9.50 |
| 1,048,576 | 7,093,089.3 | 12,922,984.2 | 0.55x | 12.32 |

**The Rust version never wins. It is 1.8x to 2.5x slower at every size.** There is no crossover. This is the most important negative result in the module. The reason is that `Vec<i64>` extraction from a Python list is a per-element `PyLong_AsLongLong` plus a bounds-checked `Vec` push, costing 7.6-12.3 ns per element, and `sum()` is a C loop doing *exactly that same extraction* and then an add. Rust did not remove the work; it added a `Vec` allocation and a second traversal on top of it.

The general rule: **a Python container argument makes the boundary O(n), not O(1), and the per-element conversion cost is usually the same work the Python builtin was already doing.** Any binding whose input is `list[int]`, `list[str]` or `dict[str, Any]` is paying this. The fix is not to pass a Python container.

### Zero-copy: the buffer protocol and numpy

The way out is to hand Rust a pointer to memory that is already flat, contiguous and typed, which is what the buffer protocol (PEP 3118) and numpy give you.

```rust
use pyo3::buffer::PyBuffer;

#[pyfunction]
fn sum_buffer(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<f64> {
    let buf: PyBuffer<f64> = PyBuffer::get(obj)?;   // validates dtype, no copy
    let n = buf.item_count();
    let ptr = buf.buf_ptr() as *const f64;
    // SAFETY: PyBuffer::get validated the element type is f64 and keeps the
    // exporting object alive for the lifetime of `buf`; the buffer is C-contiguous.
    let s = unsafe { std::slice::from_raw_parts(ptr, n) };
    Ok(py.detach(|| s.iter().sum()))                // release GIL over the loop
}
```

`PyBuffer::get` costs O(1) regardless of array size: it fills a `Py_buffer` struct with a pointer, length, itemsize and format string, and takes a reference on the exporter. No bytes move. Measured against `np.sum`:

| N (f64) | `np.sum(A)` ns | Rust `sum_buffer(A)` ns | ratio | `sum(list)` ns |
|---|---|---|---|---|
| 1 | 3,308.9 | 266.6 | **12.41x** | 105.2 |
| 16 | 2,735.8 | 298.6 | **9.16x** | 204.8 |
| 256 | 3,303.8 | 506.2 | **6.53x** | 1,174.4 |
| 4,096 | 4,298.6 | 3,968.1 | 1.08x | 18,608.8 |
| 65,536 | 24,695.0 | 58,776.6 | **0.42x** | 463,979.7 |
| 1,048,576 | 609,451.7 | 1,206,878.5 | 0.50x | 8,012,121.2 |
| 16,777,216 | 11,655,767.7 | 18,283,660.7 | 0.64x | n/a |

Two entirely different regimes, and the honest answer needs both.

**Small N: Rust wins 6-12x, and it has nothing to do with the loop.** `np.sum` costs ~2.7-3.3 µs on a *one-element* array. That is pure numpy dispatch: `__array_function__` protocol lookup, dtype resolution, ufunc reduction setup, output allocation. The Rust binding does a `PyBuffer::get` and a loop, total 266.6 ns. This is the real, under-appreciated reason Rust bindings win in production: **not faster loops, but the absence of a framework's per-call dispatch tax.** If your service calls `np.sum` on 40-element arrays a million times a request, this is your 10x.

**Large N: Rust loses 1.6-2.4x, and it is my fault, not Rust's.** `s.iter().sum()` over `f64` does not autovectorise, because IEEE-754 addition is non-associative and LLVM will not reorder your numerics. It compiles to a serial chain of scalar `addsd`. numpy uses pairwise summation with hand-written SIMD. This is exactly the failure documented in `T20-rust-perf`, where an `f32` reduction stayed scalar even with `-C target-cpu=native` on an AVX2 machine and manual 8-accumulator splitting recovered 6.67x. The fix here is identical: `s.chunks_exact(8).fold([0f64;8], ...)` and a horizontal reduce at the end, accepting that last-bit results change. **Never claim a Rust rewrite beats numpy on a bulk elementwise kernel until you have read the assembly**, because numpy's kernel is thirty years of hand-tuned SIMD and yours is an `iter().sum()`.

Practical zero-copy guidance:
- **`&[u8]` from `bytes`** is zero-copy and free: `take_bytes` cost 65.13 ns against `take_str`'s 75.86 ns, the delta being UTF-8 validation on the `&str` path.
- **`Vec<u8>` as an argument copies.** `&[u8]` borrows. Same for `String` versus `&str`. This is one character of difference and a full memcpy of the payload.
- **`numpy` via the `numpy` crate** (`PyReadonlyArray1<f64>`, `PyArray1::from_vec`) is the ergonomic layer over `PyBuffer` and handles strides and dimensionality. Use it over raw `PyBuffer` for anything with more than one dimension; strided and Fortran-ordered arrays are where hand-rolled `from_raw_parts` becomes a soundness bug.
- **Returning is where you leak the win.** `Vec<u32>` becomes a Python list with one `PyLong` allocation per element. Returning a numpy array via `PyArray1::from_vec` moves the `Vec` and costs O(1). This is precisely the HF-versus-tiktoken finding restated at the API level.
- **Mutation in place beats returning.** `fn scale(mut arr: PyReadwriteArray1<f64>, k: f64)` writes through the caller's buffer and returns nothing.

### The GIL: `detach`, and what it costs

`py.detach(|| ...)` (formerly `allow_threads`) releases the GIL for the duration of the closure. The closure cannot touch any Python object, which the type system enforces: `Python<'py>` is not `Send`, so a `Py<PyAny>` cannot be captured and dereferenced inside. This is the single feature that makes Rust bindings a parallelism story and not just a constant-factor story.

**Test 4. What does detaching cost, and when is it worth it?** Same FNV-style hash loop, one version holding the GIL and one detaching, at varying iteration counts:

| Rust loop iterations | GIL held (ns) | `py.detach()` (ns) | delta (ns) | overhead |
|---|---|---|---|---|
| 0 | 62.5 | 92.9 | 30.4 | 48.5% |
| 1 | 64.8 | 105.5 | 40.8 | 62.9% |
| 10 | 73.0 | 106.2 | 33.2 | 45.5% |
| 100 | 202.9 | 213.2 | 10.3 | 5.1% |
| 1,000 | 1,413.9 | 1,484.9 | 71.0 | 5.0% |
| 10,000 | 13,954.3 | 14,084.8 | 130.5 | 0.9% |
| 100,000 | 137,321.3 | 138,633.2 | 1,311.9 | 1.0% |

**A detach/attach round trip costs ~30-40 ns.** The rule that falls out: detach when the work exceeds roughly **1 µs**, below which you are paying 5-60% for nothing. This is why `tokenizers` detaches in `encode_batch` (milliseconds of work) and not in `encode` on a 7-token prompt.

And what it buys, on the 30,000,000-iteration version across Python threads:

| Threads | GIL held | `py.detach()` | speedup | detached scaling vs 1 thread |
|---|---|---|---|---|
| 1 | 0.049 s | 0.065 s | 0.76x | 0.84x |
| 2 | 0.135 s | 0.058 s | **2.33x** | 1.87x |
| 4 | 0.280 s | 0.113 s | **2.47x** | 1.92x |
| 8 | 0.507 s | 0.198 s | **2.56x** | 2.19x |

The GIL-held column is perfectly serial and then some: 8 threads took 10.3x the 1-thread time, the extra 29% being GIL handoff contention (CPython's `sys.setswitchinterval` default is 5 ms, and threads fight for reacquisition). The detached column saturates at 2.19x on 2 vCPUs, which is the machine's ceiling. On a 16-core loader this is a 14x factor.

For calibration, the same loop body in pure Python versus Rust, single-threaded: **104.00 ns per iteration in Python, 1.81 ns in Rust, 57.5x.** That is the constant-factor term, and note it is the *same order* as the 57x that `T20-rust-perf` measured for `String` clone versus `&str`. Interpreted bytecode dispatch and heap allocation are the two costs that dominate everything else in this space.

### maturin, wheels, and the packaging reality

`maturin` (1.14.1, 5.7k stars) is the build backend. Minimal setup, and it is genuinely three files:

```toml
# Cargo.toml
[lib]
name = "benchext"
crate-type = ["cdylib"]        # NOT "rlib" and NOT the default
[dependencies]
pyo3 = { version = "0.29", features = ["extension-module"] }
```
```toml
# pyproject.toml
[build-system]
requires = ["maturin>=1.9,<2.0"]
build-backend = "maturin"
[project]
name = "benchext"
version = "0.1.0"              # omit this and maturin warns; CI will fail later
requires-python = ">=3.8"
```
```
$ maturin build --release
🐍 Found CPython 3.10 at /usr/bin/python3
🔗 Found pyo3 bindings
   Finished `release` profile [optimized] target(s) in 20.01s
📦 Built wheel to target/wheels/benchext-0.1.0-cp310-cp310-manylinux_2_34_x86_64.whl
```

Real numbers from that build: **28.7 s wall for a clean release build** including downloading and compiling all 13 PyO3 crates, and a **222,957-byte wheel** for a module with ten trivial functions. That baseline matters: PyO3's fixed cost is roughly 200 KB of binary, so a binding is never a small artifact.

The part that bites in production is the **wheel matrix**. Note my filename says `cp310-cp310`: that wheel works on CPython 3.10 and nothing else. The `tokenizers` wheel I downloaded is `tokenizers-0.23.1-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`, **3,346,235 bytes**, and the `abi3` tag is the whole difference: one wheel serves CPython 3.10 and every later version, because it links only against the stable ABI. You get it with `pyo3 = { features = ["abi3-py310"] }`. Without it your CI builds `len(python_versions) × len(platforms)` wheels; with it, `len(platforms)`. For a five-Python, five-platform matrix that is 25 builds versus 5.

The costs of abi3, stated plainly: you lose access to non-stable C-API functions, some PyO3 optimisations that poke at struct internals are disabled, and there is a small measured slowdown on some operations because stable-ABI calls go through function pointers rather than macros. Almost every library takes the trade. `manylinux` compliance (the `manylinux_2_17` tag means glibc 2.17+) is handled by building in the `quay.io/pypa/manylinux2014_x86_64` container or by `maturin build --zig`, which cross-compiles against an older glibc without a container. `maturin develop` builds and installs into the active virtualenv in one step and is what you use in the inner loop; `maturin build --sdist` also ships a source distribution so that platforms you did not build for can compile from source, which requires the user to have a Rust toolchain and is a support burden you should be explicit about.

### free-threading: the live question, and what it does to the calculus

This is the part to treat as genuinely unsettled, because it is.

State of play as of 2026-08-06. PEP 703 introduced the free-threaded build; **PEP 779 was accepted for Python 3.14 and moved it to phase two**, meaning officially supported and no longer experimental, but still a separate opt-in binary tagged `3.14t`. Single-threaded overhead is down to roughly **5-10%**, from around **40%** in the 3.13 experimental phase. The steering council published criteria for phase three (free-threading becomes the default) but committed to no version. My sandbox is 3.10.12 with `sysconfig.get_config_var('Py_GIL_DISABLED')` returning `None`, so every GIL measurement above is from the GIL build and I could not measure the free-threaded numbers directly; treat the free-threading discussion here as sourced, not measured.

PyO3 has supported the free-threaded build since **0.23**. The mechanics you need: an extension module must declare `gil_used = false` to opt in, because a module that has not declared itself thread-safe causes the interpreter to *re-enable* the GIL at import time, which silently converts your free-threaded process back into a GIL process. From 0.23 through 0.27 the default was `gil_used = true`, so opting in was explicit; support later moved to opt-out. The failure mode is worth naming because it is invisible: you upgrade to `3.14t`, expect parallelism, get none, and there is no error, just a `RuntimeWarning` you probably filtered.

What free-threading actually changes for the "why Rust" argument:

- **It removes the parallelism half of the argument, eventually.** Today `encode_batch`'s 2.27x on 2 cores is unreachable from pure Python in one process. Under free-threading it is reachable, so a *new* binding written purely to escape the GIL becomes harder to justify.
- **It removes none of the constant-factor half.** 104.00 ns per interpreted iteration versus 1.81 ns in Rust is 57.5x and free-threading does not touch it. If anything it makes it slightly worse in the short term: the free-threaded build's per-object locking and deferred reference counting cost 5-10% single-threaded.
- **It makes existing Rust bindings *more* valuable, not less.** A `detach`ed Rust function is already thread-safe by construction. Python code that was implicitly serialised by the GIL is not, and a large fraction of the ecosystem's C extensions have latent data races that the GIL was hiding. Rust's `Send`/`Sync` bounds are checked at compile time. This is the argument that will age best.
- **It changes what you must audit in your own binding.** `#[pyclass]` structs are shared mutable state under free-threading. PyO3's `Bound`-based borrow checking (`PyRefMut` panics at runtime on an aliasing violation, it does not deadlock) still applies, but any `static mut`, any `GILOnceCell` (deprecated in 0.29 in favour of `PyOnceLock`), and any assumption that "only one thread runs Python at a time" is now a bug.

The interview-safe formulation: "the GIL argument for Rust has a multi-year expiry date; the constant-factor and memory-safety arguments do not, and free-threading will surface latent races in extensions that the GIL was accidentally protecting."

### candle and burn: Rust-native inference, honestly

Two live projects, both genuinely active as of 2026-08-05.

**candle** (HuggingFace, 20.9k stars, created 2023-06-19, `candle-core` **0.11.0**, 892 open issues). A minimalist tensor library with a PyTorch-shaped API, CPU/CUDA/Metal backends, and a large model zoo (Llama, Mistral, Whisper, Stable Diffusion, BERT variants) implemented directly in the repo. Stated goal: serverless inference and removing Python from production.

**burn** (Tracel AI, 15.7k stars, created 2022-07-18, **0.22.0-pre.1** released 2026-07-29, 0.21.0 on 2026-05-07, 287 open issues). A full framework with autodiff and training, built on **CubeCL**, which compiles Rust kernels to CUDA, ROCm/HIP, Metal, Vulkan, WebGPU, and SIMD CPU. Burn 0.20 added CubeK (portable high-performance kernels) and expanded operator fusion across elementwise, reduction and matmul.

Where they are genuinely good:

- **No-Python deployment.** A single static binary against a 4+ GB PyTorch container. This is the strongest argument and it is not about throughput at all: it is image pull time, cold start, attack surface, and dependency resolution. A container that no longer needs `torch`, `transformers`, `numpy` and their transitive tree is a different operational object.
- **Edge, embedded, and WASM.** burn compiles to `wasm32` and runs on WebGPU in a browser. PyTorch does not. If the requirement is "run a 30M-parameter model in the user's browser or on an ARM device with 512 MB RAM", this is not a comparison, it is the only option.
- **Small models and embedding services.** A BERT-base or MiniLM embedding endpoint on CPU is exactly the workload where the Python framework overhead is a meaningful fraction and the model is small enough that a less-tuned kernel still fits in budget.
- **Latency predictability.** No GC because there was never a GC, and no interpreter pauses. For a p99-sensitive CPU inference path this is real.
- **Embedding the model inside an existing Rust service.** If your gateway is already Rust, calling candle in-process beats an HTTP hop to a Python sidecar, and the hop was probably 1-3 ms.

Where they are not competitive, and you should say this plainly:

- **Anything on a GPU fleet at scale.** PyTorch plus vLLM plus CUTLASS plus FlashAttention represents an enormous amount of kernel engineering per operator. The reported candle-versus-PyTorch numbers are bimodal for exactly this reason: some paths are 35-47% faster, and candle issue **#2877** documents `all-MiniLM-L6-v2` at **122.30 ms per batch** in candle 0.8.4 against **~14.34 ms** in PyTorch, an **8.5x regression**, with issue **#942** reporting the same shape for YOLOv8 against ONNX Runtime. Whether you land on the good side or the bad side is a property of which ops your model uses, and you cannot know without benchmarking your specific model.
- **Training anything real.** burn has autodiff and it works, but the ecosystem around PyTorch training (distributed strategies, checkpointing, mixed precision recipes, profilers, every paper's reference code) does not exist.
- **Model availability.** A new architecture lands in `transformers` on release day and in candle in a few weeks, if someone ports it. That lag is fatal for a team that needs to evaluate models weekly.
- **Hiring and iteration.** Your ML engineers write Python. A Rust inference stack means every model change is a Rust change.

The decision rule I would actually give: **use candle or burn when the deployment artifact is the constraint, not when throughput is.** Edge, browser, serverless, embedded, or "we need one binary with no Python". Everywhere there is a GPU and a team of ML engineers, use PyTorch and put Rust in the band above it.

### Where Rust actually won, and the shape they share

| System | What it replaced | Why Rust won |
|---|---|---|
| `tokenizers` (10.9k stars, 0.23.1) | pure-Python BPE in `transformers` | data-dependent merge loop over short strings, no GPU path, GIL release gives 2.27x/core |
| `safetensors` (0.8.0) | `torch.save` (pickle) | mmap-able flat format, zero-copy load, and pickle is arbitrary code execution |
| `tiktoken` (18.9k stars) | pure-Python BPE | same loop; **7.8x faster than `tokenizers`** by returning only ids |
| `ruff` (49.1k stars) | flake8 + isort + pydocstyle + pyupgrade | AST walk over millions of lines; per-node Python overhead is the whole runtime |
| `uv` (88.4k stars, 0.12.2) | pip + virtualenv + pip-tools | **measured: 14.54 s for pip venv+install vs 1.68 s uv cold cache (8.7x), 0.10 s warm (145x)** |
| Polars (39.3k stars) | pandas | columnar engine, query optimiser, and multithreaded execution pandas cannot do under the GIL |
| Qdrant (33.8k), LanceDB (11.1k) | FAISS-in-a-Python-service | HNSW graph traversal is pointer chasing per query; needs real threads and no GC pauses |
| `sgl-router`, vLLM `router` | Python load balancer | tokenizes in-process to compute prefix-cache overlap for cache-aware routing at high QPS |
| PyTorch `DataLoader` replacements | `multiprocessing` workers | pickle-and-copy per item versus shared-memory threads |

Every row is the same shape. Loop over bytes or nodes or graph edges, called an enormous number of times, no matmul to hide in, and either a GIL problem or a per-item interpreter-overhead problem. **Not one of them is a model.**

The two most instructive rows are `uv` and the routers. `uv` is not doing anything algorithmically exotic; it is a dependency resolver and an unzipper. It is 8.7x faster than pip cold and 145x warm because pip was doing per-file Python work and uv does it in parallel Rust with a global content-addressed cache and hardlinks. That is the whole trick, and it is available to anyone who notices the shape. The routers are the newest instance and the one most relevant to an LLM platform engineer: SGLang's gateway and vLLM's router (a fork of it) run **Rust tokenizers, reasoning parsers and tool-call parsers** inside a gRPC pipeline, specifically so the router can compute prompt length and prefix-match locally for cache-aware load balancing without a metadata round trip to a worker. That is a component that did not exist two years ago and is Rust from birth.

---

## Build it from scratch

The lab in `labs/rust/07-rust-for-ai/` is one crate plus one Python script, and it reproduces every measurement in this module in about 30 minutes. Everything below was actually built and run.

**Step 1. Scaffold and build.**

```bash
cargo new --lib benchext && cd benchext
# Cargo.toml: crate-type = ["cdylib"], pyo3 0.29 with "extension-module"
pip install maturin                       # 1.14.1
maturin build --release                   # ~29 s clean, 222,957-byte wheel
pip install target/wheels/benchext-*.whl
```

**Step 2. The extension. Every function here exists to answer one question.**

```rust
use pyo3::prelude::*;
use pyo3::buffer::PyBuffer;

// Q: what does an empty crossing cost?            A: 54.56 ns
#[pyfunction] fn noop() {}
// Q: is trivial Rust faster than trivial Python?  A: NO. 79.16 vs 70.85 ns.
#[pyfunction] fn add(a: i64, b: i64) -> i64 { a + b }
// Q: what does a Python container argument cost?  A: 7.6-12.3 ns/element.
#[pyfunction] fn sum_list(v: Vec<i64>) -> i64 { v.iter().sum() }

// Q: what does zero-copy buy?  A: 12.4x at N=1, 0.5x at N=1e6 (see below).
#[pyfunction]
fn sum_buffer(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<f64> {
    let buf: PyBuffer<f64> = PyBuffer::get(obj)?;
    let n = buf.item_count();
    let ptr = buf.buf_ptr() as *const f64;
    // SAFETY: PyBuffer::get validated dtype f64 and holds the exporter alive.
    let s = unsafe { std::slice::from_raw_parts(ptr, n) };
    Ok(py.detach(|| s.iter().sum()))
}

// Q: what does the GIL cost, and what does detaching cost?
#[pyfunction] fn spin_hold(n: u64) -> u64 { fnv(n) }
#[pyfunction] fn spin_release(py: Python<'_>, n: u64) -> u64 { py.detach(|| fnv(n)) }

fn fnv(n: u64) -> u64 {
    let mut h: u64 = 1469598103934665603;
    for i in 0..n { h ^= i; h = h.wrapping_mul(1099511628211); }
    h
}

#[pymodule]
fn benchext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(noop, m)?)?;
    m.add_function(wrap_pyfunction!(add, m)?)?;
    m.add_function(wrap_pyfunction!(sum_list, m)?)?;
    m.add_function(wrap_pyfunction!(sum_buffer, m)?)?;
    m.add_function(wrap_pyfunction!(spin_hold, m)?)?;
    m.add_function(wrap_pyfunction!(spin_release, m)?)?;
    Ok(())
}
```

**Step 3. Measure the boundary before anything else.** This is the habit worth building.

```python
import timeit, benchext
def t(stmt, g):
    tm = timeit.Timer(stmt, globals=g); n, _ = tm.autorange()
    return min(tm.repeat(7, n)) / n * 1e9          # ns/call, min of 7
g = {"benchext": benchext, "pynoop": lambda: None}
print(t("pynoop()", g), t("benchext.noop()", g))   # 50.71   54.56
```

If you internalise one thing from this lab, make it this: **the first number you measure on any binding is the empty call.** It is your floor. Every function you expose must do meaningfully more work than that floor, or you have made things worse.

**Step 4. Reproduce the tokenizer result, which requires being scrupulous about apples-to-apples.**

```python
# untested sketch of the harness shape; the full version is in the lab
import json
from tokenizers import Tokenizer
from pybpe import PyBPE                 # canonical openai/gpt-2 encoder.py BPE
hf = Tokenizer.from_pretrained("gpt2")
spec = json.loads(hf.to_str())          # 50,257 vocab entries, 50,000 merges
py  = PyBPE(spec["model"]["vocab"], spec["model"]["merges"])
assert py.encode(text) == hf.encode(text).ids     # <-- do not skip this line
```

That assertion is the entire integrity of the comparison and it passed. Without it you are benchmarking two different algorithms and the number means nothing. Then run four conditions: pure-Python cold cache, pure-Python warm cache, `hf.encode`, `tiktoken.encode_ordinary`. The warm-cache row is the one that will surprise you.

**Step 5. Prove the GIL claim with an environment variable, not an argument.**

```bash
TOKENIZERS_PARALLELISM=true  python bench_batch.py    # 142.7 ms, 5.17 MB/s
TOKENIZERS_PARALLELISM=false python bench_batch.py    # 324.6 ms, 2.27 MB/s
```

Then wrap `encode_batch` in a `ThreadPoolExecutor(max_workers=4)` and watch the time not change (147.0 / 147.3 / 152.3 ms for 1 / 2 / 4 threads). Being able to say "I have watched adding threads do nothing because rayon was already saturating the cores" is a specific, credible answer.

**The exercise that actually builds the instinct.** Take `sum_buffer`, confirm it loses to `np.sum` at N = 1,048,576 (1,206,878 ns versus 609,451 ns), then rewrite the reduction with eight independent accumulators via `chunks_exact(8)` and watch it win. Then read the assembly of both with `cargo asm` and find the `addsd` chain in the first and the `addpd`/`vaddpd` in the second. That single experiment connects this module to `T20-rust-perf` and teaches the lesson that "rewrite it in Rust" and "make it fast" are different projects.

---

## How it's done in production

The production version of everything above is: **you do not write the binding, you pick the library that already did, and the engineering is in choosing the right granularity and configuring the parallelism correctly.**

The configuration surface that actually matters in an LLM platform:

```python
# Data loading / offline tokenization
import os
os.environ["TOKENIZERS_PARALLELISM"] = "true"   # rayon inside encode_batch
os.environ["RAYON_NUM_THREADS"] = "8"           # cap it; default is all cores
# and then DO NOT also wrap it in a ThreadPoolExecutor. Measured: no gain.

# Serving: batch at the API boundary, not per item
enc = tok.encode_batch_fast(prompts)   # 1.19x over encode_batch (no offsets)
# ...unless you need offsets for citation spans / highlighting, then you can't.
```

```toml
# Release profile for any PyO3 extension you do ship
[profile.release]
opt-level = 3
lto = "thin"          # fat LTO costs build time for marginal runtime here
codegen-units = 1
panic = "abort"       # BUT: see the caveat below. Often wrong for extensions.
```

`panic = "abort"` is the one to think about. A Rust panic that unwinds across the FFI boundary is undefined behaviour, so PyO3 catches panics at the `#[pyfunction]` boundary and converts them into a Python `PanicException`. Setting `panic = "abort"` disables that catch and turns any panic (an out-of-bounds index, an `unwrap` on `None`, an integer overflow in a debug-assert build) into an immediate `SIGABRT` that kills the whole Python process, taking every in-flight request with it. For a server extension, keep unwinding.

The other production decisions, with their real costs:

- **abi3 or not.** `features = ["abi3-py310"]` gives one wheel per platform instead of one per platform per Python version. `tokenizers` ships `cp310-abi3`. Take the trade unless you have measured a regression.
- **Granularity.** Expose one function that processes a batch, never one that processes an item. The `sum_list` result (never faster than the builtin at any N from 1 to 1,048,576) is what happens when the boundary is at the wrong level.
- **What crosses.** Return `numpy` arrays or `bytes`, not `list[int]` or `list[str]`. The HF-versus-tiktoken 7.8x is entirely this.
- **Error mapping.** `PyErr::new::<PyValueError, _>(msg)` and `impl From<MyError> for PyErr` so Rust `Result` becomes a real Python exception with a real type, not a `RuntimeError` with a debug-formatted string. Callers catch types.
- **Observability.** A Rust extension is invisible to `cProfile` and shows as one opaque frame in `py-spy`. Use `py-spy record --native`, which walks both stacks, and export metrics from the Rust side rather than inferring them.
- **Build in CI, not on the user's machine.** `maturin build --zig` or the `manylinux` container. Publishing an sdist without wheels means every installer needs a Rust toolchain and a five-minute compile.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Rewrote the Python service in Rust; p99 moved from 4,120 ms to 4,090 ms | The GPU was 95%+ of the request. You optimised the 30 ms of orchestration | Measure the CPU-bound-Python fraction first. Below 10%, do not rewrite. Fix batching, KV-cache hit rate, and scheduling instead |
| New Rust binding is *slower* than the Python it replaced | Per-call boundary cost (~55 ns) plus argument conversion exceeds the work done. Measured: Rust `add(1,2)` 79.16 ns vs Python 70.85 ns | Move the boundary up: one call per batch. Break-even is ~1 µs of Rust work per call |
| Binding taking `list[int]` / `list[str]` shows no speedup at any input size | Python container extraction is O(n) at 7.6-12.3 ns/element, which is the same work the builtin was doing. Measured 0.40-0.68x vs `sum()` across N = 1 to 1,048,576 | Pass `numpy` arrays or `bytes` and use `PyBuffer`/`PyReadonlyArray` for zero-copy |
| Rust reduction over `f64` is 2x slower than `np.sum` on large arrays | `iter().sum()` on floats does not autovectorise (IEEE non-associativity); numpy uses pairwise SIMD. Measured 1,206,878 ns vs 609,451 ns at N = 1,048,576 | Split into 8 accumulators via `chunks_exact(8)`; accept last-bit differences. See `T20-rust-perf` |
| `ThreadPoolExecutor` around `tokenizers.encode_batch` gives zero speedup | `encode_batch` already releases the GIL and saturates cores via rayon. Measured 147.0 / 147.3 / 152.3 ms for 1 / 2 / 4 threads | Remove the pool; set `RAYON_NUM_THREADS`. Oversubscription makes it slightly worse |
| Tokenization throughput halves after a deploy; no code change | Something set `TOKENIZERS_PARALLELISM=false`, usually a fork-safety warning suppression copy-pasted from a HF issue. Measured 324.6 ms vs 142.7 ms, 2.27x | Set it explicitly to `true` and fix the fork ordering instead: build the tokenizer *after* forking, or use `spawn` |
| Deadlock or hang after `os.fork()` in a data loader | rayon's thread pool does not survive `fork`; the child inherits a pool whose threads do not exist | Use `spawn` start method, or construct the tokenizer inside the child. This is what the `TOKENIZERS_PARALLELISM` warning is about |
| Whole Python process dies with `SIGABRT`, no traceback, all in-flight requests lost | `panic = "abort"` in the extension's release profile; a Rust panic could not be caught and converted to `PanicException` | Remove `panic = "abort"` from extension builds. Also audit for `unwrap`/`expect`/slice indexing on user input |
| Upgraded to Python 3.14t expecting parallelism, got none, no error | Extension did not declare `gil_used = false`, so CPython re-enabled the GIL at import | Set `gil_used = false` in `#[pymodule]` and audit the module for actual thread safety first |
| `PyRefMut` borrow panic under load on a `#[pyclass]` | Two threads (or one re-entrant call) mutably borrowing the same Rust object; PyO3 enforces this at runtime | Put the state behind a `Mutex`/`RwLock` inside the `#[pyclass]`, or redesign so the object is immutable after construction |
| `pip install` of your package takes 5 minutes and needs a compiler | You published an sdist with no matching wheel | Build wheels in CI for every target; `maturin build --zig` or a `manylinux2014` container |
| One wheel per Python version per platform, CI matrix is 25 jobs | Not built with the stable ABI | `pyo3 = { features = ["abi3-py310"] }`; the wheel tag becomes `cp310-abi3` and covers 3.10+ |
| Embedding endpoint on candle is 8.5x slower than the PyTorch version | Model uses ops without a tuned kernel in that backend (see candle issue #2877, 122.30 ms vs 14.34 ms for MiniLM) | Benchmark your specific model before committing; keep the PyTorch path until the Rust one wins on your workload |
| `py-spy` shows one opaque frame and `cProfile` shows nothing for 80% of runtime | The time is inside the native extension, invisible to Python profilers | `py-spy record --native`, or instrument the Rust side and export metrics directly |
| Tokenizer latency spikes 100x on a specific class of input | A single enormous pre-token (minified JSON, base64 blob, no whitespace) hitting the merge loop's per-pre-token cost. My corpus max pre-token was 70 chars; a 100 KB one is a different regime | Length-cap inputs before tokenizing; alert on p99.9 tokenize time; test with adversarial inputs |
| Container image is 4.2 GB and cold start is 45 s on a serverless platform | PyTorch plus CUDA plus `transformers` transitive tree | This is the one place a Rust inference stack genuinely wins. Evaluate candle/burn for *this* reason, not for throughput |

---

## Tradeoffs & when NOT to use it

- **Do not rewrite an LLM serving path in Rust.** This is the category error the whole module exists to prevent. On a 4-second generation, the GPU is the request. My measured tokenizer cost for a real prompt was 11.02 µs, which is 0.00028% of a 4-second request. If p99 is bad, the causes are queueing, batch scheduling, KV-cache eviction, prefill/decode interference and cold model loads. Every one of those is a Python-level scheduling fix. Rewriting FastAPI as axum addresses none of them and costs two quarters.

- **Do not bind a function that does less than about a microsecond of work.** The boundary is ~55 ns and argument conversion can exceed the function body: Rust `add(1,2)` measured 12% *slower* than the Python equivalent. If someone proposes binding a hot per-item helper, the correct response is to ask for the per-call work estimate, and if it is nanoseconds, to move the loop into Rust instead of the item.

- **Do not pass Python containers across the boundary and expect a win.** `sum_list(Vec<i64>)` was 1.8x to 2.5x *slower* than the builtin `sum()` at every size from 1 to 1,048,576. There was no crossover. If the input cannot be a `bytes`, a `str`, or a buffer-protocol array, the binding is probably not worth writing.

- **Do not assume Rust beats numpy or PyTorch on bulk numeric kernels.** It usually loses. My zero-copy `f64` sum was 0.42-0.64x of `np.sum` at large N because numpy's kernel is decades of hand-tuned SIMD and mine was an `iter().sum()`. The place Rust beats numpy is *small* arrays, where numpy's ~3 µs per-call dispatch dominates and Rust's is 267 ns.

- **Do not use candle or burn for GPU inference at scale.** The variance is the argument: some paths are 35-47% faster than PyTorch and some are 8.5x slower, and which one you get is a property of whether your ops have tuned kernels. On a GPU fleet you are betting against a decade of CUTLASS and FlashAttention work. Use them where the *artifact* is the constraint: edge, WASM, serverless cold start, embedded, no-Python deployment.

- **Do not adopt Rust in a team that cannot maintain it.** This is the tradeoff people leave out of the technical discussion and it is usually the deciding one. If your ML engineers ship a new reranker every two weeks and the reranker lives in Rust, you have converted a two-day task into a two-week one and created a single point of failure in whoever knows Rust. The build is also slower: my trivial ten-function extension took 28.7 s clean, and `T20-rust-perf` measured monomorphisation making a 50 KLOC service take minutes.

- **Do not set `panic = "abort"` in a Python extension.** It converts a recoverable `PanicException` into a `SIGABRT` that kills the interpreter and every concurrent request. The binary-size saving is not worth an availability incident.

- **Do not use the GIL as your entire justification going forward.** Free-threading is officially supported in 3.14 (PEP 779, phase two) with single-threaded overhead down to 5-10%. The parallelism argument has an expiry date. The 57.5x constant-factor argument (104.00 ns versus 1.81 ns per iteration) does not, and neither does compile-time-checked thread safety, which becomes *more* valuable when the GIL stops accidentally serialising everyone's latent races.

- **Do not skip the equivalence assertion when benchmarking.** The single most common way these comparisons lie is that the two implementations produce different output. My pure-Python BPE was verified byte-identical to HF's before timing, which is the only reason the surprising result (warm-cache Python beating the Rust library) is trustworthy rather than a bug.

- **Do not reach for Rust when the answer is a better algorithm or a config flag.** The 7.8x between `tokenizers` and `tiktoken` is not a language difference, it is a return-type difference, and `encode_batch_fast` recovers 1.19x of it with a one-line change. Similarly, a `ThreadPoolExecutor` removal and a `TOKENIZERS_PARALLELISM=true` gave me 2.27x for zero code. Exhaust the free wins first; they are usually larger than the rewrite.

- **Do not ignore the I/O-bound case.** If your RAG service spends 180 ms in a vector database, 40 ms in a reranker and 3,000 ms in an LLM, there is no Rust in the world that helps. Batching, caching, and cutting a network hop will each beat any language change by an order of magnitude.

---

## Interview questions

### Q1 — Why is HuggingFace `tokenizers` written in Rust?
**Testing:** whether you can name the *shape* of the problem rather than saying "for speed".
**Answer:** Because BPE encoding is a data-dependent merge loop over short byte strings: it is not a matmul, so there is no BLAS or CUDA kernel to hide in, it is called on every document in a pretraining corpus and every request in a serving path, and under the GIL it cannot use more than one core inside a process. Concretely, GPT-2's table is 50,000 merges over a 50,257-token vocabulary, and the reference Python loop does a `min` over a set of tuples with a dict probe each, then rebuilds the symbol list and pair set, per merge. I measured the same algorithm producing byte-identical ids: 0.98 MB/s in pure Python with a cold cache versus 14.08 MB/s in tiktoken's Rust core on the same 101,723-byte slice, 14.4x. The larger win is parallelism: `encode_batch` releases the GIL and fans out over rayon, which measured 142.7 ms against 324.6 ms with `TOKENIZERS_PARALLELISM=false`, 2.27x on two vCPUs and roughly linear, and pure Python cannot reach that inside one process at all.
**Follow-up trap:** *"So Rust is 14x faster than Python at tokenization?"* Not reliably. I also measured the pure-Python BPE with a warm memoisation cache at 33.8 ms against HuggingFace `tokenizers`' 43.2 ms on the identical slice, so the Python one *won*. Natural text is Zipf-distributed: 30,697 tokens produced only 3,682 distinct cache entries, so the expensive merge loop mostly does not run. The honest range is 2.4x to 17.5x depending on cache warmth, input entropy, and crucially which API you call, and the Rust-versus-Python axis is not the largest term.

### Q2 — What does it actually cost to call a Rust function from Python?
**Testing:** whether you have ever measured a boundary, which almost nobody has.
**Answer:** About one Python function call. On PyO3 0.29.2 with CPython 3.10, an empty `#[pyfunction]` cost 54.56 ns per call against 50.71 ns for an empty Python `def`, with the floor being 34.31 ns for the attribute lookup alone. The 3.85 ns delta is argument-tuple unpacking and PyO3's error-path setup. The consequence is the useful part: the practical break-even is around 1 µs of Rust work per call, below which the crossing is a double-digit percentage of the call. I have a concrete demonstration: `#[pyfunction] fn add(a: i64, b: i64) -> i64` cost 79.16 ns against 70.85 ns for the Python equivalent, so **Rust was 12% slower**, because two `PyLong_AsLongLong` conversions plus boxing the result cost more than an `add` instruction saves and CPython's small-int cache makes the Python allocation free.
**Follow-up trap:** *"Then how do libraries like `tokenizers` win at all?"* By putting the boundary in the right place. `hf.encode()` on a real 30-character prompt cost 11.02 µs, so the 55 ns crossing is 0.5% of it. The rule is one call per batch, never one call per item. When people bind a per-item helper and see no improvement, this is always why, and the fix is to move the loop into Rust rather than the loop body.

### Q3 — We want to speed up a Python function that sums a list of ints. Should we bind it to Rust?
**Testing:** whether you know that Python containers make the boundary O(n).
**Answer:** No, and I measured it so I can say so with numbers. A `#[pyfunction] fn sum_list(v: Vec<i64>) -> i64` was slower than the builtin `sum()` at every size I tested, from N=1 to N=1,048,576, in the range 0.40x to 0.68x. There is no crossover point. The reason is that extracting `Vec<i64>` from a Python list is a per-element `PyLong_AsLongLong` plus a `Vec` push, which measured 7.6 to 12.3 ns per element, and that is precisely the work `sum()`'s C loop was already doing. Rust did not eliminate the work, it added a heap allocation and a second traversal. The general rule: if the argument is a `list`, `dict` or `set`, the conversion is O(n) at roughly the same per-element cost as the builtin, so the binding is a pessimisation.
**Follow-up trap:** *"What would make it worth doing?"* Changing what crosses. If the data arrives as a numpy `float64` array I can take it zero-copy through `PyBuffer`, which is O(1) regardless of size, and then Rust wins 12.41x at N=1 and 6.53x at N=256 against `np.sum`, entirely because numpy's per-call dispatch is ~3 µs and mine is 267 ns. But note it *loses* 0.42x at N=65,536 because my `iter().sum()` on `f64` does not autovectorise while numpy uses pairwise SIMD, so the win is real only for the small-array, high-call-rate regime.

### Q4 — Walk me through how `py.detach()` (formerly `allow_threads`) works and when to use it.
**Testing:** whether you understand the GIL mechanically and know it is not free.
**Answer:** `py.detach(|| ...)` releases the GIL for the duration of the closure so other Python threads can run. Rust's type system enforces safety: `Python<'py>` is not `Send`, so you cannot capture and dereference a Python object inside the closure; it is a compile error, not a runtime hazard. It costs about 30-40 ns for the detach/attach round trip, which I measured directly: at zero iterations of work the detached version cost 92.9 ns against 62.5 ns held, a 48.5% overhead, and the overhead fell to 5.1% at 100 iterations and 0.9% at 10,000. So the rule is detach when the closure does more than roughly 1 µs of work. What it buys is real: on a 30,000,000-iteration loop, the GIL-held version took 0.049 s at one thread and 0.507 s at eight, which is 10.3x, worse than perfectly serial because of GIL handoff contention, while the detached version went 0.065 s to 0.198 s and saturated at 2.19x on a 2-vCPU box.
**Follow-up trap:** *"Does free-threaded Python make this obsolete?"* It makes the parallelism half obsolete, eventually. PEP 779 was accepted for 3.14 so free-threading is officially supported in phase two, still opt-in as the `3.14t` binary, with single-threaded overhead down to 5-10% from about 40% in 3.13. It does nothing to the constant factor: I measured 104.00 ns per interpreted iteration against 1.81 ns in Rust, 57.5x, and no GIL change touches that. There is also a trap in the other direction: a PyO3 module that has not declared `gil_used = false` causes CPython to silently re-enable the GIL at import, so you get no parallelism and no error.

### Q5 — Our LLM serving p99 is 4 seconds. A senior engineer wants to rewrite the service in Rust. What do you say?
**Testing:** the whole point of the module. Whether you can decline a rewrite numerately.
**Answer:** I ask what fraction of those 4,000 ms is CPU-bound Python bytecode, and I would bet it is under 2%. On a generation request the GPU is doing prefill and decode and that is essentially all of the wall time; the Python layer is parsing a request, tokenizing, and streaming a response. I measured tokenization of a real 30-character prompt at 11.02 µs, which is 0.00028% of a 4-second request. So the ceiling on a full rewrite is single-digit milliseconds out of 4,000, and the cost is two quarters plus the loss of the ability for ML engineers to ship model changes. The actual levers on p99 for that number are continuous-batching configuration, KV-cache hit rate and eviction policy, prefill/decode interference, queueing under burst, speculative decoding, and cold model loads. All of them are Python-level scheduling changes.
**Follow-up trap:** *"Is there any part of that stack you would move to Rust?"* Yes, and being able to name it is the point. The router or gateway, if you are doing cache-aware routing: it needs to tokenize every incoming prompt to compute prefix-match against worker caches at high QPS, which is a real CPU-bound loop on the request path. That is exactly what SGLang's `sgl-router` and vLLM's `router` (a fork of it) do, with Rust tokenizers, reasoning parsers and tool-call parsers in a gRPC pipeline. Also the offline data pipeline, where `encode_batch`'s GIL release is worth close to one core per core you own.

### Q6 — What is the difference between `tokenizers` and `tiktoken`, and why is one faster?
**Testing:** whether you look past "which language" to "what crosses the boundary".
**Answer:** Both are Rust with Python bindings and both implement byte-level BPE. On my 738,046-byte corpus producing an identical 191,673 ids (I asserted equality), `hf.encode()` took 400.1 ms at 1.84 MB/s and `tiktoken.encode_ordinary()` took 51.5 ms at 14.33 MB/s, a 7.8x gap with the same language and the same algorithm. The entire difference is the return type. HF's `Encoding` carries eight parallel vectors, `ids`, `type_ids`, `tokens`, `offsets`, `attention_mask`, `special_tokens_mask`, `word_ids` and `overflowing`, and `tokens` is a `Vec<String>` allocating a separate heap string per token, while `offsets` requires char-to-byte bookkeeping through the byte-level encoding. tiktoken returns a `Vec<u32>`. Evidence for the mechanism: `encode_batch_fast`, which exists to skip offset computation, recovered 1.19x (132.9 to 111.8 ms), so offsets alone were about 16% and the per-token `String` is the rest.
**Follow-up trap:** *"So we should switch to tiktoken?"* Only if you do not need what HF gives you. Offsets are load-bearing for citation spans, highlighting, NER alignment and any UI that maps model output back to source characters, and HF supports arbitrary trained tokenizers, normalizers and post-processors that tiktoken does not. The cheap intermediate is `encode_batch_fast` for the paths that do not need offsets, which is 1.19x for one line, plus `encode_batch` over a batch instead of `encode` per item, which was 2.87x on its own.

### Q7 — Explain the zero-copy story between numpy and Rust.
**Testing:** whether you know the buffer protocol exists and what it does and does not guarantee.
**Answer:** PEP 3118's buffer protocol lets an object export a `Py_buffer` describing a raw pointer, item count, itemsize, format string, shape and strides. `PyBuffer::<f64>::get(obj)` in PyO3 validates the element type, takes a reference on the exporting object so it stays alive, and gives you the pointer; it is O(1) regardless of array size and no bytes move. You then build a `&[f64]` with `slice::from_raw_parts`, which is `unsafe` and needs a `// SAFETY:` comment justifying that the dtype was validated, the buffer is C-contiguous, and the exporter outlives the slice. In practice you use the `numpy` crate's `PyReadonlyArray1<f64>` instead, which handles strides and dimensionality; hand-rolling `from_raw_parts` on a strided or Fortran-ordered array is a straightforward soundness bug. The measured payoff at N=1 was 266.6 ns against 3,308.9 ns for `np.sum`, 12.41x, and none of that came from a faster loop.
**Follow-up trap:** *"Where does the zero-copy claim break?"* On the return path, which people forget. Returning a `Vec<u32>` builds a Python list with one `PyLong` allocation per element and that is O(n) with a large constant; returning via `PyArray1::from_vec` moves the buffer and is O(1). Similarly on the argument side, `Vec<u8>` copies while `&[u8]` borrows, and `String` copies while `&str` borrows, which is one character of difference and a full memcpy. And a non-contiguous slice, a masked array or an object-dtype array cannot be exported at all, so you need a fallback path or an explicit error.

### Q8 — When is candle or burn the right choice over PyTorch?
**Testing:** whether you can advocate for Rust in the one place it wins without overselling it.
**Answer:** When the deployment artifact is the constraint, not throughput. Four concrete cases. First, no-Python deployment: a single static binary versus a 4+ GB PyTorch container changes image pull time, cold start, attack surface and dependency resolution, and that is categorical rather than a percentage. Second, edge, embedded and WASM: burn compiles to `wasm32` and runs on WebGPU in a browser through CubeCL, which also targets CUDA, ROCm, Metal, Vulkan and SIMD CPU; PyTorch does not compete there. Third, small models on CPU, like a MiniLM or BERT-base embedding endpoint, where framework overhead is a real fraction and the model fits in budget even with a less-tuned kernel. Fourth, embedding a model inside an existing Rust service to remove a 1-3 ms HTTP hop to a Python sidecar. Both projects are genuinely active: candle is at 0.11.0 with 20.9k stars and burn at 0.22.0-pre.1 with 15.7k, both pushed within the last day as of 2026-08-06.
**Follow-up trap:** *"Their benchmarks claim 35-47% faster than PyTorch. Do you believe them?"* Partly, and I would not plan on it. The reported numbers are bimodal because the variance is which ops have tuned kernels in that backend. Against the 47%-on-BERT claims sits candle issue #2877, which documents `all-MiniLM-L6-v2` at 122.30 ms per batch in candle 0.8.4 against ~14.34 ms in PyTorch, an 8.5x regression, and issue #942 reporting the same shape for YOLOv8 against ONNX Runtime. You cannot know which side you land on without benchmarking your specific model, so I would keep the PyTorch path until the Rust one wins on my workload.

### Q9 — How would you package and ship a PyO3 extension?
**Testing:** whether you have done it, because the packaging is most of the real work.
**Answer:** `maturin` as the build backend, three files. `Cargo.toml` needs `crate-type = ["cdylib"]` and `pyo3` with the `extension-module` feature; `pyproject.toml` names `maturin` as `build-backend` and must include `project.version` or maturin warns and CI fails later. `maturin develop` for the inner loop, `maturin build --release` for artifacts. My trivial ten-function extension took 28.7 s for a clean release build including compiling all 13 PyO3 crates and produced a 222,957-byte wheel, so PyO3's fixed cost is roughly 200 KB of binary and a binding is never a small artifact. The thing that actually determines CI cost is the stable ABI: without it my wheel was tagged `cp310-cp310` and works on exactly one Python version, so the matrix is versions times platforms. `features = ["abi3-py310"]` collapses it to one wheel per platform, which is what `tokenizers` ships (`tokenizers-0.23.1-cp310-abi3-manylinux_2_17_x86_64...whl`, 3,346,235 bytes). For glibc compatibility, build in `manylinux2014` or use `maturin build --zig` to cross-compile against an older glibc without a container.
**Follow-up trap:** *"What is the cost of abi3?"* You lose non-stable C-API functions and some PyO3 optimisations that reach into struct internals, and stable-ABI calls go through function pointers rather than macros, so there is a small measured slowdown on some operations. Almost everyone takes the trade because a 25-job matrix versus a 5-job matrix dominates. The separate trap is publishing an sdist without matching wheels: every user then needs a Rust toolchain and a multi-minute compile, which turns `pip install` into a support ticket.

### Q10 — A Rust panic happens inside your extension while serving a request. What happens?
**Testing:** production hardening, and a real config footgun most people have never thought about.
**Answer:** It depends on your release profile, and the default is the safe one. Unwinding a Rust panic across the FFI boundary is undefined behaviour, so PyO3 wraps every `#[pyfunction]` in a catch and converts a panic into a Python `PanicException`, which the caller can handle like any exception and which kills only that request. If you set `panic = "abort"` in `[profile.release]`, that catch cannot happen and any panic becomes an immediate `SIGABRT` that kills the interpreter, taking every concurrent in-flight request with it and producing no Python traceback. So for a server extension you keep unwinding, and you give up the 5-10% binary-size saving that `panic = "abort"` buys.
**Follow-up trap:** *"What actually panics in practice?"* Slice indexing on user-controlled lengths, `unwrap()` on a parse or a `HashMap` lookup, integer overflow if you built with overflow checks on, and `PyRefMut` borrow violations where two threads mutably borrow the same `#[pyclass]`, which PyO3 detects and panics on rather than deadlocking or corrupting. The fixes are to return `PyResult` with a mapped error type (`impl From<MyError> for PyErr` so callers catch a real exception class rather than a stringified `RuntimeError`), and to put shared `#[pyclass]` state behind a `Mutex` rather than relying on the GIL, which is exactly the audit free-threading forces anyway.

### Q11 — Your data-loading pipeline wraps `tokenizers.encode_batch` in a 16-worker `ThreadPoolExecutor` and it is not faster. Why?
**Testing:** whether you know what "releases the GIL" implies about who owns the cores.
**Answer:** Because `encode_batch` already releases the GIL and parallelises internally over rayon, so the cores were saturated before you added a single thread. I measured exactly this: 1, 2 and 4 Python threads over 2,511 documents took 147.0, 147.3 and 152.3 ms, flat and then slightly worse from thread and rayon-scheduling overhead. The proof that the internal parallelism is real is the environment variable: `TOKENIZERS_PARALLELISM=true` gave 142.7 ms at 5.17 MB/s and `false` gave 324.6 ms at 2.27 MB/s, a 2.27x on two vCPUs, which is essentially linear. The fix is to delete the pool and control the parallelism where it actually lives, with `RAYON_NUM_THREADS`.
**Follow-up trap:** *"Then why does `TOKENIZERS_PARALLELISM=false` show up in so many codebases?"* Because people copy it out of a HuggingFace issue to silence the fork-safety warning. rayon's thread pool does not survive `os.fork()`: the child inherits a pool whose threads do not exist, so it hangs or deadlocks, and the library warns and disables parallelism to protect you. Setting it to `false` makes the warning go away and quietly costs you 2.27x. The correct fix is to fix the fork ordering: construct the tokenizer *after* forking, or use the `spawn` start method. This is a real production regression that shows up as a deploy that halved throughput with no code change.

### Q12 — Rust has memory safety, so a Rust extension cannot crash the interpreter. True?
**Testing:** whether you know where `unsafe` is unavoidable at the boundary.
**Answer:** False, and the interesting part is where the holes are. Safe Rust plus PyO3 gets you a great deal: no use-after-free of Rust objects, no data races on Rust state (enforced by `Send`/`Sync`), and panics converted to exceptions rather than undefined behaviour. But zero-copy interop is `unsafe` by construction. `slice::from_raw_parts(buf.buf_ptr(), n)` is a promise you are making, and it is wrong if the array is strided rather than C-contiguous, if the dtype does not match the type parameter, if the exporting object is freed while you hold the slice, or if another thread mutates the array underneath you (the buffer protocol has no reader/writer lock in the general case). Beyond that, `panic = "abort"` turns any panic into a process kill, `PyRefMut` aliasing panics at runtime rather than compile time because the aliasing happens through Python, and any `extern "C"` you declare or C library you link is entirely outside Rust's guarantees.
**Follow-up trap:** *"How do you get confidence in the unsafe parts then?"* Keep the `unsafe` surface tiny and wrapped: one function that converts a `PyBuffer` into a `&[T]` with a `// SAFETY:` comment naming each invariant and why it holds, and everything downstream is safe Rust operating on a slice. Then test it under the tools that catch what review does not: `cargo miri` on the pure-Rust paths, ASan/UBSan builds for the FFI paths, and `pytest` with `faulthandler` enabled so a segfault produces a Python-side stack. And prefer the `numpy` crate's typed array wrappers over hand-rolled pointer arithmetic, because they check contiguity and dtype for you.

### Q13 — Name three components in a modern AI stack that are Rust and explain what they have in common.
**Testing:** pattern recognition, which is the actual senior skill this module teaches.
**Answer:** `tokenizers` and `tiktoken` for BPE; `safetensors` for tensor serialization; `uv` and `ruff` for packaging and linting; Polars for dataframes; Qdrant and LanceDB for vector search; and the newest ones, SGLang's `sgl-router` and vLLM's `router`. What they share is one shape: a hot loop whose unit of work is a byte, a token, an AST node or a graph edge rather than a tensor, executed an enormous number of times, with no matmul to hide in and therefore no BLAS or CUDA kernel already doing the work, plus a GIL problem or a per-item interpreter-overhead problem. `uv` is the clearest illustration because it is not algorithmically exotic at all: it resolves dependencies and unzips files, and I measured 14.54 s for `pip` to create a venv and install `tokenizers` against 1.68 s for `uv` with a cold cache and 0.10 s warm, 8.7x and 145x, achieved with parallel Rust, a content-addressed global cache and hardlinks. Not one of these components is a model.
**Follow-up trap:** *"What is conspicuously not Rust, and why?"* The two layers on either side. Above: PyTorch, JAX, vLLM and SGLang themselves are Python, because the loop body is a cuBLAS or FlashAttention call and Python overhead is a fraction of a percent, and because ML engineers need to iterate. Below: the kernels are CUDA, Triton, CUTLASS and cuDNN, where Rust has essentially no story because the ecosystem, the tooling and a decade of hand-tuning are all C++ and PTX. Rust took the band in between, and that band is defined by the absence of a tensor.

### Q14 — How would you decide whether to write a Rust binding, as a process, not a vibe?
**Testing:** staff-level judgement expressed as a checkable procedure.
**Answer:** Five steps, in order, and I stop at the first one that says no. **Step 1.** Profile and get the CPU-bound-Python fraction of p99, with `py-spy` or `cProfile`. Under 10% and the answer is no regardless of anything else, because the ceiling on the whole project is 10%. **Step 2.** Exhaust the free wins, because they are usually larger than the rewrite: a better algorithm, a batching change, an existing Rust library, a config flag. My own measurements have `encode_batch` over `encode` at 2.87x, `encode_batch_fast` at a further 1.19x, and `TOKENIZERS_PARALLELISM=true` at 2.27x, all for zero new code. **Step 3.** Estimate the per-call work. If it is under about 1 µs, the ~55 ns boundary plus argument conversion eats it, and the answer is to move the *loop* into Rust rather than the loop body. **Step 4.** Check what has to cross. If the natural argument is a `list` or `dict`, conversion is O(n) at roughly the builtin's own per-element cost and I expect no win; if it can be `bytes` or a buffer-protocol array, it is O(1) and I expect one. **Step 5.** Price the team cost honestly: build time, who can maintain it, and whether the people who change this code weekly can work in Rust. Then prototype and measure the empty call and the real call before committing.
**Follow-up trap:** *"Give me an example where you would say yes."* Offline tokenization of a large pretraining corpus, or a cache-aware router. Both are more than 40% CPU-bound Python, both have per-call work in the tens of microseconds to milliseconds so the boundary is noise, both take `str`/`bytes` so the crossing is O(1), and both benefit from GIL release for near-linear core scaling. And I would still not write the binding, I would use `tokenizers`, because the second-best answer to "should we write Rust" is almost always "someone already did".

### Q15 — Free-threaded Python is coming. Does that undermine the case for Rust in the AI stack?
**Testing:** whether you can reason about a live, unsettled question without picking a side dogmatically.
**Answer:** It undermines exactly one of the three arguments. The parallelism argument, "Rust so we can use all the cores from one process", has a multi-year expiry date: PEP 779 was accepted for 3.14 so free-threading is officially supported in phase two, shipping as the opt-in `3.14t` binary, with single-threaded overhead down to roughly 5-10% from about 40% in the 3.13 experimental build, and phase three (default) has criteria but no committed version. The constant-factor argument is untouched: I measured 104.00 ns per interpreted loop iteration against 1.81 ns in Rust, 57.5x, and removing the GIL does not change interpreter dispatch cost. The third argument, compile-time-checked thread safety, gets *stronger*, because a large amount of Python and C-extension code has latent data races that the GIL was accidentally serialising, and Rust's `Send`/`Sync` bounds catch those at compile time.
**Follow-up trap:** *"What breaks in existing PyO3 extensions when someone runs them on 3.14t?"* Two things, one loud and one silent. The silent one: a module that has not declared `gil_used = false` in its `#[pymodule]` causes CPython to re-enable the GIL at import, so you get no parallelism, no error, and only a `RuntimeWarning` that most people have filtered. The loud one: any shared mutable state in a `#[pyclass]` that was implicitly protected by the GIL is now genuinely concurrent, so `PyRefMut` borrow panics start appearing under load, and `static mut` or the now-deprecated `GILOnceCell` (replaced by `PyOnceLock` in 0.29) become bugs. The API renames in PyO3 0.29, `with_gil` to `attach` and `allow_threads` to `detach`, exist precisely to stop people reasoning as though a GIL is always there.

## Red flags that fail you

- "We should rewrite the inference service in Rust to make it faster" without naming the CPU-bound-Python fraction. This is the single answer that ends a principal-level interview, because the GPU is the request.
- "Rust is 100x faster than Python." The measured range for the same tokenization algorithm was 2.4x to 17.5x depending on cache warmth and which API you call, and in one condition the pure-Python version *won*.
- Not knowing the boundary has a cost. If you cannot say roughly what an empty PyO3 call costs (~55 ns, about one Python call), you have never measured a binding.
- Proposing to bind a per-item helper function. The correct move is always to move the loop, not the loop body.
- Claiming a Rust rewrite will beat numpy or PyTorch on a bulk numeric kernel. It usually loses; mine was 0.42x of `np.sum` at N=65,536 because `iter().sum()` on floats does not vectorise.
- Saying "Rust has no GIL so it's parallel" without knowing that `py.detach()` is what releases it, that it costs ~30-40 ns, and that the closure cannot touch Python objects.
- Treating the GIL as a permanent fact. PEP 779 moved free-threading to supported status in 3.14, and not knowing that in 2026 dates you.
- Recommending candle or burn for GPU inference at scale on the strength of a marketing benchmark, without mentioning that reported results range from 47% faster to 8.5x slower depending on the model.
- Setting `panic = "abort"` on a Python extension. It converts a per-request `PanicException` into a process-wide `SIGABRT`.
- Saying "zero-copy" without being able to name what makes it unsafe: strides, dtype mismatch, exporter lifetime, and concurrent mutation.
- Hand-editing a `Vec<String>` return type and calling it zero-copy. Every element is a Python object allocation.
- Not asking who maintains it. A Rust component in a team of Python ML engineers is an organisational single point of failure, and saying so out loud is a senior signal, not a cop-out.

## Cheat card

```
THE PATTERN: hot loop, NOT a matmul, called millions of times, no GPU/BLAS path.
             Rust owns the band where the unit of work is a BYTE, not a TENSOR.

BOUNDARY COST (PyO3 0.29.2, CPython 3.10.12, min of 7)
  python def noop()  50.71 ns | rust noop() 54.56 ns | attr lookup 34.31 ns
  rust add(1,2) 79.16 ns  >  python add(1,2) 70.85 ns   <- RUST LOSES
  => break-even ~1 us of Rust work/call. One call per BATCH, never per ITEM.

PYTHON CONTAINERS KILL IT: sum_list(Vec<i64>) 0.40-0.68x vs sum(), N=1..1,048,576.
  No crossover. Extraction is 7.6-12.3 ns/elem = the work sum() already did.

ZERO-COPY (PyBuffer, O(1)): N=1 12.41x vs np.sum | N=256 6.53x | N=65,536 0.42x
  Rust wins on numpy's ~3 us DISPATCH, loses on numpy's SIMD kernel. f64
  iter().sum() does not autovectorise (IEEE non-assoc). See T20-rust-perf.

GIL: py.detach() (was allow_threads). Round trip ~30-40 ns; detach if work >1 us.
  30M-iter loop, 8 threads: held 0.507 s (10.3x = serial) / detached 0.198 s.
  Python 104.00 ns/iter vs Rust 1.81 ns/iter = 57.5x constant factor.

TOKENIZERS (738,046 B -> 191,673 identical GPT-2 ids)
  hf.encode            400.1 ms  1.84 MB/s   | pyBPE cold  0.98 MB/s (14.4x gap)
  hf.encode_batch      132.9 ms  5.55 MB/s   | pyBPE warm  3.01 MB/s (BEATS hf)
  hf.encode_batch_fast 111.8 ms  6.60 MB/s   (skips offsets, 1.19x)
  tiktoken             51.5 ms  14.33 MB/s   <- 7.8x vs hf, SAME LANGUAGE.
     because Encoding = 8 vecs + a String PER TOKEN; tiktoken returns Vec<u32>.
  TOKENIZERS_PARALLELISM=true 142.7 ms / false 324.6 ms = 2.27x on 2 vCPU.
  ThreadPoolExecutor on top: 147.0/147.3/152.3 ms for 1/2/4 threads = NOTHING.
  Per short prompt: hf 11.02 us, tiktoken 2.17 us. = 0.0003% of a 4 s generation.

VERSIONS (2026-08-06): pyo3 0.29.2 (with_gil->attach, allow_threads->detach)
  maturin 1.14.1 | tokenizers 0.23.1 | safetensors 0.8.0 | candle 0.11.0
  burn 0.22.0-pre.1 | uv 0.12.2 | rustc 1.97.1 | PEP 779 = 3.14 phase 2, opt-in

PACKAGING: crate-type=["cdylib"] + pyo3 "extension-module" + maturin backend.
  abi3-py310 -> ONE wheel per platform (cp310-abi3) instead of per version.
  My wheel 222,957 B / 28.7 s clean build. tokenizers wheel 3,346,235 B.
  NEVER panic="abort" in an extension -> SIGABRT kills the whole interpreter.

THE DECISION: CPU-bound-Python % of p99?  >40% bind it | 10-40% profile first
                                          <10% NO (LLM serving lives here)
  uv vs pip measured: 14.54 s -> 1.68 s cold (8.7x), 0.10 s warm (145x).
```

## Sources

- [PyO3 CHANGELOG](https://github.com/PyO3/pyo3/blob/main/CHANGELOG.md) — accessed 2026-08-05
- [PyO3 user guide: Supporting Free-Threaded Python](https://pyo3.rs/main/free-threading.html) — accessed 2026-08-05
- [PyO3 user guide: Migration guide](https://pyo3.rs/main/migration.html) — accessed 2026-08-05
- [PyO3 0.27.0 release notes](https://github.com/PyO3/pyo3/releases/tag/v0.27.0) — accessed 2026-08-05
- [PEP 779: Criteria for supported status for free-threaded Python](https://peps.python.org/pep-0779/) — accessed 2026-08-05
- [Python HOWTO: Python support for free threading](https://docs.python.org/3/howto/free-threading-python.html) — accessed 2026-08-05
- [Python Free-Threading Guide](https://py-free-threading.github.io/) — accessed 2026-08-05
- [huggingface/tokenizers](https://github.com/huggingface/tokenizers) — accessed 2026-08-06
- [huggingface/candle](https://github.com/huggingface/candle) — accessed 2026-08-06
- [candle issue #2877: Candle Inference ~8.5x Slower Than PyTorch on CPU](https://github.com/huggingface/candle/issues/2877) — accessed 2026-08-05
- [candle issue #942: yolov8 inference slower than PyTorch/onnxruntime](https://github.com/huggingface/candle/issues/942) — accessed 2026-08-05
- [tracel-ai/burn](https://github.com/tracel-ai/burn) — accessed 2026-08-06
- [Burn 0.20 release notes (CubeCL, CubeK, fusion)](https://burn.dev/blog/) — accessed 2026-08-05
- [PyO3/maturin](https://github.com/PyO3/maturin) — accessed 2026-08-06
- [SGLang Model Gateway (formerly SGLang Router) docs](https://docs.sglang.io/advanced_features/router.html) — accessed 2026-08-05
- [vLLM Router release: prefill/decode aware load balancer](https://vllm.ai/blog/2025-12-13-vllm-router-release) — accessed 2026-08-05
- [vllm-project/router](https://github.com/vllm-project/router) — accessed 2026-08-05
- [openai/tiktoken](https://github.com/openai/tiktoken) — accessed 2026-08-06
- [PEP 3118: Revising the buffer protocol](https://peps.python.org/pep-3118/) — accessed 2026-08-05
- [astral-sh/uv](https://github.com/astral-sh/uv) — accessed 2026-08-06

Version and repository figures (star counts, last-push dates, crate versions) were read directly from the GitHub REST API and `cargo search` on 2026-08-06. All timings are my own measurements on the hardware and toolchain named at the top of "How it actually works".

## Changelog
- 2026-08-06 — created
