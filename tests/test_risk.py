import datetime, asyncio, config, store, telegram
from agents import risk
S = lambda k: config.get("risk." + k)
T0 = datetime.datetime(2026, 11, 3, tzinfo=datetime.timezone.utc)
def pos(stop=6.0): return {"entry_price": 1.0, "peak": 1.0, "stop_pct": stop, "trail_active": False, "opened_at": T0}
def test_trail():
    p, r = risk.evaluate(pos(), 1.25, T0, S); assert r is None and p["trail_active"]
    p, r = risk.evaluate(p, 1.25 * 0.87, T0, S); assert r == "trail"
def test_stop():
    assert risk.evaluate(pos(), 0.939, T0, S)[1] == "stop"
    assert risk.evaluate(pos(), 0.941, T0, S)[1] is None
def test_timeout():
    assert risk.evaluate(pos(), 1.04, T0 + datetime.timedelta(hours=3), S)[1] == "timeout"
def test_loosen_never_moves_open_stop_down():
    config.set_("stop", "-8%")
    p, r = risk.evaluate(pos(6.0), 0.939, T0, S); assert r == "stop" and p["stop_pct"] == 6.0
    config.set_("stop", "-4%"); p, _ = risk.evaluate(pos(6.0), 1.0, T0, S); assert p["stop_pct"] == 4.0   # tighter applies
    config.set_("stop", "-6%")
def test_set_stop_8_new_position():
    reply = telegram.set_setting("stop", "-8%"); assert reply == "stop -6% -> -8%", reply
    c = store.c()
    c.execute("INSERT INTO positions(mint,name,mode,entry_price,size_usd,peak,stop_pct,opened_at,status) VALUES('OLD','Old','PAPER',1,47.5,1,6,?,'open')", (T0.isoformat(),))
    pid = c.execute("INSERT INTO positions(mint,name,mode,entry_price,size_usd,peak,stop_pct,opened_at,status) VALUES('NEW','Newc','PAPER',1,47.5,1,?,?,'open')", (config.get("risk.stop_pct"), T0.isoformat())).lastrowid
    p = {**dict(c.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone()), "opened_at": T0, "trail_active": False}
    p, r = risk.evaluate(p, 0.919, T0, S); assert r == "stop" and p["stop_pct"] == 8
    asyncio.run(risk.exit_({**dict(c.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone()), "peak": 1, "stop_pct": 8}, "stop", 0.919))
    assert telegram.sent[-1]["text"].startswith("PAPER · Newc hit the -8% stop"), telegram.sent[-1]
    a = c.execute("SELECT agent_line FROM activity WHERE mint='NEW'").fetchone()[0]; assert a == "Risk · -8% stop", a
    assert c.execute("SELECT stop_pct FROM positions WHERE mint='OLD'").fetchone()[0] == 6
    assert f"stop -{config.get('risk.stop_pct'):g}%" == "stop -8%"     # Risk pill text
    config.set_("stop", "-6%")
