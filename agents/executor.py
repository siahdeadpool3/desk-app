"""AGENT 4 · EXECUTOR. Arithmetic + 1 button. Never places an order, never touches funds."""
import asyncio, json
import bus, net, config, store, telegram, links
from agents.common import logger
log = logger("executor")
pushed = set(); trades = 0
def stack_now(c=None):
    if config.get("desk.mode", c) == "PAPER": return store.kv_get("paper_balance", config.get("desk.paper_start_stack", c))
    return config.get("desk.stack", c)
def size(stack, open_usd, pool_liq, S):
    """returns (size, cap_hit, status, reason)."""
    free = stack - open_usd
    raw = stack * S("stack_pct") / 100; s = raw; cap = "stack_pct"
    pool_cap = (pool_liq or 0) * S("max_pool_pct") / 100
    if s > pool_cap: s, cap = pool_cap, "pool"
    if s < S("min_ticket_usd"):
        if S("below_min") == "bump": s, cap = S("min_ticket_usd"), "bump"
        else: return 0, "min", "skipped", f"under ${S('min_ticket_usd'):.2f}"
    if s > free: return 0, "free", "skipped", "no free balance"
    return round(s, 2), cap, "sent", None
def ticket_check(c=None):
    """STEP 10 ticket check. returns message or None."""
    S = lambda k: config.get("executor." + k, c); st = stack_now(c); ms = config.min_stack(c)
    if st >= ms: return None
    if S("below_min") == "bump": return f"tickets bumped to ${S('min_ticket_usd'):.2f} = {100*S('min_ticket_usd')/st:.1f}% of stack"
    return f"every coin will be skipped, stack under ${ms:,.2f}. Switch below_min to bump or raise the stack."
def open_usd(c):
    r = c.execute("SELECT COALESCE(SUM(size_usd),0) FROM positions WHERE status IN ('open','exiting','pending')").fetchone(); return r[0]
async def handle(item):
    global trades
    c = store.c(); S = lambda k: config.get("executor." + k, c); mint = item["scan"]["mint"]; name = item["scan"].get("name") or mint
    mode = config.get("desk.mode", c); link = links.coin_url(mint, "solana")
    if mint in pushed or c.execute("SELECT 1 FROM positions WHERE mint=? AND status!='closed'", (mint,)).fetchone(): return
    pushed.add(mint)
    p = (await net.dex_pairs([mint])).get(mint); f = net.pair_fields(p) if p else {}
    price = f.get("priceUsd"); base = item.get("pair") or {}
    def done(status, reason, sz=0, cap=None):
        j = {"agent": "executor", "mint": mint, "signalPrice": price, "sizeUsd": sz, "stackPct": round(100 * sz / stack, 2) if stack else 0,
             "link": link, "mode": mode, "status": status, "reason": reason}
        log.info(f"{mint} stack={stack} cap={cap} size={sz} mode={mode} status={status} reason={reason} link={link}")
        bus.emit("executor", j)
        if status in ("skipped", "missed"): store.skip(mint, "executor", reason)
        return j
    stack = stack_now(c)
    if not price: return done("skipped", "no price")
    if base.get("liquidityUsd") and (f.get("liquidityUsd") or 0) < base["liquidityUsd"] * (1 - S("recheck_liq_drop_pct") / 100): return done("skipped", "liquidity dropped")
    if base.get("priceUsd") and price > base["priceUsd"] * (1 + S("recheck_price_up_pct") / 100): return done("skipped", "price ran")
    sz, cap, status, reason = size(stack, open_usd(c), f.get("liquidityUsd"), S)
    if status == "skipped": return done("skipped", reason, 0, cap)
    pct = round(100 * sz / stack, 1)
    text = f"Buy {name} · ${sz:.2f} · {pct}% of stack · score {item['analysis']['score']}"
    pid = c.execute("INSERT INTO positions(mint,name,mode,entry_price,size_usd,peak,stop_pct,opened_at,status,link) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (mint, name, mode, price, sz, price, config.get("risk.stop_pct", c), bus.iso(), "pending", link)).lastrowid
    ok = await telegram.push(text, [[("Buy on FOMO", link)], [("Bought", f"bought:{pid}")]], mode=mode)
    trades += 1
    if mode == "PAPER":
        await asyncio.sleep(1.2)
        c.execute("UPDATE positions SET status='open', opened_at=? WHERE id=?", (bus.iso(), pid))
        store.kv_set("paper_balance", stack)  # balance changes only on exit
        store.activity("buy", f"Bought {name}", f"Executor · {bus.now().strftime('%H:%M')}Z", f"${sz:.2f} · {pct}% of stack", mint)
        return done("bought", None if ok else "push failed", sz, cap)
    if not ok:
        c.execute("DELETE FROM positions WHERE id=?", (pid,)); return done("skipped", "push failed", sz, cap)
    await asyncio.sleep(S("confirm_window_min") * 60)
    if c.execute("SELECT status FROM positions WHERE id=?", (pid,)).fetchone()[0] == "pending":
        c.execute("DELETE FROM positions WHERE id=?", (pid,)); return done("missed", "no tap", sz, cap)
    return done("bought", None, sz, cap)
def confirm_bought(pid):
    c = store.c(); r = c.execute("SELECT * FROM positions WHERE id=? AND status='pending'", (pid,)).fetchone()
    if not r: return None
    c.execute("UPDATE positions SET status='open', opened_at=? WHERE id=?", (bus.iso(), pid))
    store.activity("buy", f"Bought {r['name']}", f"Executor · {bus.now().strftime('%H:%M')}Z", f"${r['size_usd']:.2f}", r["mint"]); return r
async def run():
    while True:
        item = await bus.executor.get(); store.beat("executor")
        asyncio.create_task(handle(item))
