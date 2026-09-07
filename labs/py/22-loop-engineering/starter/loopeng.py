"""Loop engineering: budgets, compaction strategies + triggers, stop conditions, snapshot/resume, metrics."""


class LoopBudget:
    def __init__(self, turns=None, tokens_in=None, tokens_out=None, wallclock=None):
        """None = unlimited. Consume methods decrement; exhausted() names the first tripped."""

    def consume_turn(self, n=1):
        raise NotImplementedError

    def consume_tokens_in(self, n):
        raise NotImplementedError

    def consume_tokens_out(self, n):
        raise NotImplementedError

    def consume_wallclock(self, dt):
        raise NotImplementedError

    def exhausted(self):
        """Return 'turns' | 'tokens_in' | 'tokens_out' | 'wallclock' | None."""


def truncate_oldest(tokenizer, messages, target_tokens, keep_head=1):
    """Drop oldest non-pinned until <= target. Never drop pinned or the first
    `keep_head` messages. messages: list of dicts {text, pinned}."""


def sliding_window(tokenizer, messages, target_tokens, n_head=1, n_tail=3):
    """Keep first n_head and last n_tail (pinned always kept), drop the middle
    until <= target_tokens."""


def summarize(tokenizer, messages, target_tokens, summarizer):
    """Drop oldest non-pinned below target; insert one summary message (from
    the summarizer hook) at the first droppable position."""


class CompactionEngine:
    def __init__(self, strategy_fn, tokenizer=None, threshold=0.8):
        """strategy_fn(tokenizer, messages, target) -> new messages.
        threshold: compact when tokens > threshold * cap."""

    def maybe_compact(self, messages, cap):
        """If tokens > threshold*cap, run the strategy to threshold*cap and
        return (new_messages, compacted: bool). Else (messages, False)."""


class StopConditions:
    def __init__(self, goal_detector=None, stuck_tool_repeat=3, budget=None):
        """goal_detector: fn(messages) -> bool.
        stuck_tool_repeat: k consecutive identical tool calls trips 'stuck_loop'."""

    def evaluate(self, state):
        """state: dict(messages, tool_history, budget_exhausted). Return the first
        tripped condition name or None. Order: goal_met > budget_exhausted > stuck_loop."""


def snapshot(state):
    """Deep-copyable dict of loop state: messages, counters, tool history."""


def restore(blob):
    """Rebuild the state dict from snapshot()."""


class MetricsRecorder:
    def __init__(self):
        raise NotImplementedError

    def record_turn(self, tokens_in=0, tokens_out=0, tool=None):
        raise NotImplementedError

    def report(self):
        """{turns, tokens_in, tokens_out, tool_histogram}"""
