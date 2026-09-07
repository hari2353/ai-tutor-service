"""Lab 10 tests: working / episodic / semantic / procedural memory.
Deterministic — all time flows through FakeClock."""
import pytest

from memory import FakeClock


# ------------------------------------------------------------------ clock
def test_fake_clock_now_advance_sleep(M):
    c = FakeClock(t=100.0)
    assert c.now() == 100.0
    c.advance(5.0)
    assert c.now() == 105.0
    c.sleep(3.0)
    assert c.now() == 108.0
    assert c.slept == [3.0]


def test_token_estimate(M):
    assert M._estimate_tokens("") == 1        # min 1
    assert M._estimate_tokens("abcd") == 1    # 4 chars → 1
    assert M._estimate_tokens("abcde") == 2   # 5 chars → 2
    assert M._estimate_tokens("a" * 400) == 100


# ------------------------------------------------------------------ working memory
def test_working_memory_holds_within_budget(M):
    wm = M.WorkingMemory(max_tokens=100)
    wm.add("user", "hello " * 10)             # ~15 tokens
    wm.add("assistant", "hi " * 10)
    assert len(wm.messages()) == 2
    assert wm.tokens_used() <= 100


def test_working_memory_evicts_oldest_first(M):
    wm = M.WorkingMemory(max_tokens=20)
    wm.add("user", "x" * 40)                  # 10 tokens each
    wm.add("user", "y" * 40)
    wm.add("user", "z" * 40)                  # 30 > 20 → oldest evicted
    msgs = wm.messages()
    assert [r for r, _ in msgs] == ["user", "user"]
    assert "y" in msgs[0][1] and "z" in msgs[1][1]
    assert wm.evictions[0].content == "x" * 40
    assert wm.evictions[0].tokens == 10


def test_working_memory_pinned_never_evicts(M):
    wm = M.WorkingMemory(max_tokens=10)
    wm.add("system", "You are a cat.", pinned=True)   # 4 tokens
    wm.add("user", "x" * 40)
    wm.add("user", "y" * 40)                          # would evict the system msg
    roles = [r for r, _ in wm.messages()]
    assert "system" in roles
    assert all(e.role != "system" for e in wm.evictions)


def test_working_memory_all_pinned_can_exceed_budget(M):
    """When only pinned messages remain, keep them all — never an empty window."""
    wm = M.WorkingMemory(max_tokens=5)
    wm.add("system", "a very long pinned system prompt that exceeds the budget",
           pinned=True)
    assert len(wm.messages()) == 1
    assert wm.evictions == []


def test_working_memory_tokens_used_counts_everything(M):
    wm = M.WorkingMemory(max_tokens=10_000)
    wm.add("user", "x" * 16)                   # 4 tokens
    wm.add("assistant", "y" * 20)              # 5 tokens
    assert wm.tokens_used() == 9


def test_working_memory_messages_strip_pinned_flag(M):
    wm = M.WorkingMemory(max_tokens=100)
    wm.add("system", "sys", pinned=True)
    wm.add("user", "hi")
    assert wm.messages()[0] == ("system", "sys")


def test_working_memory_fifo_order(M):
    wm = M.WorkingMemory(max_tokens=1000)
    for i in range(5):
        wm.add("user", f"m{i}")
    assert [c for _, c in wm.messages()] == ["m0", "m1", "m2", "m3", "m4"]


# ------------------------------------------------------------------ episodic
def test_episodic_record_stamps_injected_clock(M):
    c = FakeClock(t=50.0)
    em = M.EpisodicMemory(clock=c)
    em.record("deployed the service at noon")
    c.advance(10.0)
    em.record("deployed the service at midnight")
    eps = em.retrieve("deployed service", k=10)
    assert len(eps) == 2
    assert eps[0].timestamp == 50.0
    assert eps[1].timestamp == 60.0


def test_episodic_retrieve_top_k_by_overlap(M):
    em = M.EpisodicMemory(clock=FakeClock())
    em.record("the chef cooked pasta with tomato sauce")
    em.record("the gardener planted tomatoes in spring")
    em.record("the chef burned the pasta again")
    hits = em.retrieve("chef pasta", k=2)
    assert len(hits) == 2
    assert "pasta" in hits[0].content
    assert "chef" in hits[0].content
    assert hits[0].score >= hits[1].score


def test_episodic_zero_overlap_not_returned(M):
    em = M.EpisodicMemory(clock=FakeClock())
    em.record("alpha beta gamma")
    em.record("chef pasta sauce")
    hits = em.retrieve("quantum physics", k=5)
    assert hits == []


def test_episodic_ties_broken_by_earlier_timestamp(M):
    em = M.EpisodicMemory(clock=FakeClock())
    em.record("deploy failed on friday")
    em.record("deploy failed on friday")       # identical, later
    hits = em.retrieve("deploy failed", k=2)
    assert hits[0].timestamp <= hits[1].timestamp


def test_episodic_len(M):
    em = M.EpisodicMemory(clock=FakeClock())
    assert len(em) == 0
    em.record("a")
    em.record("b")
    assert len(em) == 2


def test_overlap_similarity_values(M):
    assert M.overlap_similarity("cat dog", "cat dog") == 1.0
    assert M.overlap_similarity("cat", "dog") == 0.0
    assert M.overlap_similarity("cat dog", "dog bird") == pytest.approx(1 / 3)
    assert M.overlap_similarity("", "") == 0.0


def test_tokenize(M):
    assert M._tokenize("Hello, World! it's") == ["hello", "world", "it's"]


# ------------------------------------------------------------------ semantic
def test_semantic_insert_lookup(M):
    c = FakeClock(t=100.0)
    sm = M.SemanticMemory(clock=c)
    sm.insert("user_location", "Oslo", source="profile")
    f = sm.lookup("user_location")
    assert f.value == "Oslo"
    assert f.source == "profile"
    assert f.confidence == 1.0
    assert f.recorded_at == 100.0


def test_semantic_unknown_key(M):
    sm = M.SemanticMemory(clock=FakeClock())
    assert sm.lookup("ghost") is None
    assert sm.history("ghost") == []


def test_semantic_contradiction_keeps_both_with_dates(M):
    c = FakeClock(t=0.0)
    sm = M.SemanticMemory(clock=c)
    sm.insert("fav_lang", "python", source="chat-1")
    c.advance(10.0)
    sm.insert("fav_lang", "rust", source="chat-2")
    assert sm.lookup("fav_lang").value == "rust"     # latest wins for lookup
    hist = sm.history("fav_lang")
    assert [f.value for f in hist] == ["python", "rust"]
    assert [f.recorded_at for f in hist] == [0.0, 10.0]


def test_semantic_contradictions_lists_conflicts(M):
    sm = M.SemanticMemory(clock=FakeClock())
    sm.insert("a", "x", source="s1")
    sm.insert("a", "x", source="s2")            # same value — no contradiction
    sm.insert("b", "y", source="s1")
    sm.insert("b", "z", source="s2")
    cons = sm.contradictions()
    assert [k for k, _ in cons] == ["b"]
    assert [f.value for f in cons[0][1]] == ["y", "z"]


def test_semantic_keys_sorted(M):
    sm = M.SemanticMemory(clock=FakeClock())
    sm.insert("zeta", "1", source="s")
    sm.insert("alpha", "2", source="s")
    assert sm.keys() == ["alpha", "zeta"]


def test_semantic_confidence_per_fact(M):
    sm = M.SemanticMemory(clock=FakeClock())
    sm.insert("k", "v1", source="llm", confidence=0.6)
    sm.insert("k", "v2", source="human", confidence=0.99)
    hist = sm.history("k")
    assert hist[0].confidence == 0.6
    assert hist[1].confidence == 0.99


# ------------------------------------------------------------------ procedural
def test_procedural_register_and_match(M):
    c = FakeClock(t=7.0)
    pm = M.ProceduralMemory(clock=c)
    pm.register("sql-for-csv", r"\bcsv\b.*\bsql\b|\bsql\b.*\bcsv\b",
                "Pandas read_csv, then to_sql.")
    hit = pm.match("how do I load this CSV into SQL?")
    assert hit is not None and hit.name == "sql-for-csv"
    assert hit.instructions == "Pandas read_csv, then to_sql."
    assert pm.match("tell me a joke") is None


def test_procedural_match_is_case_insensitive(M):
    pm = M.ProceduralMemory(clock=FakeClock())
    pm.register("greet", r"hello", "Say hi warmly.")
    assert pm.match("HELLO there").name == "greet"


def test_procedural_match_returns_first_registered(M):
    pm = M.ProceduralMemory(clock=FakeClock())
    pm.register("first", r"error", "A")
    pm.register("second", r"error", "B")
    assert pm.match("fix this error").name == "first"


def test_procedural_match_all_returns_every_match(M):
    pm = M.ProceduralMemory(clock=FakeClock())
    pm.register("a", r"deploy", "A")
    pm.register("b", r"deploy", "B")
    pm.register("c", r"docker", "C")
    assert [s.name for s in pm.match_all("deploy now")] == ["a", "b"]


def test_procedural_success_stats(M):
    c = FakeClock(t=0.0)
    pm = M.ProceduralMemory(clock=c)
    pm.register("triage", r"bug", "Reproduce, bisect, fix.")
    assert pm.get("triage").success_rate == 0.0
    pm.record_success("triage")
    c.advance(5.0)
    pm.record_success("triage")
    pm.record_failure("triage")
    s = pm.get("triage")
    assert s.uses == 3
    assert s.successes == 2
    assert s.failures == 1
    assert s.success_rate == pytest.approx(2 / 3)
    assert s.last_used_at == 5.0


def test_procedural_prune_low_performers(M):
    pm = M.ProceduralMemory(clock=FakeClock())
    pm.register("bad", r"never works", "hopeless")
    pm.register("good", r"always works", "solid")
    pm.register("young", r"untested", "new")
    for _ in range(5):
        pm.record_failure("bad")
        pm.record_success("good")
    pm.record_success("young")                 # 1 use — protected by min_uses
    pruned = pm.prune(min_success_rate=0.5, min_uses=3)
    assert pruned == ["bad"]
    assert [s.name for s in pm.all_skills()] == ["good", "young"]


def test_procedural_skill_created_at_from_clock(M):
    c = FakeClock(t=123.0)
    pm = M.ProceduralMemory(clock=c)
    pm.register("k", r"x", "y")
    assert pm.get("k").created_at == 123.0


# ------------------------------------------------------------------ composed
def test_agent_memory_wires_one_clock_everywhere(M):
    c = FakeClock(t=10.0)
    am = M.AgentMemory(working_max_tokens=100, clock=c)
    am.working.add("user", "hi")
    am.episodic.record("talked about memory")
    am.semantic.insert("topic", "memory", source="chat")
    am.procedural.register("mem", r"memory", "recall it")
    assert am.episodic.retrieve("memory", k=1)[0].timestamp == 10.0
    assert am.semantic.lookup("topic").recorded_at == 10.0
    assert am.procedural.match("my memory").name == "mem"
    assert am.working.messages() == [("user", "hi")]
