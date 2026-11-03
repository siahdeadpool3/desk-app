"""STEP 10 settings: defaults, ranges, aliases, validation, change_log."""
import json, datetime
from db import conn
# key: (default, min, max)  (strings: (default, allowed, None))
DEFAULTS = {
 "scanner.min_liquidity_usd":(40000,1000,10_000_000),"scanner.max_top10_pct":(25,1,100),
 "scanner.max_h1_change_pct":(80,1,10000),"scanner.poll_s":(60,15,600),"scanner.min_pool_age_min":(10,0,240),
 "scanner.max_wait_min":(60,5,720),"scanner.runner_h24_pct":(300,10,100000),
 "auditor.enabled":(True,None,None),"auditor.max_dev_pct":(5,0,100),"auditor.max_top10_pct":(25,1,100),
 "auditor.min_lp_locked_pct":(99,0,100),"auditor.min_pool_age_min":(10,0,240),"auditor.max_bundled":(5,1,1000),
 "auditor.max_delegated_accounts":(10,1,10000),"auditor.retries":(3,0,10),
 "analyst.mode":("rules",("rules","jev"),None),"analyst.min_alive_6h":(0.70,0,1),"analyst.min_organic":(0.65,0,1),
 "analyst.max_chase":(0.30,0,1),"analyst.min_score":(70,0,100),"analyst.timeout_s":(10,1,60),
 "analyst.alive_volume_h1":(25000,100,10_000_000),"analyst.organic_buys_h1":(150,1,100000),
 "analyst.bundled_penalty":(0.5,0,1),"analyst.bundled_from":(3,1,1000),"analyst.flush_drop_m5_pct":(5,0,100),
 "analyst.chase_h1_pct":(80,1,10000),
 "executor.stack_pct":(8,0.1,100),"executor.max_pool_pct":(2,0.01,100),"executor.min_ticket_usd":(47.50,5,100000),
 "executor.below_min":("bump",("bump","skip"),None),"executor.recheck_liq_drop_pct":(20,0,100),
 "executor.recheck_price_up_pct":(15,0,1000),"executor.confirm_window_min":(5,1,60),
 "risk.poll_s":(15,5,300),"risk.stop_pct":(6,0.5,90),"risk.trail_start_pct":(20,1,1000),"risk.trail_pct":(12,0.5,90),
 "risk.timeout_h":(3,0.25,72),"risk.timeout_min_gain_pct":(5,-100,1000),"risk.confirm_window_min":(2,1,60),
 "desk.mode":("PAPER",("PAPER","LIVE"),None),"desk.paper_start_stack":(200,1,1_000_000),"desk.stack":(200,1,100_000_000),
 "desk.report_time":("08:00",None,None),"desk.notifier":("telegram",("telegram","webpush","channel"),None),
 "desk.rpc_url":("https://api.mainnet-beta.solana.com",None,None),"desk.push_rejects":(False,None,None),
 "desk.fees_ref_discount":(0.10,0,1),"desk.fomo_handle":("@dont_quote_siah",None,None),
}
ALIASES = {"stop":"risk.stop_pct","trail":"risk.trail_pct","stack":"desk.stack","mode":"desk.mode"}
def resolve(name):
    n = name.strip().lower().replace(" ","_")
    if n in ALIASES: return ALIASES[n]
    if n in DEFAULTS: return n
    hits = [k for k in DEFAULTS if k.split(".",1)[1] == n]
    if len(hits) == 1: return hits[0]
    raise KeyError(f"unknown or ambiguous setting {name!r}" + (f": {hits}" if hits else ""))
def validate(key, value):
    d, lo, hi = DEFAULTS[key]
    if isinstance(d, bool):
        if isinstance(value, str): value = value.lower() in ("1","true","on","yes")
        return bool(value)
    if isinstance(d, (int, float)):
        v = abs(float(str(value).replace("%","").replace("$",""))) if key.endswith("stop_pct") else float(str(value).replace("%","").replace("$",""))
        if not (lo <= v <= hi): raise ValueError(f"{key} must be between {lo} and {hi}")
        return int(v) if isinstance(d, int) and v.is_integer() else v
    if isinstance(lo, tuple):
        v = str(value)
        v = v.upper() if key == "desk.mode" else v.lower()
        if v not in lo: raise ValueError(f"{key} must be one of {lo}")
        return v
    return str(value)
def get(key, c=None):
    c = c or conn(); r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r[0]) if r else DEFAULTS[key][0]
def all_settings(c=None):
    return {k: get(k, c) for k in DEFAULTS}
def set_(name, value, source="app", c=None):
    c = c or conn(); key = resolve(name); old = get(key, c); new = validate(key, value)
    c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, json.dumps(new)))
    c.execute("INSERT INTO change_log(ts,key,old,new,source) VALUES(?,?,?,?,?)",
              (datetime.datetime.now(datetime.timezone.utc).isoformat(), key, json.dumps(old), json.dumps(new), source))
    return key, old, new
def min_stack(c=None):
    return get("executor.min_ticket_usd", c) / (get("executor.stack_pct", c) / 100)
