"""Desk process. Plan B publisher: every 15s copy web/ + data JSON into an orphan gh-pages
commit under /d/{DATA_PATH}/ and force-push, only when content changed. DATA_PATH lives only
in .secrets and the gh-pages tree (never in main)."""
import os, json, shutil, subprocess, hashlib, time, datetime, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); PAGES = os.path.join(ROOT, "pages")
REMOTE = "https://github.com/siahdeadpool3/desk-app.git"
def secrets():
    return dict(l.strip().split("=",1) for l in open(os.path.join(ROOT,".secrets")) if "=" in l)
def git(*a): return subprocess.run(["git","-C",PAGES,*a],check=True,capture_output=True,text=True).stdout
def init_pages():
    if not os.path.isdir(os.path.join(PAGES,".git")):
        os.makedirs(PAGES, exist_ok=True); subprocess.run(["git","init","-q","-b","gh-pages",PAGES],check=True)
        git("remote","add","origin",REMOTE); git("config","user.name","desk"); git("config","user.email","desk@local")
_last = None
def publish(data: dict):
    """data: {filename: obj}. Returns True if pushed."""
    global _last
    init_pages(); dp = secrets()["DATA_PATH"]
    for f in os.listdir(PAGES):
        if f != ".git": p=os.path.join(PAGES,f); shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    shutil.copytree(os.path.join(ROOT,"web"), PAGES, dirs_exist_ok=True)
    dd = os.path.join(PAGES,"d",dp); os.makedirs(dd)   # no index in /d/ -> 404
    for name,obj in data.items():
        os.makedirs(os.path.dirname(os.path.join(dd,name)), exist_ok=True); open(os.path.join(dd,name),"w").write(json.dumps(obj,separators=(",",":")))
    h = hashlib.sha256(subprocess.run(["bash","-c",f"cd {PAGES} && find . -path ./.git -prune -o -type f -print0 | sort -z | xargs -0 sha256sum"],capture_output=True,text=True).stdout.encode()).hexdigest()
    if h == _last: return False
    git("add","-A")
    # single orphan commit each time: keeps the branch tiny, history never accumulates
    tree = git("write-tree").strip(); c = git("commit-tree",tree,"-m","publish").strip()
    git("update-ref","refs/heads/gh-pages",c); git("push","-qf","origin","gh-pages")
    _last = h; return True
def state_snapshot(balance, mode="PAPER", note=None):
    return {"state.json":{"mode":mode,"balance":round(balance,2),"ts":datetime.datetime.now(datetime.timezone.utc).isoformat(),"note":note}}
def candles(rows):
    """1-min OHLC from db.prices rows (ts, price, volume_m5)."""
    out = {}
    for r in rows:
        if r["price"] is None: continue
        k = r["ts"][:16]
        c = out.get(k)
        if not c: out[k] = c = {"t": k + ":00Z", "o": r["price"], "h": r["price"], "l": r["price"], "c": r["price"], "v": r["volume_m5"] or 0}
        c["h"] = max(c["h"], r["price"]); c["l"] = min(c["l"], r["price"]); c["c"] = r["price"]; c["v"] = r["volume_m5"] or c["v"]
    return list(out.values())
def full_snapshot():
    """STEP 7 plan-B data shapes. Every FOMO link comes from links.py here; the app never builds one."""
    import store, config, bus, links
    from agents import scanner, auditor, executor
    from agents.executor import stack_now
    c = store.c(); q = lambda sql, a=(): [dict(r) for r in c.execute(sql, a)]
    S = config.all_settings(c); mode = S["desk.mode"]; cu = lambda m: links.coin_url(m, "solana")
    coins = {r["mint"]: r for r in q("SELECT * FROM coins WHERE first_seen >= datetime('now','-24 hours')")}
    for r in q("SELECT DISTINCT mint FROM positions"): coins.setdefault(r["mint"], store.coin(r["mint"]) or {"mint": r["mint"]})
    hb = {r["agent"]: r for r in q("SELECT * FROM heartbeats")}
    pos = q("SELECT * FROM positions WHERE status IN ('open','exiting','pending')")
    for p in pos: p["link"] = cu(p["mint"])
    closed = q("SELECT * FROM positions WHERE status='closed' ORDER BY closed_at")
    scans = q("SELECT mint,verdict,reason,liq,top10,h1,age_min,ts FROM scans ORDER BY id DESC LIMIT 300")
    audits = [json.loads(r["json"]) for r in q("SELECT json FROM audits ORDER BY id DESC LIMIT 100")]
    anas = [json.loads(r["json"]) for r in q("SELECT json FROM analyses ORDER BY id DESC LIMIT 100")]
    names = lambda m: (coins.get(m) or {}).get("name") or m[:6]
    for x in scans + audits + anas: x["name"] = names(x["mint"]); x["link"] = cu(x["mint"])
    start = S["desk.paper_start_stack"]; bal = round(stack_now(c), 2)
    chart = [{"t": r["closed_at"], "balance": None, "pnl": r["pnl_usd"]} for r in closed]
    run = start
    for p in chart: run += p["pnl"] or 0; p["balance"] = round(run, 2)
    up = lambda a: {"ts": (hb.get(a) or {}).get("ts"), "paused": bool((hb.get(a) or {}).get("paused"))}
    agents = {
      "scanner": {**up("scanner"), "pools": scanner.pools, "waiting": len(scanner.room), "passed": sum(1 for s in scans if s["verdict"] == "pass"),
                  "killed": sum(1 for s in scans if s["verdict"] == "kill"), "feed": scans[:30]},
      "auditor": {**up("auditor"), "taken": auditor.taken or len(audits), "rejected": sum(1 for a in audits if not a["passed"]), "last": audits[:1], "feed": audits[:30]},
      "analyst": {**up("analyst"), "mode": S["analyst.mode"], "minScore": S["analyst.min_score"], "last": anas[:1], "feed": anas[:30]},
      "executor": {**up("executor"), "trades": executor.trades, "stackPct": S["executor.stack_pct"], "feed": [e["data"] for e in bus.events if e["event"] == "executor"][-30:]},
      "risk": {**up("risk"), "open": len(pos), "stopPct": S["risk.stop_pct"], "trailPct": S["risk.trail_pct"],
               "lastExit": (closed[-1]["exit_reason"] if closed else None)}}
    files = {
      "state.json": {"mode": mode, "balance": bal, "startBalance": start, "pnlToday": round(bal - start, 2), "ts": bus.iso(),
                     "openPositions": pos, "signupUrl": links.SIGNUP_URL, "counts": {"seen": len(coins), "trades": len(closed) + len(pos)}},
      "chart.json": {"mode": mode, "start": start, "points": chart},
      "activity.json": [{**a, "link": a["link"] or (cu(a["mint"]) if a["mint"] else None)} for a in q("SELECT * FROM activity ORDER BY id DESC LIMIT 200")],
      "agents.json": agents,
      "audits.json": audits,
      "account.json": {"settings": S, "handle": S["desk.fomo_handle"], "profileUrl": links.profile_url(S["desk.fomo_handle"]),
                       "signupUrl": links.SIGNUP_URL, "notifier": "telegram", "planB": True,
                       "pushNote": "Web push is not available on plan B. Alerts come through Telegram only.",
                       "changeNote": "Settings are read-only here on plan B. Change them in Telegram, e.g. \"set stop to -8%\"."},
    }
    for m, co in coins.items():
        pr = q("SELECT ts,price,volume_m5 FROM prices WHERE mint=? ORDER BY ts", (m,))
        au = next((a for a in audits if a["mint"] == m), None)
        p = next((x for x in pos if x["mint"] == m), None) or next((x for x in reversed(closed) if x["mint"] == m), None)
        line = None
        if p and p.get("status") == "open":
            e = p["entry_price"]; line = max(e * (1 - p["stop_pct"] / 100), (p["peak"] * (1 - S["risk.trail_pct"] / 100)) if p["trail_active"] else 0)
        files[f"coin/{m}.json"] = {"mint": m, "name": co.get("name"), "symbol": co.get("symbol"), "pool": co.get("pool"), "holders": co.get("holders"),
            "migratedAt": co.get("migrated_at"), "link": cu(m), "candles": candles(pr)[-240:], "audit": au,
            "analysis": next((a for a in anas if a["mint"] == m), None), "scan": next((s for s in scans if s["mint"] == m), None),
            "position": p, "riskLine": line}
        if au: files[f"audit/{m}.json"] = au
    return files
async def publisher():
    import asyncio
    while True:
        try: await asyncio.to_thread(publish, full_snapshot())
        except Exception as e: print("publish failed", repr(e), file=sys.stderr, flush=True)
        await asyncio.sleep(60)   # Pages builds take 30s-6min and soft-limit ~10/h; 60s approved
async def amain():
    import asyncio, bus, store, config, telegram
    from agents import scanner, auditor, analyst, executor, risk
    bus.init(); c = store.c()
    c.execute("INSERT INTO nights(mode,started,start_balance) VALUES(?,?,?)", (config.get("desk.mode", c), bus.iso(), executor.stack_now(c)))
    tc = executor.ticket_check(c)
    if tc: await telegram.send(tc)
    await asyncio.gather(scanner.run(), auditor.run(), analyst.run(), executor.run(), risk.run(), telegram.run(), publisher())
if __name__ == "__main__":
    import asyncio; asyncio.run(amain())
