"""Harness skeleton: context window + compaction, risk-gated tool router, budgeted loop, kill switch."""
import json
import time


class SystemClock:
    def now(self):
        return time.monotonic()


class FakeClock:
    def __init__(self, t=0):
        self._t = t

    def now(self):
        return self._t

    def advance(self, dt):
        self._t += dt


def _default_tokenizer(s):
    return max(1, len(s) // 4)


class ContextWindow:
    def __init__(self, cap, tokenizer=None, summarizer=None):
        self.cap = cap
        self.tok = tokenizer or _default_tokenizer
        self.summarizer = summarizer or (lambda dropped: f"[summary of {len(dropped)} dropped messages]")
        self._msgs = []          # list of [text, pinned]

    def tokens(self):
        return sum(self.tok(t) for t, _ in self._msgs)

    def messages(self):
        return [(t, p) for t, p in self._msgs]

    def add(self, msg, pinned=False):
        self._msgs.append([msg, pinned])
        if self.tokens() <= self.cap:
            return
        # one-shot compaction: drop oldest non-pinned messages until we fit,
        # then insert a single summary message after the pinned prefix
        dropped = []
        while self.tokens() > self.cap:
            idx = next((i for i, (t, p) in enumerate(self._msgs) if not p), None)
            if idx is None:
                break  # pinned alone exceeds cap; nothing more we can do
            dropped.append(self._msgs[idx][0])
            self._msgs = self._msgs[:idx] + self._msgs[idx + 1:]
        if dropped:
            summary = self.summarizer(dropped)
            insert_at = 0
            for i, (t, p) in enumerate(self._msgs):
                if p:
                    insert_at = i + 1
            # replace a previous summary (at insert_at, if present) instead of stacking
            if (insert_at < len(self._msgs)
                    and self._msgs[insert_at][0].startswith("[SUMMARY")):
                self._msgs.pop(insert_at)
            self._msgs.insert(insert_at, [summary, False])
            # if the summary itself pushes us over, drop one more non-pinned non-summary
            while self.tokens() > self.cap:
                idx = next((i for i, (t, p) in enumerate(self._msgs)
                            if not p and not t.startswith("[SUMMARY")), None)
                if idx is None:
                    break
                self._msgs = self._msgs[:idx] + self._msgs[idx + 1:]


class ToolError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class PermissionDenied(Exception):
    pass


class ToolRouter:
    def __init__(self):
        self._tools = {}

    def register(self, name, fn, schema, risk):
        assert risk in ("read_only", "side_effect", "destructive")
        self._tools[name] = (fn, schema, risk)

    def call(self, name, args, approver=None):
        if name not in self._tools:
            raise ToolError(f"unknown tool: {name}", retryable=False)
        fn, schema, risk = self._tools[name]
        missing = [k for k in schema.get("required", []) if k not in args]
        if missing:
            raise ToolError(f"{name}: missing args {missing}", retryable=False)
        if risk == "destructive":
            if approver is None or not approver(name, args):
                raise PermissionDenied(f"destructive tool {name} requires approval")
        try:
            return fn(**args)
        except ToolError:
            raise
        except PermissionDenied:
            raise
        except Exception as e:
            retryable = getattr(e, "retryable", False)
            raise ToolError(f"{name} failed: {e}", retryable=retryable) from e


class EventLog:
    def __init__(self):
        self._events = []

    def append(self, t, kind, payload):
        self._events.append((t, kind, payload))

    def events(self, kind=None):
        if kind is None:
            return list(self._events)
        return [e for e in self._events if e[1] == kind]


class LoopEngine:
    def __init__(self, llm, router, context, cfg, clock):
        self.llm = llm
        self.router = router
        self.ctx = context
        self.cfg = cfg
        self.clock = clock
        self.log = EventLog()
        self.kill_switch = False
        self._consecutive_tool_errors = 0
        self._start_t = None

    def _token_estimate(self):
        return self.ctx.tokens()

    def run(self):
        self._start_t = self.clock.now()
        turns = 0
        stopped_by = None
        while True:
            # --- between-turns checks ---
            if self.kill_switch:
                stopped_by = "kill_switch"
                self.log.append(self.clock.now(), "stop", {"reason": "kill_switch"})
                break
            if turns >= self.cfg.get("max_turns", 10):
                stopped_by = "max_turns"
                self.log.append(self.clock.now(), "stop", {"reason": "max_turns"})
                break
            if self._token_estimate() > self.cfg.get("token_budget", 10 ** 9):
                stopped_by = "token_budget"
                self.log.append(self.clock.now(), "stop", {"reason": "token_budget"})
                break
            if self.clock.now() - self._start_t > self.cfg.get("wallclock_budget", 10 ** 9):
                stopped_by = "wallclock_budget"
                self.log.append(self.clock.now(), "stop", {"reason": "wallclock_budget"})
                break
            if self._consecutive_tool_errors >= self.cfg.get("max_tool_errors", 3):
                stopped_by = "max_tool_errors"
                self.log.append(self.clock.now(), "stop", {"reason": "max_tool_errors"})
                break

            # --- a turn ---
            turns += 1
            msgs = [t for t, _ in self.ctx.messages()]
            reply = self.llm(msgs)
            self.ctx.add(f"assistant: {reply}")
            self.log.append(self.clock.now(), "reply", {"turn": turns, "text": reply})

            if reply.strip() == "STOP":
                stopped_by = "explicit_stop"
                self.log.append(self.clock.now(), "stop", {"reason": "explicit_stop"})
                break
            if reply.startswith("CALL:"):
                try:
                    body = reply[5:].strip()
                    name, argstr = body.split(" ", 1)
                    args = json.loads(argstr)
                except (ValueError, IndexError):
                    self._consecutive_tool_errors += 1
                    self.ctx.add(f"tool-error: malformed call {reply!r}")
                    self.log.append(self.clock.now(), "tool_error",
                                    {"malformed": True, "turn": turns})
                    continue
                try:
                    result = self.router.call(name, args, self.cfg.get("approver"))
                    self._consecutive_tool_errors = 0
                    self.ctx.add(f"tool-result: {result}")
                    self.log.append(self.clock.now(), "tool", {"name": name,
                                                               "turn": turns,
                                                               "ok": True})
                except (ToolError, PermissionDenied) as e:
                    self._consecutive_tool_errors += 1
                    self.ctx.add(f"tool-error: {e}")
                    self.log.append(self.clock.now(), "tool", {"name": name,
                                                               "turn": turns,
                                                               "ok": False,
                                                               "error": str(e)})
            else:
                # plain assistant message ends the loop
                stopped_by = "done"
                self.log.append(self.clock.now(), "stop", {"reason": "done"})
                break
        return {"stopped_by": stopped_by, "turns": turns}
