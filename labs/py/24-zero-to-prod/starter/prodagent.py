"""The capstone: a production-shaped agent service — loop + tools + cost guard + checkpoints."""


class FakeClock:
    def __init__(self, t=0):
        self._t = t

    def now(self):
        return self._t

    def advance(self, dt):
        self._t += dt


class FakeLLM:
    def __init__(self, replies, resume_at=0):
        """replies: list of strings. .i tracks the current index."""

    def __call__(self, messages):
        """Return the next scripted reply; last one repeats when exhausted."""


class ProductionAgent:
    def __init__(self, llm, tools, config, clock=None):
        """tools: dict name -> callable(**args). config: max_turns, token_budget,
        cost_cap_usd, cost_per_call. llm: callable(messages)->reply string."""

    def run(self, task):
        """Loop until stop condition. Returns
        {answer, turns, cost_usd, events, stopped_by}."""

    def checkpoint(self):
        """Plain-data snapshot: messages, llm_index, turns, cost, consecutive_errors."""


def resume(agent, cp):
    """Return the same agent object with state restored from the checkpoint."""


def validate(events):
    """Return a list of invariant-violation strings (empty = healthy).
    Invariants: every tool_call has a matching observation or tool_error;
    cost entries are monotonic non-decreasing."""
