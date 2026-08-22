# I/O Models: Blocking, epoll, io_uring, mmap, Zero-Copy

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2h · **Prereqs:** T16-os-internals · **Updated:** 2026-08-03
> **Module id:** `T16-io-models` · **Tags:** os, critical

## The 30-second version

Every I/O model is answering the same question — "how does an application find out data is ready without wasting a thread" — and the four generations answer it differently: blocking I/O burns one OS thread per connection and relies on the scheduler; `select`/`poll` let one thread watch many descriptors but cost O(n) per call because the whole interest list is re-copied and re-scanned every time; `epoll` fixes that by keeping the interest list inside the kernel (`epoll_ctl`) so `epoll_wait` only returns what actually became ready, making it O(1) per ready descriptor and the reason nginx, Redis, and every serious event loop use it on Linux. `io_uring` (Linux 5.1, 2019) goes a level further by replacing "notify me, then I'll call read()" with a completion model: you submit a request into a shared-memory submission queue (SQ) and the kernel deposits the result into a completion queue (CQ), so a batch of I/O can complete with a single syscall or, with `SQPOLL`, zero syscalls at all — at 100K connections, epoll servers spend roughly 15-25% of CPU in syscall overhead alone, and io_uring with batching can push per-operation cost under 10ns. Zero-copy (`sendfile`, `splice`, `io_uring` registered buffers) skips the userspace round-trip entirely, copying data kernel-cache-to-NIC directly instead of kernel→userspace→kernel, which is why a static file server built on `sendfile()` needs roughly one syscall per file transfer instead of thousands of `read`+`write` pairs. The catch with io_uring specifically: its complexity has made it the single largest source of Linux kernel privilege-escalation CVEs in the last three years, which is why Google disabled it by default in ChromeOS, Android, and production servers.

## Why this gets asked

Because "how would you build a server that handles 100K concurrent connections" is one of the most reliable senior-vs-junior filters in a systems interview, and the honest answer requires knowing what the OS is actually doing underneath your framework's event loop — not just that Node/Python asyncio/Go's netpoller "use epoll." The interviewer has almost certainly debugged a service where a thread-per-connection model fell over past a few thousand connections (context-switch thrashing, memory exhausted by thread stacks), or watched `strace -c` on a hot path reveal thousands of small `read()`/`write()` syscalls that a `sendfile()` or buffering change collapsed into a handful. They want to see that you can reason about *why* epoll is O(1) rather than just naming it, and whether you know io_uring's real tradeoffs (throughput vs. attack surface) rather than reciting it as a strictly-better technology.

---

## Lineage: past → present → future

**What came before.** The original Unix I/O model was synchronous and blocking: a `read()` call didn't return until data was available, so the only way to serve N concurrent clients was N OS threads (or, pre-threads, N forked processes — the classic Apache prefork model). This worked fine when "concurrent connections" meant dozens, but it broke on two axes as the web scaled in the late 1990s: each thread needs its own stack (commonly 1-8MB of virtual address space, megabytes of *resident* memory once touched) and the kernel scheduler itself degrades under thousands of runnable/blocked threads — this is the C10K problem, named in Dan Kegel's 1999 essay, which documented that commodity hardware of the era simply could not serve 10,000 simultaneous connections with a thread-per-connection model. `select()` (BSD, 1983) and later `poll()` (System V) were the first attempt at single-threaded multiplexing: pass the kernel a list of file descriptors, block until any is ready, get back a bitmap or list of what's ready. Both share the same fatal flaw at scale — the interest list is stateless from the kernel's point of view, so every single call re-passes and the kernel re-scans the *entire* list even when only one of 10,000 descriptors is ready, making each call O(n) in the number of watched descriptors. `select()` additionally hard-caps the descriptor count at `FD_SETSIZE` (typically 1024), which made it unusable for true C10K-scale services regardless of CPU budget.

**Where it stands now.** `epoll` (Linux 2.5.44, 2002) is the current default for virtually all high-concurrency Linux network servers: nginx, Redis, HAProxy, nearly every language runtime's async I/O layer (Node's libuv, Python's asyncio selector, Go's netpoller, Java's NIO Selector on Linux) sits on top of it. Its core fix is moving the interest list *into* the kernel via `epoll_ctl(ADD/MOD/DEL)`, so `epoll_wait()` only has to report descriptors that actually transitioned to ready — O(1) amortized per ready event rather than O(n) per call regardless of readiness. `io_uring` (Linux 5.1, 2019, Jens Axboe) is the live disagreement: it's a strict throughput and syscall-count win for I/O-heavy workloads (file I/O, high-fan-out network I/O, database engines — ScyllaDB and RocksDB-adjacent projects have adopted it aggressively), but its kernel-side complexity has made it disproportionately CVE-prone, and several major shops (Google across ChromeOS/Android/production, containerd removing it from the default seccomp profile) have restricted or disabled it specifically because of that track record, not because of a performance regret. So "should we use io_uring" in 2026 is a genuinely contested operational question, not settled consensus — it depends on whether you trust your kernel version's hardening and whether your threat model includes an attacker who can already run code as an unprivileged user (io_uring's exploits are almost all local-privesc, not remote).
Zero-copy techniques (`sendfile`, `splice`, `mmap`+`write` avoidance, and io_uring's registered-buffer / fixed-file modes) sit orthogonal to this axis — they're about avoiding userspace copies regardless of which notification model you use, and they've been production-standard since the late 1990s for anything serving static or semi-static bytes off disk to a socket.

**Where it's heading.** io_uring's security posture is actively improving (kernel hardening work, io_uring-specific fuzzing investment funded partly by the same bug bounty payouts that exposed the problem), and its adoption keeps growing in database and storage engines where the throughput win is largest and the deployment is usually a trusted, single-tenant context where the local-privesc risk model is less severe than on a shared multi-tenant OS. The more speculative direction is user-space networking bypassing the kernel network stack entirely (DPDK, AF_XDP) for the very highest-throughput cases — real and shipping in specific high-frequency-trading and CDN contexts today, but a genuinely different and much higher-complexity tool than anything in this module, not a mainstream replacement for epoll/io_uring in ordinary services. Expect io_uring to keep gaining share in storage-heavy and specialized network services while epoll remains the pragmatic default for general-purpose servers for years yet, precisely because its simplicity is also a security property.

---

## Mental model

```
BLOCKING (1 thread per conn):
  Thread1 --read()--> [BLOCKED waiting on socket A] ... data arrives ... returns
  Thread2 --read()--> [BLOCKED waiting on socket B] ...
  N threads, N stacks, N contexts the scheduler must juggle.

SELECT/POLL (O(n) per call):
  App: "here are my 10,000 fds, which are ready?"   -----> kernel scans ALL 10,000
  Kernel: "these 3 are ready"                        <----- every single call, even if
  App re-passes the FULL list next call.                    only 1 fd changed state.

EPOLL (O(1) amortized):
  App: epoll_ctl(ADD, fd)  ---once, kernel remembers---> [interest list lives in kernel]
  App: epoll_wait()  ------------------------------->    only READY fds come back
  Kernel maintains a ready-list via callbacks fired when a watched fd's state changes;
  epoll_wait just drains that ready-list, doesn't rescan everything.

IO_URING (completion model, batched, optionally 0 syscalls):
  App writes SQEs into a shared-memory ring  --no syscall needed to enqueue--
  io_uring_enter() [submits batch + optionally waits]  ---1 syscall for N ops---
  Kernel does the I/O, writes results as CQEs into a second shared-memory ring
  App drains CQEs from userspace -- no syscall needed to read completions
  SQPOLL: a kernel thread polls the SQ itself, so steady-state submission is 0 syscalls.
```

The throughline: each generation moves more bookkeeping from "re-explain everything every time" (select/poll) to "tell the kernel once, let it push state changes back" (epoll) to "batch the entire request/response cycle through shared memory so the syscall boundary itself nearly disappears" (io_uring).

---

## How it actually works

### select/poll: why O(n) is the whole problem

`select(nfds, &readfds, &writefds, &exceptfds, &timeout)` takes bitmaps of every fd you care about. Two costs repeat on **every call**: the kernel must walk and re-register interest across the entire list (it doesn't remember it from last time), and the *application* must walk the returned bitmap to figure out which of possibly thousands of bits flipped. `poll()` swaps bitmaps for an array of `struct pollfd`, removing the 1024-fd `FD_SETSIZE` ceiling, but the O(n) scan-every-call cost is identical. At 10 watched descriptors this is invisible. At 10,000, with most idle at any instant, you are paying a full kernel-side linear scan multiple times a second for a handful of actual state changes — this is the mechanical reason C10K needed a different primitive, not just "select is old."

### epoll: the three calls and the *n* + *m* complexity split

```c
int epfd = epoll_create1(0);
struct epoll_event ev = { .events = EPOLLIN, .data.fd = client_fd };
epoll_ctl(epfd, EPOLL_CTL_ADD, client_fd, &ev);   // register once
...
struct epoll_event ready[MAX_EVENTS];
int n = epoll_wait(epfd, ready, MAX_EVENTS, timeout_ms);  // only ready fds come back
```

Internally, `epoll_ctl` links the fd into a red-black tree keyed by fd number (fast add/remove/lookup, O(log n)) and registers a callback with the underlying device driver's wait queue. When the socket's state actually changes (data arrives, buffer drains), the driver's interrupt handler fires that callback, which pushes the fd onto a separate **ready list** (a simple linked list). `epoll_wait` does nothing more than drain that ready list — it never touches the red-black tree or rescans anything unchanged. This is why the complexity is described as O(1) *per ready event* rather than O(n) per call: cost scales with how much actually happened, not with how much you're watching.

**Level-triggered (LT, default) vs edge-triggered (ET):** LT fires every time you call `epoll_wait` as long as the fd *remains* readable — if you read only half the available bytes, the next call reports the same fd ready again, which is forgiving but means a lazy handler keeps getting re-notified. ET fires only on the *transition* from not-ready to ready, so if you don't drain the socket with a `read()` loop until you get `EAGAIN`, you will never be told again and the connection silently stalls — ET requires non-blocking fds and a "read until EAGAIN" discipline, in exchange for fewer wakeups under high-throughput steady streaming. nginx defaults to ET for exactly this efficiency reason and is written to always loop-drain.

### io_uring: submission/completion rings

```c
struct io_uring ring;
io_uring_queue_init(256, &ring, 0);              // 256-entry SQ/CQ, shared mmap'd rings

struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
io_uring_prep_read(sqe, fd, buf, size, offset);   // fill in a submission entry
io_uring_submit(&ring);                            // io_uring_enter() -- 1 syscall

struct io_uring_cqe *cqe;
io_uring_wait_cqe(&ring, &cqe);                    // may also be a syscall, or none if
                                                     // completions were already posted
int result = cqe->res;
io_uring_cqe_seen(&ring, cqe);
```

The SQ and CQ are memory-mapped and shared between kernel and userspace, so *filling in* a submission entry costs nothing (no syscall) — the syscall only happens at `io_uring_enter()`, and you can batch dozens of operations into one call. With `IORING_SETUP_SQPOLL`, a dedicated kernel thread continuously polls the SQ for new entries, so **steady-state submission needs zero syscalls at all** from the application — at the cost of that kernel thread burning a CPU core. Benchmarks on echo-server-style microbenchmarks show io_uring with SQPOLL cutting syscall counts by roughly 80% versus an equivalent epoll implementation, and batched `io_uring_enter` calls (32 SQEs submitted, 32 CQEs reaped per call) bring the amortized per-operation syscall cost under 10ns on modern CPUs — but if you submit one operation at a time with no batching, io_uring's internal bookkeeping overhead can make it *slower* than epoll, because you've paid its setup cost without collecting its batching win. This is a real, frequently-cited caveat: io_uring is not unconditionally faster, it's faster when the workload lets you batch.

### mmap: mapping a file instead of read()/write()ing it

`mmap(NULL, length, PROT_READ, MAP_PRIVATE, fd, 0)` maps a file's pages directly into the process's virtual address space; reading the mapped memory triggers ordinary page faults (see the memory hierarchy and os-internals modules) that pull pages from the page cache — the same page cache `read()` would use — rather than a syscall-per-chunk copy loop. This avoids `read()`'s mandatory copy from the kernel's page cache buffer into a userspace buffer entirely; the userspace "buffer" *is* the page cache page, shared. The tradeoff: `mmap` has real per-call setup cost (page table entries must be created, and a large mapping stresses the TLB — see memory-hierarchy) that makes it a net loss for small, one-shot reads, and a page fault on a byte you haven't touched yet is *first-touch-lazy*, meaning a naive mmap-and-scan of a giant file can be slower and more page-fault-heavy than a straight sequential `read()` with a decent buffer size, because `read()` benefits from kernel-side readahead in a way that unpredictable memory-access patterns on an mmap'd region often don't. The classic good use case is random-access reads into a large file you'll touch repeatedly (memory-mapped databases like LMDB, SQLite's optional mmap mode) — the classic bad use case is a one-pass sequential scan of a huge file, where plain buffered `read()` usually wins.

### Zero-copy: sendfile and splice

`sendfile(out_fd, in_fd, &offset, count)` tells the kernel "move bytes from this file descriptor to that one" without ever bringing the data into userspace — the kernel DMA-copies (or, on hardware supporting scatter-gather DMA, copies zero times) directly from the page cache to the NIC's transmit buffer. Compare the syscall count for serving a large file the naive way (`read()` into a buffer, `write()` that buffer to the socket, repeated per chunk) versus `sendfile()`: a real measurement moving 2.5GiB showed **2,972 syscalls with `sendfile()` versus 131,093 syscalls with read+write** — roughly a 44x reduction in syscall count for the identical bytes moved, which directly translates to far fewer user/kernel mode transitions (each costing on the order of 100-300ns, per the os-internals module) and zero userspace buffer copies. `splice()` generalizes this to pipe-to-anything and anything-to-pipe transfers (not just file-to-socket), which is how tools like `nginx`'s and HAProxy's internal proxying paths avoid userspace copies when relaying bytes between two sockets. The practical break-even point where zero-copy's setup cost is worth it is commonly cited around **10-100KB transfers**, depending on workload — for tiny payloads the fixed overhead of setting up the zero-copy path can exceed a plain `read`+`write`, and zero-copy provides *no* benefit at all when the data must be transformed in userspace anyway (e.g., nginx serving gzip-compressed output on the fly must decompress-then-compress in userspace, so `sendfile` doesn't apply to that path — it only helps serving bytes unmodified).

---

## Build it from scratch

A minimal comparison worth being able to write: a blocking-thread echo server versus an epoll-based one, to make the mechanical difference in file-descriptor handling concrete.

```python
# untested sketch — minimal epoll echo server, Linux only
import socket, select

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 9000))
server.listen(128)
server.setblocking(False)

epoll = select.epoll()
epoll.register(server.fileno(), select.EPOLLIN)

connections = {}
try:
    while True:
        events = epoll.poll(timeout=1)          # blocks until something is ready
        for fd, event in events:
            if fd == server.fileno():
                conn, addr = server.accept()
                conn.setblocking(False)
                epoll.register(conn.fileno(), select.EPOLLIN)
                connections[conn.fileno()] = conn
            elif event & select.EPOLLIN:
                conn = connections[fd]
                try:
                    data = conn.recv(4096)
                    if data:
                        conn.send(data)           # echo it back
                    else:
                        epoll.unregister(fd)
                        conn.close()
                        del connections[fd]
                except BlockingIOError:
                    pass                            # EAGAIN, nothing to do this round
finally:
    epoll.unregister(server.fileno())
    epoll.close()
    server.close()
```

This single-threaded loop handles an arbitrary number of connections with one thread, one stack, and O(1) work per ready descriptor — the entire point of the model. A production comparison lab (measuring thread-per-connection memory/CPU vs. this epoll loop vs. an `io_uring`-based version under `wrk`/`ab` load) belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Service falls over past a few thousand concurrent connections, high memory, high context-switch rate in `vmstat` | Thread-per-connection model — each thread's stack (1-8MB reserved) plus scheduler overhead doesn't scale past low thousands | Move to an event-loop model (epoll-backed: nginx, Node, Go's netpoller, Python asyncio) |
| `strace -c` on a hot path shows huge counts of small `read()`/`write()` | Streaming a file byte-buffer-at-a-time instead of using `sendfile()`/`splice()`, or missing buffering | Use `sendfile()` for unmodified file-to-socket transfers; add userspace buffering (e.g. `BufWriter`) where zero-copy doesn't apply |
| Edge-triggered epoll handler works in testing, silently stalls specific connections under real traffic | Handler reads once per `EPOLLIN` event instead of looping until `EAGAIN`, so remaining buffered bytes never trigger another edge | Loop `read()`/`recv()` until `EAGAIN` on every ET wakeup, or switch to LT if that discipline is hard to guarantee everywhere |
| `io_uring`-based service hits kernel panics or is flagged by a security scanner for privilege-escalation risk | io_uring's large in-kernel attack surface — 60%+ of Google's kCTF kernel bug bounty submissions have targeted io_uring, with roughly $1M paid out for io_uring-specific exploits, including CVE-2024-0582 (use-after-free giving read/write on freed pages) | Restrict io_uring via seccomp in multi-tenant/untrusted contexts (containerd removed it from the default `RuntimeDefault` profile for this reason); Google disabled it by default on ChromeOS, Android, and production servers |
| CPU pegged at 100% on one core, throughput doesn't improve | `SQPOLL` kernel polling thread burning a full core even when I/O is light | Only enable `SQPOLL` for genuinely I/O-saturated workloads; benchmark before enabling, it's not a free lunch |
| Random-access mmap'd file workload shows worse throughput than expected, high minor-fault rate in `/proc/<pid>/stat` | Access pattern defeats kernel readahead, and every first-touch page costs a minor fault (~1-10μs) that `read()`'s explicit buffering + readahead would have amortized | Use `madvise(MADV_SEQUENTIAL)`/`MADV_RANDOM` to hint access pattern, or fall back to buffered `read()` for pure sequential scans |

---

## Tradeoffs & when NOT to use it

- **Don't reach for io_uring by default in a multi-tenant or security-sensitive context.** Its throughput win is real, but so is its CVE track record — Google disabling it in ChromeOS/Android/production and containerd stripping it from the default seccomp profile are both direct responses to it being the single largest source of exploitable kernel bugs in recent years. If your workload doesn't actually need the syscall-count reduction (i.e., you're not I/O-bound at high fan-out), epoll's smaller attack surface is the more defensible default.
- **Don't use edge-triggered epoll unless your handler is written to always drain to `EAGAIN`.** LT is more forgiving and the performance delta only matters at genuinely high per-connection throughput; ET picked incorrectly produces silent, hard-to-reproduce stalls, not a crash you'd catch in code review.
- **Don't mmap small or one-shot-sequential files expecting a free win.** The per-mapping setup cost (page table entries, potential TLB pressure) and loss of kernel readahead can make mmap slower than a plain buffered `read()` for exactly the workload people intuitively reach for it on.
- **Don't expect zero-copy to help when the data must be transformed.** On-the-fly compression, encryption, or any userspace transform requires the bytes to actually pass through userspace, so `sendfile`/`splice` simply don't apply to that code path — check whether your "slow" endpoint is even eligible before optimizing toward zero-copy.
- **Don't multiplex with `select()` in new code.** Its `FD_SETSIZE` ceiling (typically 1024) and O(n)-per-call cost make it strictly dominated by `poll()` for correctness and by `epoll` for performance on Linux; it survives only in portability shims targeting non-Linux/BSD-lite environments.

---

## Interview questions

### Q1 — Why is `epoll` faster than `select`/`poll` at high fd counts? Give the actual complexity.
**Testing:** whether the O(1) vs O(n) distinction is understood mechanically, not just as a memorized label.
**Answer:** `select`/`poll` are stateless across calls — every call re-passes and the kernel re-scans the entire watched-fd list, so cost is O(n) in the number of watched descriptors *per call*, regardless of how many actually changed state. `epoll` keeps the interest list inside the kernel (a red-black tree, registered once via `epoll_ctl`) and uses driver callbacks to push state changes onto a separate ready-list; `epoll_wait` just drains that ready-list, so cost is proportional to how many descriptors actually became ready, not how many are being watched.
**Follow-up trap:** *"Is `epoll_ctl` itself free?"* — no, it's O(log n) per add/remove/modify against the red-black tree; the O(1) claim is specifically about `epoll_wait`'s cost per ready event, not the setup cost of registering interest, which is a common overstatement to catch.

### Q2 — Explain edge-triggered vs level-triggered epoll and when a bug shows up from getting it wrong.
**Testing:** real operational experience, not textbook definitions.
**Answer:** Level-triggered fires every `epoll_wait` call as long as the fd remains ready (forgiving, but repeats notifications for partially-drained data). Edge-triggered fires only on the transition to ready, so a handler that reads only part of the available data on an ET wakeup will never be told again about the remaining bytes until new data arrives — the fix is looping `read()` until `EAGAIN` on every ET event.
**Follow-up trap:** *"Your ET-based service has a handful of connections that just... stop receiving data, no error, no crash."* — this is the exact symptom of not draining to `EAGAIN`: the fd is still readable but the edge already fired and won't fire again, so the connection looks alive but silently starves. The fix is a code audit for every `EPOLLIN` handler, confirming a full drain loop.

### Q3 — Walk me through what happens, syscall by syscall, when io_uring reads a file, versus the same read with epoll+read().
**Testing:** whether the completion-queue model is actually understood versus name-recognized.
**Answer:** epoll+read is two logical steps requiring at least two syscalls: `epoll_wait` to learn the fd is readable, then `read()` to actually get the bytes (plus `epoll_ctl` once up front to register). io_uring separates *submission* (writing an SQE into a shared-memory ring — no syscall) from *notification* (`io_uring_enter`, one syscall that can submit a whole batch of SQEs and reap a whole batch of CQEs at once) — so N reads can complete with roughly 1 syscall instead of up to 2N.
**Follow-up trap:** *"So io_uring is always faster?"* — no; if you submit one operation at a time without batching, io_uring's setup/bookkeeping overhead can exceed epoll's simpler per-call cost, making it *slower* for unbatched single-op workloads. The win is specifically in amortizing syscall cost across a batch.

### Q4 — What is SQPOLL and what does it cost?
**Testing:** whether the "free lunch" myth around io_uring is understood.
**Answer:** `IORING_SETUP_SQPOLL` spins up a dedicated kernel thread that continuously polls the submission queue, so the application can submit work without ever calling `io_uring_enter()` in the steady state — genuinely zero syscalls for submission. The cost is that kernel thread burns a full CPU core continuously polling, whether or not there's actual work, which is a real resource tradeoff, not free.
**Follow-up trap:** *"Would you enable SQPOLL on a lightly-loaded service?"* — no; pegging a core for polling only pays off when I/O volume is high enough that the syscalls it eliminates would otherwise dominate CPU time. On a lightly loaded service you're strictly worse off.

### Q5 — Why has Google disabled io_uring by default in ChromeOS, Android, and production servers?
**Testing:** whether the candidate treats io_uring as an unconditionally-better technology or understands its real tradeoffs.
**Answer:** io_uring's kernel-side complexity (shared-memory rings, deferred/async completion semantics, extensive buffer/file registration machinery) has made it disproportionately exploitable — reportedly around 60% of submissions to Google's kCTF kernel vulnerability reward program have targeted io_uring, with roughly $1M paid out, including CVE-2024-0582, a use-after-free giving an attacker read/write access to freed kernel pages. Google's response was to disable it by default across ChromeOS, Android, and production servers rather than accept that risk for the throughput gain.
**Follow-up trap:** *"Does that mean nobody should use io_uring?"* — no; it means the deployment context matters. A trusted, single-tenant, security-hardened environment (a dedicated database or storage engine you control end-to-end) has a very different risk calculus than a shared multi-tenant OS running arbitrary untrusted code, which is exactly why containerd stripped io_uring syscalls from its *default* seccomp profile without banning it outright for workloads that opt in.

### Q6 — What does `sendfile()` actually save, concretely?
**Testing:** whether the syscall/copy-avoidance mechanism is understood with real numbers, not just "it's zero-copy."
**Answer:** A naive file-to-socket transfer loops `read()` (kernel page cache → userspace buffer) then `write()` (userspace buffer → kernel socket buffer) per chunk — two copies and two syscalls per chunk. `sendfile(out_fd, in_fd, ...)` does the transfer inside the kernel in one call, DMA-copying page-cache data straight to the NIC's transmit path without ever landing in userspace. A real measurement moving 2.5GiB showed 2,972 syscalls with sendfile versus 131,093 with read+write — a roughly 44x reduction in syscall count for identical bytes moved.
**Follow-up trap:** *"Would sendfile help an nginx endpoint that gzips on the fly?"* — no. Compression requires the bytes to pass through userspace to be transformed, so sendfile's kernel-only path doesn't apply; zero-copy only helps when the bytes are served unmodified.

### Q7 — When would mmap be the wrong choice for reading a large file?
**Testing:** whether mmap is understood as a real tradeoff, not a free "faster read."
**Answer:** For a single sequential pass over a large file, plain buffered `read()` benefits from kernel readahead tuned for sequential access, while `mmap` faults pages in lazily on first touch — an unpredictable or misconfigured access pattern can produce more minor page faults (each costing roughly 1-10μs) than a straight `read()` loop would, plus mmap has real setup cost building page table entries for the mapping. mmap wins for repeated random-access workloads (memory-mapped databases like LMDB) where amortizing that setup cost across many accesses pays off.
**Follow-up trap:** *"Isn't a page fault basically free since the data's already in the page cache?"* — a minor fault (data present, just needs a page table entry installed) is cheap (~1-10μs) but not zero, and doing it once per 4KB page across a huge sequential scan adds up to real, measurable overhead compared to `read()`'s ability to fill a much larger userspace buffer per syscall with kernel-side readahead already warm.

### Q8 — Your team wants to serve 1 million idle-most-of-the-time WebSocket connections from one box. Walk through the design decision at the I/O-model layer.
**Testing:** applying the whole model to a realistic capacity-planning scenario.
**Answer:** Thread-per-connection is immediately disqualified — even at a conservative 1-2MB per thread stack, 1M threads would need terabytes of address space and the scheduler would thrash long before that. `select`/`poll` are disqualified by the O(n)-per-call cost scaling with 1M mostly-idle descriptors on every wakeup. The right layer is epoll (LT is fine here since connections are mostly idle and per-event overhead isn't the bottleneck) — cost scales with actual activity, not with the million watched-but-idle sockets. io_uring is a possible upgrade if the workload becomes I/O-saturated (many simultaneous reads/writes needing batching), but for mostly-idle long-lived connections epoll's simpler model and smaller attack surface is the sound default.
**Follow-up trap:** *"What's the actual memory cost per idle connection, roughly?"* — a `struct epoll_event` registration plus the kernel socket buffers dominate, not stack space, so per-connection cost is far smaller than thread-per-connection — commonly cited in the low kilobytes per idle connection versus low megabytes per thread, which is the entire reason this architecture scales two to three orders of magnitude further on the same hardware.

### Q9 — What's the difference between `splice()` and `sendfile()`?
**Testing:** whether the more general primitive is understood, since `sendfile` is often (mis)treated as the only zero-copy tool.
**Answer:** `sendfile()` is specifically file-descriptor-to-socket (or more generally, one fd directly to another where the kernel supports it), historically the narrower, older interface. `splice()` is the general primitive: it moves data between a pipe and any other fd (or pipe-to-pipe) without a userspace copy, which is how proxying/relaying data between two arbitrary sockets (not just file-to-socket) can still be zero-copy — nginx and HAProxy use `splice()` for socket-to-socket proxying paths where `sendfile()` wouldn't apply because neither side is a plain file.
**Follow-up trap:** *"So splice can replace sendfile everywhere?"* — sendfile is a simpler, slightly more optimized special case for the file-to-socket path on some kernels/hardware (can leverage scatter-gather DMA more directly); splice is more general but not automatically faster for the specific case sendfile was built for, so production code typically picks whichever matches the actual data path rather than defaulting to the more general one.

### Q10 — A colleague proposes replacing your epoll-based service with io_uring purely for the performance win. What questions do you ask before agreeing?
**Testing:** staff-level judgment — recognizing this is a tradeoff decision, not a pure upgrade.
**Answer:** First, is the workload actually syscall-bound at the volumes you run — profiling (`strace -c`, perf) should show syscall overhead as a real fraction of CPU time before io_uring's batching has anything to amortize; if the bottleneck is elsewhere (application logic, network bandwidth itself), io_uring buys nothing. Second, what's the deployment's trust boundary — is this multi-tenant or running untrusted code where io_uring's CVE history (60%+ of Google's kCTF bounty submissions, ~$1M paid, CVE-2024-0582) is a real exposure, or a trusted single-tenant service where that risk is more acceptable? Third, what's the kernel version and whether seccomp/container runtime policy already restricts io_uring syscalls (containerd's default profile does) — you may need explicit policy changes to even use it.
**Follow-up trap:** *"What if profiling shows real syscall-bound overhead but this is a shared multi-tenant Kubernetes cluster?"* — that's exactly the case where the answer is genuinely "no, or only with heavy sandboxing" — the throughput win doesn't override the security posture in a shared-tenancy environment, and the honest answer is naming that tension rather than picking one side reflexively.

### Q11 — Why does `select()` cap out at `FD_SETSIZE` (typically 1024), and why can't you just raise it?
**Testing:** understanding a specific, quotable historical limitation rather than vague "select is old" hand-waving.
**Answer:** `FD_SETSIZE` is a compile-time constant sizing the fixed-size bitmap `fd_set` uses to represent watched descriptors; it's baked into the glibc header and ABI at build time, so while you technically *can* recompile with a larger value, doing so isn't portable and doesn't fix the deeper O(n)-per-call scanning cost that made select unsuitable for high-fd-count workloads in the first place — `poll()` removes the hard cap (dynamically sized array) but keeps the O(n) scan, and only epoll fixes the actual algorithmic problem.
**Follow-up trap:** *"So poll() solves C10K?"* — no, poll only solves the *hard descriptor cap*, not the throughput problem; it's still O(n) per call, so at genuinely high fd counts with high churn it has the same scaling wall as select, just a higher ceiling before you hit it.

---

## Red flags that fail you

- Describing epoll as "just faster select" without being able to explain the O(1)-vs-O(n) mechanism (kernel-resident interest list + callback-driven ready list).
- Claiming io_uring is unconditionally faster than epoll with no mention of the batching requirement or the unbatched-single-op regression case.
- Recommending io_uring in a multi-tenant/shared-kernel context with no acknowledgment of its CVE history.
- Not knowing the difference between edge-triggered and level-triggered, or claiming ET is "always the better choice" without naming the drain-to-EAGAIN discipline it requires.
- Treating `mmap` as strictly faster than `read()` with no caveat about sequential-scan/readahead workloads.
- Claiming zero-copy helps compression/encryption/transform paths.

---

## Cheat card

```
BLOCKING: 1 thread/conn, ~1-8MB stack each -> C10K wall (Kegel, 1999)
SELECT: O(n)/call, FD_SETSIZE cap ~1024, stateless across calls
POLL: O(n)/call, no fd cap, still rescans everything every call
EPOLL (Linux 2.5.44, 2002): interest list IN kernel (rbtree), ready-list via
  driver callbacks -> epoll_wait is O(1) per READY event, not O(n) watched
  LT (default): re-fires while fd stays ready. ET: fires once on transition,
  MUST read-loop to EAGAIN or you silently stall.
IO_URING (Linux 5.1, 2019): SQ/CQ shared-memory rings, syscall only at
  io_uring_enter() (can batch N ops/1 syscall). SQPOLL = kernel thread polls
  SQ -> 0 syscalls steady-state, but burns 1 full core.
  100K conns: epoll ~15-25% CPU in syscalls; io_uring+SQPOLL cuts syscalls ~80%
  Unbatched single-op io_uring can be SLOWER than epoll -- batching is the win.
  SECURITY: ~60% of Google kCTF bounty submissions target io_uring, ~$1M paid,
  CVE-2024-0582 (UAF, freed-page R/W) -> disabled by default: ChromeOS/Android/
  Google prod; containerd dropped it from default seccomp profile.
SENDFILE: file->socket, kernel-only copy. 2.5GiB: 2,972 syscalls (sendfile)
  vs 131,093 (read+write) = ~44x fewer syscalls. No benefit if data is
  transformed (gzip, encryption) in userspace.
SPLICE: general pipe<->fd zero-copy (socket-to-socket proxying, unlike sendfile)
MMAP: page-cache pages mapped into address space, no read()/write() copy.
  Good: random-access repeated reads (LMDB). Bad: one-pass sequential scan
  (loses kernel readahead, pays per-page minor-fault cost, ~1-10us each)
ZERO-COPY BREAK-EVEN: roughly 10-100KB transfer size depending on workload
```

## Sources

- [io_uring vs epoll — Linux Kernel Internals](https://kernel-internals.org/io-uring/io-uring-vs-epoll/) — accessed 2026-08-03
- [io_uring is slower than epoll · Issue #189, axboe/liburing](https://github.com/axboe/liburing/issues/189) — accessed 2026-08-03
- [Google Limiting IO_uring Use Due To Security Vulnerabilities — Phoronix](https://www.phoronix.com/news/Google-Restricting-IO_uring) — accessed 2026-08-03
- [oss-security — CVE-2024-0582 io_uring use-after-free writeup](https://www.openwall.com/lists/oss-security/2024/04/24/3) — accessed 2026-08-03
- [Consider removing io_uring syscalls from RuntimeDefault · Issue #9048, containerd/containerd](https://github.com/containerd/containerd/issues/9048) — accessed 2026-08-03
- [Linux Zero-Copy Using sendfile() — CocCoc Techblog](https://medium.com/swlh/linux-zero-copy-using-sendfile-75d2eb56b39b) — accessed 2026-08-03
- [splice, sendfile, and Zero-Copy — Linux Kernel Internals](https://kernel-internals.org/io/splice-sendfile/) — accessed 2026-08-03
- [The Zero Copy Principle with Apache Kafka](https://gautambangalore.medium.com/the-zero-copy-principle-with-apache-kafka-749dfd2ef2df) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
