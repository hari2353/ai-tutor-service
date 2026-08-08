# Debuggers Everywhere: pdb, delve, jdb/IntelliJ, node --inspect, rust-gdb

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 2.5h · **Prereqs:** T27-debug-methodology
> **Module id:** `T27-debug-any-language` · **Tags:** debugging, critical

## The 30-second version

Every mainstream language's debugger converges on the same five primitives — breakpoint, step-over, step-into, inspect locals, evaluate an expression — because they're solving the same problem (pause execution, inspect state, resume) against different runtimes, and the actual skill transferring across languages is knowing which invocation gets you there fast, not relearning debugging from scratch each time. Python: `breakpoint()` in source or `python -m pdb -c continue script.py` for post-mortem, `ipdb` as the drop-in nicer frontend. Go: `dlv debug`, `dlv attach <pid>`, or `dlv exec ./binary`, with `break`, `continue`, `next`, `step`, `print`. Java: `jdb` for the raw JDWP client, but in practice almost always IntelliJ's remote-debug config pointed at a JVM started with `-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005`. Node: `node --inspect` (attach any time) versus `node --inspect-brk` (pause on line one, wait for attach) plus `chrome://inspect`. Rust: `rust-gdb`/`rust-lldb`, thin wrappers around gdb/lldb that load pretty-printers so `Option::Some(42)` prints as itself instead of raw struct bytes. The one non-obvious fact that matters across all of them: `--inspect-brk`/`suspend=y`/`dlv exec` (as opposed to `--inspect`/`suspend=n`/running-and-attaching) exist specifically to catch bugs in code that runs before you could otherwise attach — startup-time initialization, module-load-time bugs, the first few requests.

## Why this gets asked

Because a polyglot engineer who's fluent debugging Python but freezes or reaches for `print` statements the moment they're handed a Go or Rust service is a real, common gap interviewers have seen — and because "attach a debugger to a running process you didn't start in debug mode" is a specific, non-obvious skill (most engineers only know how to launch something already wired for debugging) that separates people who've actually done on-call for polyglot production systems from people who've only debugged in their local IDE with defaults pre-configured.

---

## Lineage: past → present → future

**What came before.** Command-line, single-language debuggers (gdb for C/C++, jdb for Java, pdb for Python) each grew independently, tied tightly to their runtime's specific execution model — gdb reads DWARF debug symbols and ptrace's the process directly; jdb speaks the JVM's own wire protocol; pdb hooks CPython's frame-inspection API. This meant genuinely different mental models and invocation syntax per language, with no shared muscle memory, and for compiled languages specifically, debugging was frequently print-statement-only in practice because attaching a real debugger to a running production binary was rare, risky, and poorly supported by comparison to just adding a log line and redeploying.

**Where it stands now.** Every mainstream ecosystem has converged on the same conceptual toolkit (breakpoints, stepping, locals inspection, conditional breaks, remote/attach mode) even though the concrete commands differ — the DAP (Debug Adapter Protocol), introduced by Microsoft for VS Code in 2016, is the closest thing to a real unifying standard, letting one IDE frontend drive gdb, delve, debugpy, and others through a common protocol rather than each needing bespoke IDE integration. What's not unified and still a live pain point: attaching to an already-running production process without restarting it varies enormously in safety and ergonomics by language — Python's `py-spy dump` can inspect a running process without pausing it at all (covered in prod-debugging), Java's JDWP attach is well-supported and safe when the JVM was started with the agent flag but requires a restart if it wasn't, Go's delve can attach to any running process without prior instrumentation (`dlv attach <pid>`) using ptrace directly, and Rust/C++ debugging via gdb/lldb attach works but pretty-printing quality for complex generic types remains inconsistent enough that it's a commonly cited practical annoyance, not a solved problem, as of 2026.

**Where it's heading.** IDE-integrated remote debugging into containers and Kubernetes pods (`kubectl debug`-style ephemeral containers wired directly to a language's debug protocol, one-click "attach to this pod" flows in IntelliJ/VS Code) is real and actively improving, reducing the gap between "debug locally" and "debug the actual thing running in staging/prod." The more speculative direction is AI-assisted interactive debugging — a model driving the actual debugger's stepping and inspection commands based on a stated hypothesis, rather than a human typing `next`/`print` by hand — which exists in early tooling but isn't yet a reliable replacement for a human directing the session, especially for anything beyond straightforward, well-bounded bugs.

---

## Mental model

```
EVERY DEBUGGER = THE SAME FIVE PRIMITIVES, DIFFERENT SYNTAX PER RUNTIME

  BREAKPOINT       -- pause execution at a specific line/function
  STEP OVER        -- run the current line, don't descend into called functions
  STEP INTO        -- run the current line, DO descend into the next called function
  INSPECT LOCALS   -- show variables in the current frame
  EVALUATE         -- run an arbitrary expression in the current frame's context

TWO ATTACH MODES THAT MATTER MORE THAN THE FIVE PRIMITIVES:
  LAUNCH-AND-PAUSE-IMMEDIATELY   catches bugs in code that runs BEFORE you could attach --
   (suspend=y, --inspect-brk,     startup init, module-load side effects, connection setup.
    dlv exec/debug)               Costs: process is frozen until a debugger actually connects.

  ATTACH-TO-ALREADY-RUNNING       for a process already serving traffic; you WILL miss
   (suspend=n, --inspect,         anything that already executed before you attached.
    dlv attach <pid>,             Some attach mechanisms (delve, gdb/lldb via ptrace) can
    jdb -attach)                  attach to a process with ZERO prior instrumentation;
                                   others (Node inspector, JDWP) need the flag present
                                   at process start, so you can't retrofit them onto an
                                   already-running unmodified process.

LANGUAGE  | LAUNCH-DEBUG              | ATTACH-TO-RUNNING        | KEY COMMANDS
----------|---------------------------|---------------------------|---------------------------
Python    | python -m pdb script.py   | (no native pid-attach;    | b, c, n, s, p, l, where,
          | or breakpoint() inline    |  py-spy for read-only,    | pp, up/down, pdb.pm()
          |                           |  see prod-debugging)      |
Go        | dlv debug ./main.go       | dlv attach <pid>          | break, continue, next,
          |                           | (ptrace, no prior         | step, print, bt
          |                           |  instrumentation needed)  |
Java      | java -agentlib:jdwp=...   | jdb -attach <port>        | stop at, cont, next, step,
          | suspend=y (pause at start)| (JVM MUST have started    | print, locals, threads
          |                           |  with the jdwp agent flag)|
Node      | node --inspect-brk app.js | node --inspect app.js     | chrome://inspect UI, or
          |                           | (attach any time after)   | debugger; statement inline
Rust      | rust-gdb ./target/debug/x | rust-gdb -p <pid>         | break, run, next, step,
          | rust-lldb ./target/.../x |                            | info locals/print, bt
```

## How it actually works

**Python: `pdb`/`ipdb`, and specifically post-mortem debugging.** `breakpoint()` (Python 3.7+) drops into whatever debugger `PYTHONBREAKPOINT` points at — `pdb` by default, or set `PYTHONBREAKPOINT=ipdb.set_trace` to route to ipdb's nicer frontend (tab completion, syntax highlighting) without changing source code. Setting `PYTHONBREAKPOINT=0` disables every `breakpoint()` call process-wide — the correct way to guarantee a stray debug call never hangs a production deployment waiting on stdin. Post-mortem debugging — entering the debugger *after* an unhandled exception, at the exact frame it died in — is the highest-leverage Python debugging technique for "it crashed once and I need to see the state at the moment it died": run `python -m pdb -c continue script.py` to run the script under pdb and drop into an interactive session at the exception, or call `pdb.pm()` interactively right after a crash in a REPL/notebook to inspect the most recent traceback's frames. Inside any pdb session: `w`/`where` for the full stack, `p expr` to evaluate, `pp expr` for pretty-printed output, `u`/`d` to move up/down frames, `l` to list surrounding source, `c` to continue, `n`/`s` for step-over/step-into.

**Go: `dlv` (delve), and specifically attach-without-instrumentation.** `dlv debug ./cmd/server` compiles and launches under the debugger directly. `dlv exec ./already-built-binary` runs a pre-built binary under delve. The mechanically important one: `dlv attach <pid>` attaches to an already-running process with zero prior flags or instrumentation required — delve uses ptrace directly against the live process, the same low-level mechanism gdb uses, which is why it works on an unmodified running Go binary in a way Node's inspector or JDWP fundamentally cannot (those require an agent/flag present at process start). Inside a delve session: `break main.go:42` or `break pkg.FuncName`, `continue`/`c`, `next`/`n` (step over), `step`/`s` (step into), `print`/`p expr`, `locals` for all local variables in the current frame, `bt` for backtrace, `goroutines` to list all goroutines (critical for a deadlock or leaked-goroutine investigation), and `goroutine <n> bt` to backtrace a specific one.

**Java: `jdb` exists, but IntelliJ remote debug via JDWP is what's actually used.** JDWP (Java Debug Wire Protocol) is the underlying network protocol; `jdb` is the JDK's bare command-line client for it, rarely used directly outside minimal environments with no IDE access. The practical setup: start the target JVM with `-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005` — `server=y` means this JVM is the one being debugged (waits for a debugger to connect, doesn't initiate), `suspend=n` means the JVM starts running immediately without waiting for a debugger (use `suspend=y` specifically when you need to catch a bug in class-loading or static-initializer code that runs before you could otherwise attach), `address=*:5005` is the port a debugger connects to. In IntelliJ: Run > Edit Configurations > Remote JVM Debug, point host/port at the target, attach. Once attached, IntelliJ's breakpoints, stepping, and "Evaluate Expression" (which can call arbitrary methods on live objects, including ones with side effects — be careful evaluating anything non-idempotent against production state) all work identically to local debugging. `jdb` itself, if you're stuck with only a terminal: `jdb -attach 5005`, then `stop at ClassName:42`, `cont`, `next`, `step`, `print expr`, `locals`, `threads` to list all threads and `thread <id>` to switch context — mechanically the same five primitives, uglier syntax.

**Node: `--inspect` vs `--inspect-brk`, and where the debugger actually attaches.** `node --inspect app.js` starts the process running immediately and opens a WebSocket-based inspector protocol port (default 9229) that a debugger (Chrome DevTools via `chrome://inspect`, VS Code, WebStorm) can attach to at any later point — anything that already ran before attach is invisible. `node --inspect-brk app.js` pauses execution on the very first line and waits for a debugger to connect before running anything, which is the only way to catch a bug in module-top-level code or an early `require`/`import` side effect. `node --inspect=9230 app.js` picks a specific port when the default is already in use or firewalled. Inline, a `debugger;` statement in source acts as a breakpoint exactly like one set in the DevTools UI, and only has effect while a debugger is actually attached — otherwise it's a no-op, which is why leaving one in committed code isn't itself dangerous, just noise.

**Rust: `rust-gdb`/`rust-lldb` are the same gdb/lldb with Rust-aware pretty-printing loaded.** Plain `gdb ./target/debug/myprogram` works but prints Rust enums/generics as raw memory layout (a tag byte and a union of possible variants, not `Some(42)`); `rust-gdb`/`rust-lldb` are wrapper scripts that auto-load Rust's pretty-printer Python scripts, so the exact same debugging session shows `core::option::Option<i32>::Some(42)` instead. Standard flow: `rust-gdb ./target/debug/myprogram`, `break src/main.rs:15` or `break myprogram::function_name`, `run` (with args after `run` if needed), `next`/`step`, `print variable`, `info locals` for all locals in the frame, `backtrace`/`bt`. LLDB's equivalent commands use a different verb structure — `breakpoint set --name factorial` or `breakpoint set --file main.rs --line 15`, `watchpoint set variable <name>` to break on a variable's value changing (mechanically distinct from a regular breakpoint, and the right tool when you know *what* changed but not *where* in the code it happened) — and both gdb and lldb support a "run this command automatically every time execution stops" hook (`display <expr>` in gdb, `target stop-hook add -o "p <expr>"` in lldb) useful for watching one variable across many step commands without retyping `print` each time.

## Build it from scratch

```bash
# --- Python: breakpoint, post-mortem, and disabling it for prod ---
python3 -c "
def divide(a, b):
    breakpoint()          # drops into pdb (or ipdb if PYTHONBREAKPOINT is set) right here
    return a / b
divide(4, 0)
"
# post-mortem on an already-crashed script, entering the debugger at the exception frame:
python -m pdb -c continue crashing_script.py
# inside pdb: where | p locals() | pp some_var | up | down | n | s | c | q
PYTHONBREAKPOINT=0 python3 app.py            # disables ALL breakpoint() calls process-wide

# --- Go: launch-debug, attach-to-running, goroutine inspection ---
dlv debug ./cmd/server -- --port=8080        # compile + launch under delve, pass app args after --
dlv attach $(pgrep -f myserver)               # attach to an ALREADY RUNNING unmodified binary
# inside dlv: break main.handleRequest | continue | next | step | print req | locals
#             goroutines                        -- list all goroutines, look for stuck ones
#             goroutine 17 bt                    -- backtrace a specific suspected-deadlocked one

# --- Java: start with JDWP agent, attach from IntelliJ or jdb ---
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar app.jar
# IntelliJ: Run > Edit Configurations > + > Remote JVM Debug > host=<target>, port=5005 > Debug
# bare jdb, if no IDE access:
jdb -attach 5005
# > stop at com.example.OrderService:88
# > cont
# > locals
# > print order.getStatus()

# --- Node: inspect vs inspect-brk ---
node --inspect server.js                      # runs immediately, attach anytime after via chrome://inspect
node --inspect-brk server.js                  # PAUSES on line 1 -- catches module-load-time bugs
node --inspect=0.0.0.0:9230 server.js         # bind to all interfaces, non-default port (container use)
# in source: `debugger;` -- no-op unless a debugger is actually attached

# --- Rust: pretty-printed enums, watchpoints ---
rust-gdb ./target/debug/myprogram
# (gdb) break src/main.rs:22
# (gdb) run --some-arg value
# (gdb) print my_option              # shows Some(42), not raw bytes, thanks to pretty-printers
# (gdb) watch my_struct.counter      # breaks whenever this specific value changes, not a fixed line
# (gdb) bt
rust-lldb ./target/debug/myprogram
# (lldb) breakpoint set --file main.rs --line 22
# (lldb) watchpoint set variable my_struct.counter
```

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| `node --inspect` attached, but the bug (a wrong value from a top-level `const` computed at module load) never shows up in the debugger | `--inspect` doesn't pause execution — anything before attach already ran | Use `--inspect-brk` specifically for module-load-time or startup-sequence bugs; accept the tradeoff that the process is frozen until something actually connects |
| JDWP attach from IntelliJ fails to connect at all | Target JVM wasn't started with the `-agentlib:jdwp=...` flag, or the port is blocked by a firewall/security group between IntelliJ and the target | Confirm the flag was present at JVM startup (it can't be added to an already-running JVM without a restart) and that the port is reachable from where IntelliJ is running, not just from the target host itself |
| `dlv attach <pid>` works locally but fails in a container/Kubernetes pod | Delve's ptrace-based attach needs `CAP_SYS_PTRACE` (or running as the same user/privileged), which many container security policies strip by default | Add `CAP_SYS_PTRACE` (or `securityContext.capabilities.add: [SYS_PTRACE]` in Kubernetes) to the specific container, or use an ephemeral debug container/sidecar sharing the target's PID namespace instead of attaching from outside |
| Python `breakpoint()` left in code accidentally ships to production and hangs a request indefinitely | `PYTHONBREAKPOINT` wasn't disabled in the production environment, so the stray call waits on stdin that will never receive input in a server context | Set `PYTHONBREAKPOINT=0` as a standing production environment variable, not something remembered per-deploy; treat this as infrastructure, not developer discipline |
| `rust-gdb` shows a Rust `Option`/`Result`/generic struct as raw bytes instead of a readable value | Plain `gdb`/`lldb` used instead of the `rust-gdb`/`rust-lldb` wrapper, so Rust's pretty-printer scripts were never loaded | Always use the `rust-` prefixed wrapper for Rust binaries; if working through another tool (an IDE's built-in debugger) confirm it's actually invoking the Rust-aware variant, not bare gdb/lldb underneath |
| A Go service is stuck; `dlv attach` shows 400 goroutines and no obvious starting point | No triage strategy for goroutine dumps — reading all 400 individually | `goroutines` first for the full list, then group visually by the function they're blocked in (delve's output groups similar stacks); goroutines piled up waiting on the same channel/mutex are the signal, not the exact count |
| `jdb` session drops or hangs mid-investigation on a production JVM under load | `jdb`'s raw JDWP client isn't designed for sustained interactive use against a busy production JVM, and manually stepping through a live, request-serving process risks pausing it long enough to trip health checks or timeouts | Prefer non-invasive tools for a live production JVM (thread/heap dumps via `jstack`/`jcmd`, covered in prod-debugging) over an interactive attach-and-step session; reserve interactive JDWP attach for staging/reproducible environments, not live production traffic |

## Tradeoffs & when NOT to use it

- **Don't attach an interactive debugger to a live, traffic-serving production process as a first move.** Stepping through code pauses that specific execution, which can trip upstream timeouts, health checks, or cause cascading retries — for production, prefer non-invasive tools first (logs, traces, `py-spy dump`, `jstack`, core dumps — see prod-debugging), and reserve interactive attach for staging/reproducible environments or for a deliberate, communicated, brief production investigation.
- **Don't use `suspend=y`/`--inspect-brk`/`dlv exec` (pause-immediately) by default** — freezing the process until a debugger connects is exactly wrong for the common case (you already know roughly where the bug is, mid-execution) and only earns its cost for the specific case of startup/module-load bugs.
- **Don't reach for a full interactive debugger when a simpler tool answers the question faster.** "What's this variable's value right now" is often faster with a single well-placed log line and a redeploy in a fast-iterating environment than standing up remote debugging infrastructure — the debugger earns its cost specifically when you need to inspect complex, hard-to-log state (a large object graph, exact call-stack context) or step through nontrivial control flow.
- **Rust/C++ debugging via gdb/lldb still has real, acknowledged gaps** — pretty-printing for deeply generic types or async/await state machines (which the compiler transforms into anonymous state-machine structs) is meaningfully worse than debugging equivalent Python or Java state; don't expect it to be as smooth, and budget more time for reading raw structure when pretty-printers fall short.

---

## Interview questions

### Q1 — What's the practical difference between `node --inspect` and `node --inspect-brk`, and when does the difference actually matter?
**Testing:** whether the candidate knows this is about timing relative to attach, not just "two flags that start debugging."
**Answer:** `--inspect` starts the process running immediately and opens the inspector port for attaching at any later point — anything that executed before attach is simply invisible to the debugger. `--inspect-brk` pauses execution on the very first line and won't proceed until a debugger actually connects. It matters specifically for bugs in code that runs before you'd otherwise have a chance to attach: module-top-level initialization, an early `require`/`import` side effect, connection setup that happens once at startup.
**Follow-up trap:** *"You use `--inspect-brk` on a service that other processes depend on being up quickly. What's the operational risk?"* — the process is genuinely frozen, not just slow, until something connects a debugger — if this is done against a service other things health-check or depend on starting promptly, you can trip a liveness probe or cause dependent services to fail their own startup, so `--inspect-brk` needs to be used deliberately in an isolated or communicated context, not as a routine default.

### Q2 — `dlv attach <pid>` can attach to an already-running Go binary with zero prior instrumentation. Why can't Node's inspector or Java's JDWP do the same thing?
**Answer:** Delve's attach uses `ptrace` directly against the live process at the OS level, the same low-level mechanism `gdb`/`rust-gdb` use — it doesn't require the target process to have been started with any special flag. Node's inspector protocol and Java's JDWP are both application/runtime-level protocols that the process itself has to open a listening port for, which means the flag (`--inspect`/`-agentlib:jdwp=...`) has to be present when the process starts; there's no way to retrofit that listening capability onto a process already running without it.
**Follow-up trap:** *"So can you ptrace-attach to a running Node or Java process too, bypassing the flag requirement?"* — you can attach a raw OS-level debugger like gdb to any process via ptrace regardless of language, but you'd be debugging at the level of the underlying runtime's C/C++ implementation (V8's internals, the JVM's own native code) rather than getting meaningful JavaScript or Java-level stack frames, variable names, or line numbers — which is why practically speaking, without the language-level flag present at startup, you're stuck with much lower-level, much less useful debugging than the intended workflow provides.

### Q3 — Explain what `suspend=y` versus `suspend=n` actually controls in a JDWP connection string, precisely.
**Answer:** It controls whether the JVM waits for a debugger to actually connect before executing any application code. `suspend=y` means the JVM starts, initializes the JDWP agent, and then blocks — no application code runs — until a debugger attaches; this is the JVM-level equivalent of Node's `--inspect-brk`, needed to catch bugs in static initializers or class-loading-time side effects. `suspend=n` means the JVM starts and runs immediately, with the JDWP port simply available for a debugger to connect to whenever, matching plain `--inspect`.
**Follow-up trap:** *"A teammate sets `suspend=y` on a production JVM as a standing default 'just in case they need to debug something.' What's wrong with that?"* — every restart of that JVM (a deploy, a crash-restart, an autoscale event) now hangs indefinitely waiting for a debugger connection that usually isn't coming, which will look exactly like a hung, unresponsive deployment to anything monitoring startup — `suspend=y` should be a deliberate, temporary choice for an active debugging session, never a standing production configuration.

### Q4 — You need to debug a deadlock in a running Go service using delve. What's your actual investigation sequence?
**Answer:** `dlv attach <pid>` to the live process (no restart needed, since delve uses ptrace directly). Run `goroutines` to list all goroutines and their current state/location — a deadlock typically shows a cluster of goroutines blocked on the same channel operation or mutex, distinguishable from goroutines simply idle waiting for work. Pick a representative blocked goroutine, `goroutine <id> bt` to see its exact call stack at the point of blocking, and cross-reference against another blocked goroutine's stack to identify the actual lock-ordering or channel-direction mismatch causing the mutual block.
**Follow-up trap:** *"You attach delve and the process's health check starts failing while you're investigating. Why, and what should you have anticipated?"* — attaching a debugger via ptrace and especially pausing execution while inspecting goroutines can itself delay request handling enough to trip a liveness/readiness probe that was already borderline before you attached (since the service was already deadlocked or degraded) — anticipate this by either working in a non-serving replica/staging instance, briefly pulling the target out of the load balancer rotation before attaching, or accepting and communicating the operational risk explicitly rather than being surprised by it.

### Q5 — What does `rust-gdb` actually add over plain `gdb` when debugging a Rust binary, mechanically?
**Answer:** `rust-gdb` is a wrapper script that auto-loads Rust-specific pretty-printer Python scripts into the gdb session before you start debugging. Without them, gdb shows Rust's enums (like `Option`/`Result`) and generics as raw memory layout — a discriminant tag byte plus a union of possible variant data — because gdb has no built-in understanding of Rust's type system; with the pretty-printers loaded, the same memory prints as `Some(42)` or `Err("message")`, matching how the value would actually be written in source.
**Follow-up trap:** *"Your team's Rust binary is debugged inside a Docker container using a stripped-down base image. `rust-gdb` reports it can't find the pretty-printer scripts. What's the underlying cause?"* — the pretty-printer Python scripts ship alongside a full Rust toolchain installation (via rustup) or specific compiler-associated files, and a minimal container image built for running the compiled binary (not for compiling or debugging it) frequently doesn't include them — the fix is either installing the matching Rust toolchain's debug-support files inside the debugging environment, or debugging from a host/container that has the full toolchain installed rather than the minimal runtime image the binary actually ships in.

### Q6 — A candidate says "I always just add print statements, I don't really use debuggers." Under what circumstances is that actually a defensible position, and when does it fail?
**Answer:** Defensible for simple, fast-iterating environments where redeploying with an extra log line costs seconds and the state you need is a small number of scalar values — the overhead of standing up remote debugging infrastructure genuinely isn't worth it. It fails for anything requiring inspection of complex state (a large object graph, many interacting local variables across a deep call stack), for bugs that only manifest under conditions hard to reproduce with a quick redeploy-and-check loop, or for any environment where redeploying to add a print statement is itself slow/expensive (a long CI/CD pipeline, a production incident where every redeploy risks further destabilizing things).
**Follow-up trap:** *"The bug is in a live production incident, mid-outage, in a language you know well. Print-statement-and-redeploy or attach a debugger?"* — attach a debugger (non-invasively where possible — favor a dump/snapshot mechanism like `py-spy dump` or `jstack` over an interactive stepping session during an active incident) rather than redeploy-with-logging, specifically because redeploying mid-incident adds deployment risk and delay on top of an already-degraded system, whereas a read-mostly attach/dump gets you state faster without another deploy cycle in the loop.

### Q7 — How would you catch a bug that only manifests in a module's top-level code, executed once at import/require time, in both Python and Node?
**Answer:** Node: `node --inspect-brk app.js`, which pauses on the very first line before any module code (including top-level `require`/`import` side effects) executes, then step through from there. Python doesn't have a direct equivalent single flag for "pause before any module code runs" in the same way, but the practical approach is placing an explicit `breakpoint()` call at the very top of the specific module suspected of the bug (or using `python -m pdb script.py`, which starts pdb before running the script at all, letting you set a breakpoint on the suspect module before it's imported, then `continue`).
**Follow-up trap:** *"The Python bug is in a module imported deep in a dependency chain, not the top-level script itself. Does `python -m pdb script.py` still help directly?"* — yes, but requires setting a breakpoint explicitly on the target module/line before continuing (`b module_path.py:line` at the pdb prompt before your first `c`), since `python -m pdb` pauses before the script begins but doesn't automatically stop at every nested import — you need to know or guess which module to break in ahead of time, which loops back to needing at least a rough hypothesis (from the methodology module) about where the bug lives before you can set the right breakpoint.

### Q8 — Compare LLDB's `watchpoint set variable` to a regular breakpoint. What kind of bug is a watchpoint specifically the right tool for?
**Answer:** A regular breakpoint stops execution at a specific line or function regardless of what state is at that point. A watchpoint stops execution whenever a specific variable's value actually changes, regardless of where in the code that happens. It's the right tool when you know *what* value became wrong but have no idea *where* in a large codebase it got corrupted — setting a watchpoint on that variable and continuing will stop exactly at the line that changes it, even if that line is somewhere you'd never have thought to place a breakpoint.
**Follow-up trap:** *"You set a watchpoint on a struct field and it never triggers, even though you're certain the value changes somewhere. What are two possible reasons, mechanically?"* — (1) the value is being changed through a different memory location than the one the watchpoint is tracking — e.g., an alias, a raw pointer, or a copy of the struct being mutated instead of the original — so the watchpoint on the specific address you set it against genuinely isn't the memory being written; (2) hardware watchpoint limits (most architectures support only a small fixed number of hardware watchpoints, often 4) have been exceeded and the debugger silently fell back to a slower software watchpoint or failed to set it at all, which some debugger/OS/architecture combinations handle by just not triggering rather than erroring loudly.

### Q9 — Why is IntelliJ's "Evaluate Expression" feature during a live remote-debug session against a shared staging or production JVM something to be careful with, specifically?
**Answer:** Evaluate Expression can invoke arbitrary methods on live objects in the paused JVM's actual memory, including methods with real side effects — calling a method that mutates state, sends a network request, or writes to a database isn't a read-only inspection at that point, it's an actual production/staging-affecting action taken from inside a debugger session, easy to do accidentally by evaluating something that looks like a harmless getter but isn't.
**Follow-up trap:** *"How do you tell, before evaluating an expression, whether it's actually safe (read-only) to run?"* — check the method's actual implementation (not just its name — a method named `getStatus()` could still have side effects if poorly designed) for anything beyond reading and returning a value: no writes, no I/O, no mutation of shared state; if there's any doubt and the target is a shared or production JVM, don't evaluate it live — reproduce the same call against a local or isolated instance first instead.

### Q10 — You're debugging a Kubernetes-deployed Go service and `dlv attach <pid>` fails with a permissions error inside the pod. Diagnose and fix.
**Answer:** Delve's attach relies on `ptrace`, which requires the `CAP_SYS_PTRACE` capability (or root) — most container security policies strip this by default as a hardening measure, since ptrace access is also a privilege-escalation and container-escape-adjacent vector if misused. Fix: add `securityContext.capabilities.add: [SYS_PTRACE]` to the specific container's pod spec (temporarily, for the debugging session, not as a standing production default), or use an ephemeral debug container (`kubectl debug --target=<container> --image=<image-with-delve>`) sharing the target's PID namespace instead of trying to attach from a process outside the pod's namespace boundary entirely.
**Follow-up trap:** *"Security wants to know why granting SYS_PTRACE even temporarily is acceptable here, given it's flagged as risky in general.** How do you frame the tradeoff?"* — scope it as narrowly and temporarily as possible: apply it to a specific pod/container for the duration of an active investigation (not cluster-wide, not as a default in the deployment manifest), and prefer the ephemeral-debug-container approach where the elevated capability lives in a short-lived sidecar rather than the long-running production container itself, which limits the window and blast radius of the elevated privilege considerably compared to a standing grant.

---

## Red flags that fail you

- Not knowing the difference between attach-anytime (`--inspect`, `suspend=n`) and pause-until-attached (`--inspect-brk`, `suspend=y`) modes, or when each is actually needed.
- Believing every language's debugger can attach to an unmodified already-running process the way delve/gdb can — Node's inspector and JDWP both require a flag present at process start.
- Reaching for an interactive attach-and-step session as a first move against live, traffic-serving production processes instead of non-invasive tools.
- Using plain `gdb`/`lldb` on a Rust binary and not knowing why enums/generics print as raw bytes instead of using `rust-gdb`/`rust-lldb`.
- Evaluating an expression with unknown side effects against a live shared JVM without checking the method's actual implementation first.
- Not knowing that `PYTHONBREAKPOINT=0` exists as the standing production safeguard against a stray `breakpoint()` call.
- Confusing a watchpoint (triggers on value change, anywhere) with a breakpoint (triggers at a specific line, regardless of value) and reaching for the wrong one.

## Cheat card

```
5 UNIVERSAL PRIMITIVES: breakpoint, step-over, step-into, inspect locals, evaluate expression

2 ATTACH MODES THAT MATTER MOST:
  pause-until-attached (suspend=y / --inspect-brk / dlv exec)  -- catches startup/module-load bugs
  attach-anytime        (suspend=n / --inspect / dlv attach)   -- misses anything before you connect

PYTHON:  breakpoint()  inline  |  python -m pdb -c continue script.py   -- post-mortem
         PYTHONBREAKPOINT=ipdb.set_trace   -- nicer frontend, no code change
         PYTHONBREAKPOINT=0                -- disable ALL breakpoint() calls (standing prod safeguard)
         pdb.pm()  -- post-mortem on last traceback, interactively
         cmds: w(here) p(rint) pp u(p) d(own) l(ist) n(ext) s(tep) c(ontinue)

GO:      dlv debug ./cmd/x   |  dlv exec ./binary   |  dlv attach <pid>  (ptrace, NO prior flag needed)
         cmds: break, continue, next, step, print, locals, bt, goroutines, goroutine <n> bt

JAVA:    java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar app.jar
         suspend=y = pause at JVM start until debugger connects (catches static-init bugs)
         IntelliJ: Run > Edit Configurations > Remote JVM Debug, point at host:port
         jdb -attach <port>  -- raw CLI client, needs the flag present at JVM START (can't retrofit)
         cmds: stop at Class:line, cont, next, step, print, locals, threads, thread <id>

NODE:    node --inspect app.js        -- runs now, attach anytime, misses what already ran
         node --inspect-brk app.js    -- pauses line 1, catches module-load-time bugs
         chrome://inspect  or  debugger;  statement (no-op unless debugger attached)

RUST:    rust-gdb / rust-lldb  -- gdb/lldb + Rust pretty-printers (Some(42), not raw bytes)
         gdb: break, run, next, step, print, info locals, bt, watch <expr>
         lldb: breakpoint set --name/--file/--line, watchpoint set variable <name>
         watchpoint = triggers on VALUE CHANGE anywhere; breakpoint = triggers at a LOCATION

DON'T: interactive-attach live prod traffic as first move. USE non-invasive dumps
  (py-spy dump, jstack, core dump -- see prod-debugging) for a live serving process instead.

K8s/containers: dlv attach needs CAP_SYS_PTRACE -- stripped by most security policies by default.
  Use an ephemeral debug container / kubectl debug --target=<c> sharing the pod's PID namespace.
```

## Sources

- [Delve User Guide — DeepWiki](https://deepwiki.com/go-delve/delve/5-user-guide) — accessed 2026-07-28
- [delve/Documentation/cli/README.md — GitHub](https://github.com/go-delve/delve/blob/master/Documentation/cli/README.md) — accessed 2026-07-28
- [How to use node --inspect in Node.js — CoreUI](https://coreui.io/answers/how-to-use-node-inspect-in-nodejs/) — accessed 2026-07-28
- [Debugging Node.js — Node.js Learn (official docs)](https://nodejs.org/learn/getting-started/debugging) — accessed 2026-07-28
- [Tutorial: Remote debug — IntelliJ IDEA Documentation](https://www.jetbrains.com/help/idea/tutorial-remote-debug.html) — accessed 2026-07-28
- [Java debugging: how to debug Java code in IntelliJ, Eclipse, and jdb — Bugfender](https://bugfender.com/blog/debugging-java/) — accessed 2026-07-28
- [Debugging Rust Applications: A Comprehensive Guide — reintech](https://reintech.io/blog/debugging-rust-applications-guide) — accessed 2026-07-28
- [Rust specific tools: rust-gdb, rust-lldb — KodeKloud notes](https://notes.kodekloud.com/docs/Rust-Programming/Debugging-in-Rust/Rust-specific-tools-rust-gdb-rust-lldb/page) — accessed 2026-07-28
- [pdb — The Python Debugger (official docs)](https://docs.python.org/3/library/pdb.html) — accessed 2026-07-28
- [ipdb · PyPI](https://pypi.org/project/ipdb/) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
