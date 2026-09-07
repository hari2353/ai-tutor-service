"""The capstone: a production-shaped agent service — loop + tools + cost guard + checkpoints."""
import json


def _tokens(text):
    return len(text) // 4 + 1


class FakeClock:
    def __init__(self, t=0):
        self._t = t

    def now(self):
        return self._t

    def advance(self, dt):
        self._t += dt


class FakeLLM:
    def __init__(self, replies, resume_at=0):
        self.replies = list(replies)
        self.i = resume_at

    def __call__(self, messages):
        r = self.replies[min(self.i, len(self.replies) - 1)]
        self.i += 1
        return r


class ProductionAgent:
    def __init__(self, llm, tools, config, clock=None):
        self.llm = llm
        self.tools = tools
        self.config = dict(config)
        self.clock = clock or FakeClock()
        self.messages = []
        self.turns = 0
        self.cost = 0.0
        self.consecutive_errors = 0
        self.events = []

    def _log(self, kind, **payload):
        self.events.append(dict(kind=kind, t=self.clock.now(), **payload))

    def run(self, task):
        self.messages.append(f"user: {task}")
        stopped_by = None
        answer = None
        while True:
            # ---- between-turns checks ----
            if self.turns >= self.config.get("max_turns", 10):
                stopped_by = "max_turns"
                break
            if self.cost + self.config.get("cost_per_call", 0.0) > \
                    self.config.get("cost_cap_usd", 10 ** 9):
                stopped_by = "cost"
                break
            if self.consecutive_errors >= 3:
                stopped_by = "tool_errors"
                break
            if sum(_tokens(m) for m in self.messages) > \
                    self.config.get("token_budget", 10 ** 9):
                stopped_by = "token_budget"
                break

            # ---- a turn ----
            self.turns += 1
            self.cost += self.config.get("cost_per_call", 0.0)
            self._log("llm_call", turn=self.turns, cost_after=round(self.cost, 4))
            reply = self.llm(self.messages)
            self.messages.append(f"assistant: {reply}")

            if reply.startswith("DONE:"):
                answer = reply[5:].strip()
                self._log("done", turn=self.turns, answer=answer)
                stopped_by = "done"
                break
            if reply.startswith("CALL:"):
                try:
                    body = reply[5:].strip()
                    name, argstr = body.split(" ", 1)
                    args = json.loads(argstr)
                except (ValueError, IndexError):
                    self.consecutive_errors += 1
                    self.messages.append("observation: error: malformed call")
                    self._log("tool_error", turn=self.turns, error="malformed call")
                    continue
                self._log("tool_call", turn=self.turns, tool=name, args=args)
                if name not in self.tools:
                    self.consecutive_errors += 1
                    self.messages.append(f"observation: error: unknown tool {name}")
                    self._log("tool_error", turn=self.turns, tool=name,
                              error="unknown tool")
                    continue
                try:
                    result = self.tools[name](**args)
                    self.consecutive_errors = 0
                    self.messages.append(f"observation: {result}")
                    self._log("observation", turn=self.turns, tool=name,
                              result=str(result))
                except Exception as e:
                    self.consecutive_errors += 1
                    self.messages.append(f"observation: error: {e}")
                    self._log("tool_error", turn=self.turns, tool=name, error=str(e))
            else:
                # plain reply treated as the answer
                answer = reply
                stopped_by = "done"
                break

        return dict(answer=answer, turns=self.turns, cost_usd=round(self.cost, 4),
                    events=list(self.events), stopped_by=stopped_by)

    def checkpoint(self):
        return dict(
            messages=list(self.messages),
            llm_index=self.llm.i,
            turns=self.turns,
            cost=self.cost,
            consecutive_errors=self.consecutive_errors,
        )


def resume(agent, cp):
    agent.messages = list(cp["messages"])
    agent.llm.i = cp["llm_index"]
    agent.turns = cp["turns"]
    agent.cost = cp["cost"]
    agent.consecutive_errors = cp["consecutive_errors"]
    return agent


def validate(events):
    violations = []
    pending_calls = []
    last_cost = 0.0
    for ev in events:
        kind = ev.get("kind")
        if kind == "tool_call":
            pending_calls.append((ev.get("turn"), ev.get("tool")))
        elif kind in ("observation", "tool_error"):
            if pending_calls:
                pending_calls.pop(0)
        elif kind == "llm_call":
            c = ev.get("cost_after", 0.0)
            if c < last_cost - 1e-9:
                violations.append(f"cost decreased at t={ev.get('t')}")
            last_cost = c
    for turn, tool in pending_calls:
        violations.append(f"tool_call {tool} at turn {turn} has no observation")
    return violations
