"""STEP 9 · Telegram: owner-only long polling, pushes with buttons, commands. FOMO URLs only from links.py."""
import asyncio, os, json, re, logging
import httpx
import config, links, store, bus
ROOT = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("telegram")
DRY = os.environ.get("DESK_TG_DRY") == "1"; sent = []   # tests: collect instead of sending
def _sec():
    return dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".secrets")) if "=" in l)
def api(): return f"https://api.telegram.org/bot{_sec()['TG_TOKEN']}/"
def owner(): return int(_sec()["OWNER_CHAT_ID"])
def kb(buttons):
    if not buttons: return None
    return {"inline_keyboard": [[{"text": t, "url": v} if v.startswith("http") else {"text": t, "callback_data": v} for t, v in row] for row in buttons]}
async def send(text, buttons=None, chat=None):
    if DRY: sent.append({"text": text, "buttons": buttons}); return True
    body = {"chat_id": chat or owner(), "text": text, "disable_web_page_preview": True}
    if buttons: body["reply_markup"] = kb(buttons)
    for i in range(3):
        try:
            async with httpx.AsyncClient(timeout=15) as h:
                r = await h.post(api() + "sendMessage", json=body)
                if r.status_code == 200: return True
                logging.getLogger("telegram").warning(f"send {r.status_code} {r.text[:200]}")
        except Exception as e: log.warning(f"send error {e!r}")
        await asyncio.sleep(2)
    return False
async def push(text, buttons=None, mode=None):
    mode = mode or config.get("desk.mode", store.c())
    if mode == "PAPER" and not text.startswith("PAPER · "): text = "PAPER · " + text
    return await send(text, buttons)
async def maybe_reject_push(name, mint, line):
    if config.get("desk.push_rejects", store.c()): await push(f"Rejected {name} · {line}", [[(name, links.coin_url(mint, "solana"))]])
HELP = ("buy X · sell X · why X · pause/resume Agent · set stop to -8% · stack 1240 · status · paper | live · invite · report\n"
        "X can be a name, symbol or mint.")
AGENTS = ["scanner", "auditor", "analyst", "executor", "risk"]
def find(x):
    c = store.c(); x = x.strip()
    rows = c.execute("SELECT mint,name,symbol FROM coins WHERE mint=? OR lower(name)=lower(?) OR lower(symbol)=lower(?) OR lower(symbol)=lower(?)",
                     (x, x, x, x.lstrip("$"))).fetchall()
    return [dict(r) for r in rows]
async def resolve(x):
    rows = find(x)
    if not rows:
        if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", x.strip()): return {"mint": x.strip(), "name": x.strip()[:6], "symbol": None}
        await send(f"I don't know {x}. Send me its mint address."); return None
    if len(rows) > 1:
        await send("Which one?\n" + "\n".join(f"{r['name']} ({r['symbol']}) {links.coin_url(r['mint'], 'solana')}" for r in rows)); return None
    return rows[0]
def cu(m): return links.coin_url(m, "solana")
async def handle_text(t):
    c = store.c(); t = t.strip().lstrip("/"); low = t.lower()
    m = re.match(r"(buy|sell|why)\s+(.+)", t, re.I)
    if m:
        verb, x = m.group(1).lower(), m.group(2); coin = await resolve(x)
        if not coin: return
        mint, name = coin["mint"], coin["name"] or coin["mint"][:6]
        if verb == "buy":
            pos = c.execute("SELECT * FROM positions WHERE mint=? ORDER BY id DESC LIMIT 1", (mint,)).fetchone()
            if pos:
                return await push(f"Buy {name} · ${pos['size_usd']:.2f}", [[("Buy on FOMO", cu(mint))], [("Bought", f"bought:{pos['id']}")]], mode=pos["mode"])
            from agents import auditor
            scan = c.execute("SELECT json FROM scans WHERE mint=? ORDER BY id DESC LIMIT 1", (mint,)).fetchone()
            scan = json.loads(scan[0]) if scan else {"mint": mint, "pool": None}
            if not scan.get("pool"):
                import net
                p = (await net.dex_pairs([mint])).get(mint); scan["pool"] = p and p.get("pairAddress")
            await send(f"Taking {name} apart…")
            j = await auditor.audit(scan, store.coin(mint) or {}, emit=False)
            lines = "\n".join(f"{'✅' if l['pass'] else ('❌' if l['pass'] is False else '▫️')} {l['n']} {l['name']}: {l['value']}" for l in j["layers"])
            return await send(f"{name} {cu(mint)}\n{lines}\nnot sized, not on the desk", [[("Buy on FOMO", cu(mint))]])
        if verb == "sell":
            pos = c.execute("SELECT * FROM positions WHERE mint=? AND status IN ('open','exiting') ORDER BY id DESC LIMIT 1", (mint,)).fetchone()
            if not pos: return await send(f"No open position in {name} {cu(mint)}")
            return await push(f"Sell {name}", [[("Sell on FOMO", cu(mint))]] + ([[("Sold", f"sold:{pos['id']}")]] if pos["mode"] == "LIVE" else []), mode=pos["mode"])
        return await send(why(mint, name))
    m = re.match(r"(pause|resume)\s+(\w+)", low)
    if m:
        a = m.group(2)
        if a not in AGENTS: return await send(f"Agents: {', '.join(AGENTS)}")
        if a == "risk" and m.group(1) == "pause" and c.execute("SELECT 1 FROM positions WHERE status IN ('open','exiting')").fetchone():
            return await send("Risk can't be paused while a position is open.")
        c.execute("INSERT INTO heartbeats(agent,ts,paused) VALUES(?,?,?) ON CONFLICT(agent) DO UPDATE SET paused=excluded.paused", (a, bus.iso(), int(m.group(1) == "pause")))
        return await send(f"{a.title()} {'paused' if m.group(1) == 'pause' else 'resumed'}")
    m = re.match(r"set\s+(.+?)\s+(?:to\s+)?(\S+)$", t, re.I)
    if m: return await send(set_setting(m.group(1), m.group(2)))
    m = re.match(r"stack\s+\$?([\d.,]+)$", low)
    if m:
        r = set_setting("stack", m.group(1).replace(",", "")); from agents.executor import ticket_check
        tc = ticket_check(c); return await send(r + (f"\n{tc}" if tc else ""))
    if low == "status": return await status()
    if low == "paper":
        config.set_("desk.mode", "PAPER", "telegram"); return await send("Mode PAPER")
    if t == "LIVE" or low == "live":
        if t != "LIVE": return await send("Type LIVE (capitals) to switch to LIVE.")
        if not c.execute("SELECT 1 FROM nights WHERE mode='PAPER' AND ended IS NOT NULL").fetchone():
            return await send("LIVE needs at least 1 full PAPER night first.")
        config.set_("desk.mode", "LIVE", "telegram"); return await send("Mode LIVE. Money moves only when you tap Buy on FOMO.")
    if low == "invite": return await send(links.SIGNUP_URL)
    if low == "report":
        u = store.kv_get("last_report_url"); return await send(u or "No morning Page yet.")
    if low in ("start", "help"): return await send(HELP)
    return await send(HELP)
def set_setting(name, val):
    try:
        key, old, new = config.set_(name, val, "telegram")
    except (KeyError, ValueError) as e: return str(e)
    short = key.split(".", 1)[1].replace("_pct", "")
    fmt = lambda v: f"-{v:g}%" if key == "risk.stop_pct" else (f"{v:g}%" if key.endswith("_pct") else str(v))
    return f"{short} {fmt(old)} -> {fmt(new)}"
def why(mint, name):
    c = store.c(); u = cu(mint)
    for tbl, cond, f in (("scans", "verdict='kill'", lambda r: f"Scanner · {r['reason']}"), ("audits", "passed=0", lambda r: f"Auditor · layer {r['layers_checked']} · {r['reason']}"),
                         ("analyses", "passed=0", lambda r: f"Analyst (rules) · {json.loads(r['failed'])[0]}")):
        r = c.execute(f"SELECT * FROM {tbl} WHERE mint=? AND {cond} ORDER BY id DESC LIMIT 1", (mint,)).fetchone()
        if r: return f"{name} {u}\nstopped by {f(r)} at {r['ts']}"
    r = c.execute("SELECT * FROM skips WHERE mint=? ORDER BY id DESC LIMIT 1", (mint,)).fetchone()
    if r: return f"{name} {u}\nstopped by {r['agent'].title()} · {r['reason']} at {r['ts']}"
    return f"{name} {u}\nnothing stopped it (not seen or still in play)"
async def status():
    c = store.c(); from agents.executor import stack_now
    mode = config.get("desk.mode", c); rows = c.execute("SELECT * FROM positions WHERE status IN ('open','exiting','pending')").fetchall()
    await send(f"{mode} · balance ${stack_now(c):,.2f} · {len(rows)} open")
    for r in rows: await send(f"{r['name']} · ${r['size_usd']:.2f} @ {r['entry_price']:.8g} · stop -{r['stop_pct']:g}%", [[("Sell on FOMO", cu(r["mint"]))]])
async def on_callback(cb):
    data = cb.get("data", "")
    from agents import executor, risk
    if data.startswith("bought:"): r = executor.confirm_bought(int(data.split(":")[1])); msg = "Position opened" if r else "Already handled"
    elif data.startswith("sold:"): risk.confirm_sold(int(data.split(":")[1])); msg = "Position closed"
    else: msg = "?"
    if not DRY:
        async with httpx.AsyncClient(timeout=15) as h: await h.post(api() + "answerCallbackQuery", json={"callback_query_id": cb["id"], "text": msg})
async def run():
    off = store.kv_get("tg_offset", 0)
    async with httpx.AsyncClient(timeout=60) as h:
        while True:
            try:
                r = (await h.get(api() + "getUpdates", params={"offset": off, "timeout": 50})).json()
                for u in r.get("result", []):
                    off = u["update_id"] + 1; store.kv_set("tg_offset", off)
                    src = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
                    frm = (u.get("message") or u.get("callback_query") or {}).get("from", {})
                    if frm.get("id") != owner() and (src.get("chat") or {}).get("id") != owner(): continue   # owner only
                    try:
                        if "callback_query" in u: await on_callback(u["callback_query"])
                        elif u.get("message", {}).get("text"): await handle_text(u["message"]["text"])
                    except Exception as e: log.warning(f"cmd error {e!r}"); await send(f"Error: {e}")
            except Exception as e: log.warning(f"poll {e!r}"); await asyncio.sleep(5)
