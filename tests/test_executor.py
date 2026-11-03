import config, store
from agents.executor import size, ticket_check
def S(over=None):
    return lambda k: (over or {}).get(k, config.DEFAULTS["executor." + k][0])
def test_200_bump():
    assert size(200, 0, 1e9, S()) == (47.5, "bump", "sent", None)   # 8% of 200 = $16 < 47.50 -> bump
def test_200_skip():
    s = size(200, 0, 1e9, S({"below_min": "skip"})); assert s[2] == "skipped"
def test_pool_cap():
    assert size(100000, 0, 40000, S())[0] == 800
def test_paper_skip_warning():
    c = store.c(); config.set_("executor.below_min", "skip")
    assert "every coin will be skipped" in ticket_check(c)
    config.set_("executor.below_min", "bump"); assert ticket_check(c).startswith("tickets bumped to $47.50 = 23.8% of stack")
import asyncio, links, telegram
from agents import executor
def test_recheck():
    s = S()
    assert executor.recheck(50000, 39999, 1.0, 1.0, s) == "liquidity dropping"
    assert executor.recheck(50000, 40000, 1.0, 1.15, s) is None
    assert executor.recheck(50000, 45000, 1.0, 1.151, s) == "ran before the push"
def test_push_text():
    t = executor.push_text("Frog", 47.5, 23.8, 74)
    assert t == "Buy Frog · $47.50 · 23.8% of stack\nAuditor 8/8 · Analyst 74 · stop -6% · trail 12%"
    b = executor.buttons(links.coin_url("M", "solana"), 5)
    assert b == [[("Buy on FOMO", links.coin_url("M", "solana"))], [("Bought", "bought:5"), ("Skip", "skip:5")]]
def _run(mode, pair, push_ok=True):
    import net
    od, op = net.dex_pairs, telegram.push
    config.set_("desk.mode", mode)
    async def dex(m): return {m[0]: pair} if pair else {}
    net.dex_pairs = dex
    async def p(*a, **k): telegram.sent.append({"text": a[0]}); return push_ok
    telegram.push = p; executor.pushed.clear()
    item = {"scan": {"mint": "EX" + mode + str(push_ok) + str(bool(pair)), "name": "Ex", "liquidityUsd": 60000}, "analysis": {"score": 80}, "pair": {"priceUsd": 1.0}}
    try: asyncio.run(executor.handle(item))
    finally: net.dex_pairs, telegram.push = od, op
    return item["scan"]["mint"]
PAIR = {"pairAddress": "P", "priceUsd": "1.0", "liquidity": {"usd": 60000}, "baseToken": {}}
def test_no_price_skip():
    m = _run("PAPER", None); assert store.c().execute("SELECT reason FROM skips WHERE mint=?", (m,)).fetchone()[0] == "no price"
def test_paper_push_failed_fills():
    m = _run("PAPER", PAIR, push_ok=False); assert store.c().execute("SELECT status FROM positions WHERE mint=?", (m,)).fetchone()[0] == "open"
def test_live_push_failed_no_position():
    m = _run("LIVE", PAIR, push_ok=False); assert store.c().execute("SELECT 1 FROM positions WHERE mint=?", (m,)).fetchone() is None
    config.set_("desk.mode", "PAPER")
def test_skip_tap():
    c = store.c(); pid = c.execute("INSERT INTO positions(mint,name,mode,status,size_usd) VALUES('SK','Sk','LIVE','pending',47.5)").lastrowid
    assert executor.skip_tap(pid) and c.execute("SELECT reason FROM skips WHERE mint='SK'").fetchone()[0] == "you tapped Skip"
