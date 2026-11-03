import config
from agents.analyst import gate, rules_answers
S = lambda k: config.DEFAULTS["analyst." + k][0]
BASE = {"alive_6h": 0.70, "organic": 0.65, "flush": 1.0, "chase": 0.30}
def test_each_rejects():
    for k, v in (("alive_6h", 0.69), ("organic", 0.64), ("chase", 0.31)):
        score, ok, failed = gate({**BASE, k: v}, S); assert not ok and failed[0].startswith(k), (k, failed)
def test_score_69_rejects():
    a = {"alive_6h": 0.70, "organic": 0.65, "flush": 0.66, "chase": 0.25}
    score, ok, failed = gate(a, S); assert score == 69 and not ok and failed == ["score 69"]
def test_threshold_passes():
    a = {"alive_6h": 0.70, "organic": 0.65, "flush": 0.75, "chase": 0.30}
    score, ok, failed = gate(a, S); assert score == 70 and ok, (score, failed)
def test_rules_mode_fake_dex():
    f = {"v1": 17250, "b1": 97.5, "p5": -6, "b5": 10, "s5": 5, "p1": 24}
    a = rules_answers(f, 0, S); assert a == {"alive_6h": 0.69, "organic": 0.65, "flush": 1.0, "chase": 0.3}
    assert not gate(a, S)[1]
    f2 = {**f, "v1": 17500}; a2 = rules_answers(f2, 0, S); assert gate(a2, S)[1]
    assert rules_answers({**f2, "p5": None}, 0, S)["flush"] == 0.0          # m5 missing
    assert rules_answers(f2, 3, S)["organic"] == 0.325                      # bundled penalty from 3
def test_rules_activity_label():
    import asyncio, bus, store, telegram
    from agents import analyst
    bus.init()
    async def go():
        await bus.analyst.put({"scan": {"mint": "M1", "name": "Low"}, "audit": {}, "ctx": {"bund": 0}})
        orig = analyst.analyse
        async def fake(item, S=None, pair=None): return await orig(item, pair={"v1": 100, "b1": 1, "p1": 0, "liquidityUsd": 50000})
        analyst.analyse = fake
        t = asyncio.create_task(analyst.run()); await asyncio.sleep(0.2); t.cancel(); analyst.analyse = orig
    asyncio.run(go())
    r = store.c().execute("SELECT agent_line FROM activity WHERE mint='M1'").fetchone()[0]
    assert r.startswith("Analyst (rules) · alive_6h"), r
