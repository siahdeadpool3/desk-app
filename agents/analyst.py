"""AGENT 3 · ANALYST. Builds a numbers-only state, gets 4 noul answers (Jev or rules), code applies the gate."""
import asyncio, json, hashlib
import bus, net, config, store, telegram
from agents.common import logger
log = logger("analyst")
asked = set()
def clamp(x): return max(0.0, min(1.0, x))
def rules_answers(f, bundled, S):
    alive = clamp((f.get("v1") or 0) / S("alive_volume_h1"))
    organic = clamp((f.get("b1") or 0) / S("organic_buys_h1"))
    if (bundled or 0) >= S("bundled_from"): organic *= S("bundled_penalty")
    p5 = f.get("p5")   # may be missing -> None -> treated as no move
    b5, s5 = f.get("b5") or 0, f.get("s5") or 0
    if p5 is not None and p5 <= -S("flush_drop_m5_pct") and b5 >= s5: flush = 1.0
    elif p5 is not None and p5 < 0: flush = 0.5
    else: flush = 0.0
    chase = clamp((f.get("p1") or 0) / S("chase_h1_pct"))
    return {"alive_6h": round(alive, 4), "organic": round(organic, 4), "flush": flush, "chase": round(chase, 4)}
def gate(a, S):
    failed = []
    if a["alive_6h"] < S("min_alive_6h"): failed.append(f"alive_6h {a['alive_6h']:.2f}")
    if a["organic"] < S("min_organic"): failed.append(f"organic {a['organic']:.2f}")
    if a["chase"] > S("max_chase"): failed.append(f"chase {a['chase']:.2f}")
    score = round(100 * (a["alive_6h"] + a["organic"] + a["flush"] + (1 - a["chase"])) / 4)
    if score < S("min_score"): failed.append(f"score {score}")
    return score, not failed, failed
def state_text(scan, ctx, f, age):
    s = (f"Coin {scan.get('name')} on Solana, graduated {age} min ago. Liquidity ${f.get('liquidityUsd'):,.0f}. Market cap ${f.get('marketCap') or 0:,.0f}.\n"
         f"Last 5 min: {f.get('b5')} buys, {f.get('s5')} sells, volume ${f.get('v5') or 0:,.0f}, price {f.get('p5') if f.get('p5') is not None else 'n/a'}%.\n"
         f"Last 1h: {f.get('b1')} buys, {f.get('s1')} sells, volume ${f.get('v1') or 0:,.0f}, price {f.get('p1')}%.\n"
         f"Top 10 hold {ctx.get('top10')}%. Dev holds {ctx.get('dev', 0):.1f}%, sold 0. LP {ctx.get('lp')}. Bundled {ctx.get('bund')}. Delegations {ctx.get('del')}.")
    return s[:3000]
async def analyse(item, S=None, pair=None):
    S = S or (lambda k: config.get("analyst." + k)); scan, ctx = item["scan"], item["ctx"]; mint = scan["mint"]
    if pair is None:
        p = (await net.dex_pairs([mint])).get(mint); pair = net.pair_fields(p) if p else None
    if not pair: return {"agent": "analyst", "mint": mint, "answers": None, "score": 0, "passed": False, "failed": ["no answer"], "model": "rules", "inputTokens": 0}
    mode = S("mode")
    if mode != "rules":   # no Jev key on this desk; never falls back silently
        return {"agent": "analyst", "mint": mint, "answers": None, "score": 0, "passed": False, "failed": ["no answer"], "model": "jev-latest", "inputTokens": 0}
    a = rules_answers(pair, ctx.get("bund"), S)
    score, ok, failed = gate(a, S)
    st = state_text(scan, ctx, pair, scan.get("ageMin"))
    j = {"agent": "analyst", "mint": mint, "answers": a, "score": score, "passed": ok, "failed": failed, "model": "rules", "inputTokens": 0, "_pair": pair}
    log.info(f"{mint} {hashlib.sha256(st.encode()).hexdigest()[:12]} {a} score={score} {'pass' if ok else 'reject'} tokens=0")
    return j
async def run():
    while True:
        item = await bus.analyst.get(); store.beat("analyst"); mint = item["scan"]["mint"]
        if mint in asked: continue
        asked.add(mint)
        j = await analyse(item); pair = j.pop("_pair", None)
        store.c().execute("INSERT INTO analyses(mint,score,passed,failed,model,input_tokens,ts,json) VALUES(?,?,?,?,?,?,?,?)",
                          (mint, j["score"], int(j["passed"]), json.dumps(j["failed"]), j["model"], 0, bus.iso(), json.dumps(j)))
        bus.emit("analysis", j)
        if j["passed"]: await bus.executor.put({**item, "analysis": j, "pair": pair})
        else:
            label = "Analyst (rules)" if j["model"] == "rules" else "Analyst"; name = item["scan"].get("name") or mint
            store.activity("reject", f"Rejected {name}", f"{label} · {j['failed'][0]}", "Skipped", mint)
            store.skip(mint, "analyst", j["failed"][0])
            await telegram.maybe_reject_push(name, mint, f"{label} · {j['failed'][0]}")
