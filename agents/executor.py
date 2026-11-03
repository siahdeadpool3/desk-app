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
    price = f.get("priceUsd"); base = item.get("pair") or {}; scan = item["scan"]
    def done(status, reason, sz=0, cap=None):
        j = {"agent": "executor", "mint": mint, "signalPrice": price, "sizeUsd": sz, "stackPct": round(100 * sz / stack, 2) if stack else 0,
             "link": link, "mode": mode, "status": status, "reason": reason}
        log.info(f"{mint} stack={stack} cap={cap} size={sz} mode={mode} status={status} reason={reason} link={link}")
        bus.emit("executor", j)
        if status in ("skipped", "missed"): store.skip(mint, "executor", reason)
        return j
    stack = stack_now(c)
    if not price: return done("skipped", "no price")
    r = recheck(scan.get("liquidityUsd"), f.get("liquidityUsd"), base.get("priceUsd"), price, S)
    if r: return done("skipped", r)
    sz, cap, status, reason = size(stack, open_usd(c), f.get("liquidityUsd"), S)
    if status == "skipped": return done("skipped", reason, 0, cap)
    pct = round(100 * sz / stack, 1)
    pid = c.execute("INSERT INTO positions(mint,name,mode,entry_price,size_usd,peak,stop_pct,opened_at,status,link) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (mint, name, mode, price, sz, price, config.get("risk.stop_pct", c), bus.iso(), "pending", link)).lastrowid
    text, btn = push_text(name, sz, pct, item["analysis"]["score"], c), buttons(link, pid)
    ok = await telegram.push(text, btn, mode=mode)
    trades += 1
    if mode == "PAPER":
        await asyncio.sleep(1.2)
        if c.execute("SELECT status FROM positions WHERE id=?", (pid,)).fetchone()[0] == "skipped": return done("skipped", "you tapped Skip", sz, cap)
        fill(c, pid, name, sz, pct, mint)
        if not ok: log.info(f"{mint} push failed")
        return done("bought", None if ok else "push failed", sz, cap)
    if not ok:
        log.info(f"{mint} push failed"); c.execute("DELETE FROM positions WHERE id=?", (pid,)); return done("skipped", "push failed", sz, cap)
    for _ in range(int(S("confirm_window_min") * 60)):
        await asyncio.sleep(1)
        st = c.execute("SELECT status FROM positions WHERE id=?", (pid,)).fetchone()
        if not st or st[0] != "pending": break
    st = c.execute("SELECT status FROM positions WHERE id=?", (pid,)).fetchone()
    if st and st[0] == "pending":
        c.execute("DELETE FROM positions WHERE id=?", (pid,)); return done("missed", "missed", sz, cap)
    if st and st[0] == "skipped": c.execute("DELETE FROM positions WHERE id=?", (pid,)); return done("skipped", "you tapped Skip", sz, cap)
    return done("bought", None, sz, cap)
def recheck(scan_liq, liq, analyst_price, price, S):
    if scan_liq and (liq or 0) < scan_liq * (1 - S("recheck_liq_drop_pct") / 100): return "liquidity dropping"
    if analyst_price and price > analyst_price * (1 + S("recheck_price_up_pct") / 100): return "ran before the push"
    return None
def push_text(name, sz, pct, score, c=None):
    return (f"Buy {name} · ${sz:.2f} · {pct:g}% of stack\n"
            f"Auditor 8/8 · Analyst {score} · stop -{config.get('risk.stop_pct', c):g}% · trail {config.get('risk.trail_pct', c):g}%")
def buttons(link, pid): return [[("Buy on FOMO", link)], [("Bought", f"bought:{pid}"), ("Skip", f"skip:{pid}")]]
def fill(c, pid, name, sz, pct, mint):
    c.execute("UPDATE positions SET status='open', opened_at=? WHERE id=?", (bus.iso(), pid))
    store.activity("buy", f"Bought {name}", f"Executor · {bus.now().strftime('%H:%M')}", f"${sz:.2f} · {pct:g}% of stack", mint)
def skip_tap(pid):
    c = store.c(); r = c.execute("SELECT * FROM positions WHERE id=? AND status='pending'", (pid,)).fetchone()
    if not r: return None
    c.execute("UPDATE positions SET status='skipped' WHERE id=?", (pid,)); store.skip(r["mint"], "executor", "you tapped Skip"); return r
def confirm_bought(pid):
    c = store.c(); r = c.execute("SELECT * FROM positions WHERE id=? AND status='pending'", (pid,)).fetchone()
    if not r: return None
    fill(c, pid, r["name"], r["size_usd"], round(100 * r["size_usd"] / stack_now(c), 1), r["mint"]); return r
async def run():
    while True:
        item = await bus.executor.get(); store.beat("executor")
        asyncio.create_task(handle(item))
