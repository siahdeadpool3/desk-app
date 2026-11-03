"""AGENT 1 · SCANNER. Counts and cuts. One PumpPortal websocket for the desk."""
import asyncio, json, re, time, datetime
import websockets
import bus, net, config, store
from agents.common import logger, top10_pct
log = logger("scanner")
room = {}          # mint -> {"migratedAt": dt, "seen": t, "top10": (pct, ts)}
decided = set()    # mints decided tonight (pass or kill) - never sent twice
pools = 0
def norm(s): return re.sub(r"[\s\d]|[^\w]", "", (s or "").lower())
def copycat(name, symbol, runners):
    """runners: list of (name, symbol). exact match or one inside the other."""
    for rn, rs in runners:
        for a in (norm(name), norm(symbol)):
            for b in (norm(rn), norm(rs)):
                if a and b and len(min(a, b, key=len)) >= 3 and (a == b or a in b or b in a): return rn
    return None
def fmt_k(v): return f"${v/1000:.1f}K" if v < 1e6 else f"${v/1e6:.2f}M"
def runners(c, mint):
    r = c.execute("SELECT name,symbol FROM coins WHERE mint!=? AND h24_change>=? AND first_seen>=date('now')",
                  (mint, config.get("scanner.runner_h24_pct", c))).fetchall()
    return [(x[0], x[1]) for x in r]
async def on_migration(msg):
    global pools
    mint = msg.get("mint")
    if not mint or mint in room or mint in decided or msg.get("txType") not in (None, "migrate"): return
    pools += 1
    now = bus.now(); room[mint] = {"migratedAt": now, "seen": time.time()}
    creator, cbal = None, None
    try:
        rep = await net.rugcheck(mint, "report"); creator = rep.get("creator"); cbal = rep.get("creatorBalance")
    except Exception as e: log.info(f"{mint} rugcheck creator lookup failed {e}")
    if creator:
        try: cbal = await creator_balance(creator, mint)
        except Exception: pass
    store.c().execute("INSERT OR IGNORE INTO coins(mint,creator,creator_balance,migrated_at,signature,first_seen) VALUES(?,?,?,?,?,?)",
                      (mint, creator, cbal, now.isoformat(), msg.get("signature"), now.isoformat()))
    bus.emit("scanner_seen", {"mint": mint, "pools": pools})
async def creator_balance(owner, mint):
    r = await net.rpc("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed"}])
    return sum(float(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmountString"]) for a in r["value"])
def out(mint, f, top10, age, verdict, reason):
    j = {"agent": "scanner", "mint": mint, "name": f.get("name"), "symbol": f.get("symbol"), "pool": f.get("pool"),
         "liquidityUsd": f.get("liquidityUsd"), "top10Pct": top10, "h1ChangePct": f.get("p1"), "ageMin": age,
         "verdict": verdict, "reason": reason, "ts": bus.iso()}
    store.c().execute("INSERT INTO scans(mint,verdict,reason,liq,top10,h1,age_min,ts,json) VALUES(?,?,?,?,?,?,?,?,?)",
                      (mint, verdict, reason, f.get("liquidityUsd"), top10, f.get("p1"), age, j["ts"], json.dumps(j)))
    log.info(f"{j['ts']} {mint} {verdict} {reason} liq={f.get('liquidityUsd')} top10={top10} h1={f.get('p1')} age={age}")
    bus.emit("scan", j); return j
async def poll_once():
    c = store.c(); S = lambda k: config.get("scanner." + k, c)
    for mint in [m for m, r in room.items() if (bus.now() - r["migratedAt"]).total_seconds() / 60 >= S("max_wait_min")]:
        out(mint, {}, None, int(S("max_wait_min")), "kill", "never qualified"); store.skip(mint, "scanner", "never qualified")
        room.pop(mint); decided.add(mint)
    if not room: return
    pairs = await net.dex_pairs(list(room))
    for mint, p in pairs.items():
        f = net.pair_fields(p); r = room.get(mint)
        if not r: continue
        store.price(mint, f["priceUsd"], f["v5"])
        c.execute("UPDATE coins SET name=?,symbol=?,pool=?,h24_change=? WHERE mint=?", (f["name"], f["symbol"], f["pool"], f["p24"], mint))
        age = int((bus.now() - r["migratedAt"]).total_seconds() // 60)
        reason = None
        liq = f["liquidityUsd"] or 0
        if liq < S("min_liquidity_usd"): reason = f"liq {fmt_k(liq)}"
        top10 = None
        if not reason:
            t = r.get("top10")
            if not t or time.time() - t[1] > 120:
                try: t = ((await top10_pct(mint, f["pool"]))[0], time.time()); r["top10"] = t
                except Exception as e: log.info(f"{mint} top10 rpc error {e}"); continue   # wait in room
            top10 = t[0]
            if top10 is None: continue
            if top10 > S("max_top10_pct"): reason = f"top 10 hold {top10:.0f}%"
        if not reason and f["p1"] is not None and f["p1"] > S("max_h1_change_pct"): reason = f"+{f['p1']:.0f}% in 1h"
        if not reason:
            cc = copycat(f["name"], f["symbol"], runners(c, mint))
            if cc: reason = f"copycat of {cc}"
        if reason:
            out(mint, f, top10, age, "kill", reason); store.skip(mint, "scanner", reason); room.pop(mint); decided.add(mint)
        elif age >= S("min_pool_age_min"):
            j = out(mint, f, top10, age, "pass", None); room.pop(mint); decided.add(mint)
            await bus.auditor.put(j)
async def poll_loop():
    while True:
        store.beat("scanner")
        if not store.paused("scanner"):
            try: await poll_once()
            except net.RateLimited: log.info("dexscreener 429, wait 30s"); await asyncio.sleep(30); continue
            except Exception as e: log.info(f"poll error {e!r}")
        await asyncio.sleep(config.get("scanner.poll_s"))
async def ws_loop():
    back = 1
    while True:
        try:
            async with websockets.connect("wss://pumpportal.fun/api/data", ping_interval=20) as w:
                await w.send(json.dumps({"method": "subscribeMigration"})); back = 1
                log.info("ws connected")
                while True:
                    raw = await asyncio.wait_for(w.recv(), 120)
                    try: d = json.loads(raw)
                    except Exception: continue
                    if "mint" in d and not store.paused("scanner"): await on_migration(d)
        except Exception as e:
            store.c().execute("INSERT INTO ws_events(ts,kind) VALUES(?,?)", (bus.iso(), "reconnect"))
            log.info(f"ws reconnect in {back}s ({e!r})"); await asyncio.sleep(back); back = min(back * 2, 60)
async def run(): await asyncio.gather(ws_loop(), poll_loop())
