"""Loop engineering: budgets, compaction strategies + triggers, stop conditions, snapshot/resume, metrics."""
import copy


def _default_tokenizer(s):
    return max(1, len(s) // 4)


def _tokens(tokenizer, messages):
    tok = tokenizer or _default_tokenizer
    return sum(tok(m.get("text", "")) for m in messages)


class LoopBudget:
    def __init__(self, turns=None, tokens_in=None, tokens_out=None, wallclock=None):
        self.caps = dict(turns=turns, tokens_in=tokens_in,
                         tokens_out=tokens_out, wallclock=wallclock)
        self.left = dict(turns=turns, tokens_in=tokens_in,
                         tokens_out=tokens_out, wallclock=wallclock)

    def consume_turn(self, n=1):
        if self.left["turns"] is not None:
            self.left["turns"] -= n

    def consume_tokens_in(self, n):
        if self.left["tokens_in"] is not None:
            self.left["tokens_in"] -= n

    def consume_tokens_out(self, n):
        if self.left["tokens_out"] is not None:
            self.left["tokens_out"] -= n

    def consume_wallclock(self, dt):
        if self.left["wallclock"] is not None:
            self.left["wallclock"] -= dt

    def exhausted(self):
        for k in ("turns", "tokens_in", "tokens_out", "wallclock"):
            if self.caps[k] is not None and self.left[k] <= 0:
                return k
        return None


def truncate_oldest(tokenizer, messages, target_tokens, keep_head=1):
    msgs = [dict(m) for m in messages]
    while _tokens(tokenizer, msgs) > target_tokens and len(msgs) > keep_head:
        # oldest non-pinned, skipping the protected head
        idx = next((i for i in range(keep_head, len(msgs))
                    if not msgs[i].get("pinned")), None)
        if idx is None:
            break
        msgs.pop(idx)
    return msgs


def sliding_window(tokenizer, messages, target_tokens, n_head=1, n_tail=3):
    msgs = [dict(m) for m in messages]
    while _tokens(tokenizer, msgs) > target_tokens:
        if len(msgs) <= n_head + n_tail:
            break
        # drop a middle non-pinned message, else a middle one
        idx = next((i for i in range(n_head, len(msgs) - n_tail)
                    if not msgs[i].get("pinned")), None)
        if idx is None:
            idx = n_head
            if len(msgs) - n_tail <= n_head:
                break
        msgs.pop(idx)
    return msgs


def summarize(tokenizer, messages, target_tokens, summarizer):
    msgs = [dict(m) for m in messages]
    dropped = []
    while _tokens(tokenizer, msgs) > target_tokens:
        idx = next((i for i, m in enumerate(msgs) if not m.get("pinned")), None)
        if idx is None or len(msgs) <= 1:
            break
        dropped.append(msgs.pop(idx))
    if dropped:
        summary = summarizer([m["text"] for m in dropped])
        # replace any previous summary instead of stacking
        msgs = [m for i, m in enumerate(msgs)
                if i == 0 or not m["text"].startswith("[SUMMARY")]
        # insert after pinned prefix
        at = 0
        for i, m in enumerate(msgs):
            if m.get("pinned"):
                at = i + 1
        msgs.insert(at, {"text": summary, "pinned": False})
    return msgs


class CompactionEngine:
    def __init__(self, strategy_fn, tokenizer=None, threshold=0.8):
        self.strategy_fn = strategy_fn
        self.tokenizer = tokenizer or _default_tokenizer
        self.threshold = threshold

    def maybe_compact(self, messages, cap):
        if _tokens(self.tokenizer, messages) > self.threshold * cap:
            target = int(self.threshold * cap)
            return self.strategy_fn(self.tokenizer, messages, target), True
        return messages, False


class StopConditions:
    def __init__(self, goal_detector=None, stuck_tool_repeat=3, budget=None):
        self.goal_detector = goal_detector
        self.stuck_k = stuck_tool_repeat
        self.budget = budget

    def evaluate(self, state):
        if self.goal_detector and self.goal_detector(state.get("messages", [])):
            return "goal_met"
        if self.budget is not None and self.budget.exhausted():
            return "budget_exhausted"
        hist = state.get("tool_history", [])
        if self.stuck_k and len(hist) >= self.stuck_k:
            def key(h):
                if isinstance(h, dict):
                    return tuple(sorted((k, key(v)) for k, v in h.items()))
                if isinstance(h, (list, tuple)):
                    return tuple(key(x) for x in h)
                return h
            last = hist[-self.stuck_k:]
            if len({key(h) for h in last}) == 1:
                return "stuck_loop"
        return None


def snapshot(state):
    return copy.deepcopy(dict(state))


def restore(blob):
    return copy.deepcopy(dict(blob))


class MetricsRecorder:
    def __init__(self):
        self.turns = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.tool_histogram = {}

    def record_turn(self, tokens_in=0, tokens_out=0, tool=None):
        self.turns += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        if tool is not None:
            self.tool_histogram[tool] = self.tool_histogram.get(tool, 0) + 1

    def report(self):
        return {
            "turns": self.turns,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "tool_histogram": dict(self.tool_histogram),
        }
