"""AGENT 5 · RISK. Exit rules, no bending. Never places an order."""
import asyncio, datetime
import bus, net, config, store, telegram, fees, links
from agents.common import logger
log = logger("risk")
no_price = {}
def effective_stop(pos_stop, setting_stop):
    """Never moves a stop down: an open position takes a new stop only if it is tighter."""
    return min(pos_stop, setting_stop)
def evaluate(pos, price, now, S):
    """pos: dict entry_price, peak, stop_pct, trail_active, opened_at(dt). returns (pos, reason|None)."""
    e = pos["entry_price"]; pos["peak"] = max(pos["peak"], price)
    stop = effective_stop(pos["stop_pct"], S("stop_pct")); pos["stop_pct"] = stop
    if price <= e * (1 - stop / 100): return pos, "stop"
    if price >= e * (1 + S("trail_start_pct") / 100): pos["trail_active"] = True
    if pos["trail_active"] and price <= pos["peak"] * (1 - S("trail_pct") / 100): return pos, "trail"
    if (now - pos["opened_at"]).total_seconds() >= S("timeout_h") * 3600 and price < e * (1 + S("timeout_min_gain_pct") / 100): return pos, "timeout"
    return pos, None
def pnl(pos, exit_price, disc):
    out_usd = pos["size_usd"] * exit_price / pos["entry_price"]
    fee = fees.round_trip(pos["size_usd"], out_usd, disc)
    p = out_usd - pos["size_usd"] - fee
    return round(p, 2), round(100 * p / pos["size_usd"], 2), round(fee, 4)
def message(reason, name, p, pct, stop_pct, timeout_h):
    if reason == "trail": return f"Sold {name} · {'+' if p>=0 else '-'}${abs(p):.2f} ({pct:+.1f}%)"
    if reason == "stop": return f"{name} hit the -{stop_pct:g}% stop · -${abs(p):.2f}"
    if reason == "timeout": return f"Sell {name}, dead money · {pct:+.1f}% in {timeout_h:g}h"
    return f"Sell {name} now, liquidity pulled · {pct:+.1f}%"
async def exit_(pos, reason, price):
    c = store.c(); mode = pos["mode"]; link = links.coin_url(pos["mint"], "solana")
    p, pct, fee = pnl(pos, price, config.get("desk.fees_ref_discount", c))
    status = "closed" if mode == "PAPER" else "exiting"
    c.execute("UPDATE positions SET status=?,exit_price=?,exit_reason=?,pnl_usd=?,pct=?,fees_usd=?,closed_at=?,peak=?,stop_pct=? WHERE id=?",
              (status, price, reason, p, pct, fee, bus.iso() if status == "closed" else None, pos["peak"], pos["stop_pct"], pos["id"]))
    if mode == "PAPER":
        store.kv_set("paper_balance", round(store.kv_get("paper_balance", config.get("desk.paper_start_stack", c)) + p, 2))
    if reason == "trail": store.activity("sell", f"Sold {pos['name']}", "Risk · trailing stop", f"{'+' if p>=0 else '-'}${abs(p):.2f} / {pct:+.1f}%", pos["mint"], mode)
    elif reason == "stop": store.activity("stop", f"Stopped {pos['name']}", f"Risk · -{pos['stop_pct']:g}% stop", f"-${abs(p):.2f}", pos["mint"], mode)
    else: store.activity("sell", f"Sold {pos['name']}", f"Risk · {reason}", f"{'+' if p>=0 else '-'}${abs(p):.2f} / {pct:+.1f}%", pos["mint"], mode)
    text = message(reason, pos["name"], p, pct, pos["stop_pct"], config.get("risk.timeout_h", c))
    btn = [[("Sell on FOMO", link)]] + ([[("Sold", f"sold:{pos['id']}")]] if mode == "LIVE" else [])
    await telegram.push(text, btn, mode=mode)
    j = {"agent": "risk", "mint": pos["mint"], "name": pos["name"], "ts": bus.iso(), "reason": reason, "entryPrice": pos["entry_price"],
         "exitPrice": price, "peakPrice": pos["peak"], "pnlUsd": p, "pct": pct, "feesUsd": fee, "stopPct": pos["stop_pct"], "mode": mode, "status": status, "link": link}
    bus.emit("exit", j); log.info(f"EXIT {j}")
    if mode == "LIVE": asyncio.create_task(reminder(pos["id"], text, btn))
    return j
async def reminder(pid, text, btn):
    await asyncio.sleep(config.get("risk.confirm_window_min") * 60)
    r = store.c().execute("SELECT status FROM positions WHERE id=?", (pid,)).fetchone()
    if r and r[0] == "exiting": await telegram.push(text + " · still open", btn, mode="LIVE")
def confirm_sold(pid):
    c = store.c(); c.execute("UPDATE positions SET status='closed', closed_at=? WHERE id=? AND status='exiting'", (bus.iso(), pid))
async def poll_once():
    c = store.c(); S = lambda k: config.get("risk." + k, c)
    rows = [dict(r) for r in c.execute("SELECT * FROM positions WHERE status='open'")]
    if not rows: return
    pairs = await net.dex_pairs(list({r["mint"] for r in rows}))
    for pos in rows:
        p = pairs.get(pos["mint"]); f = net.pair_fields(p) if p else {}
        price = f.get("priceUsd")
        if p and (f.get("liquidityUsd") or 0) <= 0:
            last = c.execute("SELECT price FROM prices WHERE mint=? AND price IS NOT NULL ORDER BY ts DESC LIMIT 1", (pos["mint"],)).fetchone()
            await exit_(pos, "pulled", last[0] if last else pos["entry_price"]); continue
        if not price:
            no_price[pos["id"]] = no_price.get(pos["id"], 0) + 1
            if no_price[pos["id"]] == 4: await telegram.push(f"{pos['name']}: no price for 1 min", [[("Sell on FOMO", links.coin_url(pos["mint"], "solana"))]], mode=pos["mode"])
            log.info(f"{pos['mint']} no price"); continue
        no_price[pos["id"]] = 0; store.price(pos["mint"], price, f.get("v5"))
        pos["opened_at_dt"] = datetime.datetime.fromisoformat(pos["opened_at"].replace("Z", "+00:00"))
        q = {**pos, "opened_at": pos["opened_at_dt"], "trail_active": bool(pos["trail_active"])}
        q, reason = evaluate(q, price, bus.now(), S)
        e = pos["entry_price"]; stopline = e * (1 - q["stop_pct"] / 100); trail = q["peak"] * (1 - S("trail_pct") / 100) if q["trail_active"] else None
        log.info(f"{pos['mint']} price={price} peak={q['peak']} stop={stopline} trail={trail} action={reason}")
        c.execute("UPDATE positions SET peak=?, trail_active=?, stop_pct=? WHERE id=?", (q["peak"], int(q["trail_active"]), q["stop_pct"], pos["id"]))
        if reason: await exit_({**pos, "peak": q["peak"], "stop_pct": q["stop_pct"]}, reason, price)
async def run():
    while True:
        store.beat("risk")
        try: await poll_once()
        except net.RateLimited: log.info("429, back off 30s, polls missed"); await asyncio.sleep(30); continue
        except Exception as e: log.info(f"poll error {e!r}")
        await asyncio.sleep(config.get("risk.poll_s"))
