"""db helpers shared by agents."""
import json, db, bus, links
C = None
def c():
    global C
    if C is None: C = db.conn()
    return C
def activity(kind, title, agent_line, right, mint=None, mode=None):
    import config
    mode = mode or config.get("desk.mode", c())
    c().execute("INSERT INTO activity(ts,kind,title,agent_line,right,mint,mode,link) VALUES(?,?,?,?,?,?,?,?)",
                (bus.iso(), kind, title, agent_line, right, mint, mode, links.coin_url(mint, "solana") if mint else None))
    bus.emit("activity", {"kind": kind, "title": title, "agent": agent_line, "right": right, "mint": mint})
def skip(mint, agent, reason):
    c().execute("INSERT INTO skips(mint,agent,reason,ts) VALUES(?,?,?,?)", (mint, agent, reason, bus.iso()))
def beat(agent):
    c().execute("INSERT INTO heartbeats(agent,ts) VALUES(?,?) ON CONFLICT(agent) DO UPDATE SET ts=excluded.ts", (agent, bus.iso()))
def paused(agent):
    r = c().execute("SELECT paused FROM heartbeats WHERE agent=?", (agent,)).fetchone()
    return bool(r and r[0])
def coin(mint):
    r = c().execute("SELECT * FROM coins WHERE mint=?", (mint,)).fetchone()
    return dict(r) if r else None
def price(mint, p, v5):
    c().execute("INSERT INTO prices VALUES(?,?,?,?)", (mint, bus.iso(), p, v5))
def kv_get(k, d=None):
    r = c().execute("SELECT value FROM kv WHERE key=?", (k,)).fetchone(); return json.loads(r[0]) if r else d
def kv_set(k, v): c().execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (k, json.dumps(v)))
