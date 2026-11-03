"""AGENT 2 · AUDITOR. 8 layers in order, first red stops, rest 'not checked'. No data is never a pass."""
import asyncio, json, time
import bus, net, config, store, telegram
from agents.common import logger, top10_pct
log = logger("auditor")
NAMES = ["Mint authority", "Freeze authority", "Dev wallet", "Top 10 holders", "Liquidity", "Pool age", "Bundled wallets", "Delegations"]
SRC = ["rpc", "rpc", "rpc", "rpc", "rugcheck", "rpc", "rugcheck", "rpc"]
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"; TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
audited = set(); taken = 0; rejected = 0; layer8_killed = 0
class NoData(Exception): pass
class Sources:
    """Real sources. Tests pass a fake with the same methods."""
    async def mint_info(self, mint):
        r = await net.rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}]); v = r["value"]
        return v["data"]["parsed"]["info"]
    async def creator_balance(self, owner, mint):
        from agents.scanner import creator_balance; return await creator_balance(owner, mint)
    async def top10(self, mint, pool): return (await top10_pct(mint, pool))[0]
    async def report(self, mint): return await net.rugcheck(mint, "report")
    async def graph(self, mint): return await net.rugcheck(mint, "graph")
    async def liquidity(self, mint):
        p = (await net.dex_pairs([mint])).get(mint); return net.pair_fields(p)["liquidityUsd"] if p else None
    async def token_accounts(self, mint):
        a = await net.rpc("getProgramAccounts", [TOKEN, {"encoding": "jsonParsed", "filters": [{"dataSize": 165}, {"memcmp": {"offset": 0, "bytes": mint}}]}], timeout=90)
        b = await net.rpc("getProgramAccounts", [TOKEN22, {"encoding": "jsonParsed", "filters": [{"memcmp": {"offset": 0, "bytes": mint}}]}], timeout=90)
        return [x["account"]["data"]["parsed"]["info"] for x in a + b]
def short(a): return f"{a[:4]}...{a[-3:]}"
def biggest_group(graph, mint=None):
    if not isinstance(graph, list): raise NoData
    nodes, edges = set(), []
    for net_ in graph:
        if "links" not in net_: raise NoData
        for n in net_.get("nodes") or []:
            if (n.get("holdings") or 0) > 0: nodes.add(n["id"])
        edges += [(l["source"], l["target"]) for l in net_["links"]]
    parent = {n: n for n in nodes}
    def f(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b in edges:
        if a in parent and b in parent: parent[f(a)] = f(b)
    sizes = {}
    for n in nodes: sizes[f(n)] = sizes.get(f(n), 0) + 1
    big = max(sizes.values()) if sizes else 0
    return big if big > 1 else 0
async def audit(scan, coin, src=None, S=None, emit=True):
    src = src or Sources(); S = S or (lambda k: config.get("auditor." + k))
    mint, pool = scan["mint"], scan["pool"]; layers = []; holders = None; ctx = {}
    async def tryit(fn):
        last = None
        for i in range(int(S("retries")) + 1):
            try: return await asyncio.wait_for(fn(), 120)
            except NoData: raise
            except Exception as e:
                last = e
                if i < S("retries"): await asyncio.sleep(2)
        raise NoData(repr(last))
    async def L1():
        info = ctx["mi"] = await tryit(lambda: src.mint_info(mint))
        return (info.get("mintAuthority") is None, "Revoked" if info.get("mintAuthority") is None else "mint not revoked")
    async def L2():
        info = ctx.get("mi") or await tryit(lambda: src.mint_info(mint))
        return (info.get("freezeAuthority") is None, "Revoked" if info.get("freezeAuthority") is None else "freeze not revoked")
    async def L3():
        info = ctx.get("mi") or await tryit(lambda: src.mint_info(mint))
        try: supply = int(info["supply"]) / 10 ** int(info["decimals"])
        except Exception: supply = 0
        if supply <= 0: return (False, "no supply")
        cr = coin.get("creator")
        if not cr: return (False, "no data: dev")
        bal = await tryit(lambda: src.creator_balance(cr, mint)); pct = 100 * bal / supply
        base = coin.get("creator_balance")
        if base is None: return (False, "no data: dev")
        if bal < float(base) - 1e-9: return (False, "dev sold")
        if pct >= S("max_dev_pct"): return (False, f"dev holds {pct:.0f}%")
        ctx["dev"] = pct; return (True, f"{pct:.1f}% · sold 0")
    async def L4():
        t = await tryit(lambda: src.top10(mint, pool)); ctx["top10"] = t
        return (t < S("max_top10_pct"), f"{t:.1f}%" if t < S("max_top10_pct") else f"top 10 hold {t:.0f}%")
    async def L5():
        rep = await tryit(lambda: src.report(mint))
        m = next((m for m in rep.get("markets") or [] if m.get("pubkey") == pool), None)
        lp = ((m or {}).get("lp") or {}).get("lpLockedPct")
        if lp is None: return (False, "no data: liquidity")
        if lp < S("min_lp_locked_pct"): return (False, "liquidity unlocked")
        liq = await tryit(lambda: src.liquidity(mint))
        if liq is None: return (False, "no data: liquidity")
        if scan.get("liquidityUsd") and liq < 0.5 * scan["liquidityUsd"]: return (False, "liquidity pulled")
        ctx["lp"] = f"{lp:.0f}% locked"; return (True, f"{lp:.0f}% burned" if lp >= 100 else f"{lp:.0f}% locked")
    async def L6():
        ma = coin.get("migrated_at")
        if not ma: return (False, "no data: pool age")
        import datetime
        age = (bus.now() - datetime.datetime.fromisoformat(ma)).total_seconds() / 60
        return (age >= S("min_pool_age_min"), f"{int(age)}m" if age >= S("min_pool_age_min") else "pool too young")
    async def L7():
        g = await tryit(lambda: src.graph(mint))
        try: big = biggest_group(g)
        except NoData: return (False, "no data: bundles")
        ctx["bund"] = big
        return (big < S("max_bundled"), "None" if big == 0 else (f"{big} wallets" if big < S("max_bundled") else f"{big} bundled wallets"))
    async def L8():
        nonlocal holders
        accts = await tryit(lambda: src.token_accounts(mint))
        holders = sum(1 for a in accts if float(a["tokenAmount"]["uiAmountString"] or 0) > 0)
        by = {}
        for a in accts:
            d = a.get("delegate")
            if d: by[d] = by.get(d, 0) + 1
        worst = max(by.items(), key=lambda x: x[1]) if by else None
        ctx["del"] = worst[1] if worst else 0
        if worst and worst[1] > S("max_delegated_accounts"): return (False, f"{worst[1]} wallets → {short(worst[0])}")
        return (True, "None" if not worst else f"max {worst[1]} → {short(worst[0])}")
    fns = [L1, L2, L3, L4, L5, L6, L7, L8]; passed = True; reason = None
    for i, fn in enumerate(fns):
        t0 = time.time()
        if emit: bus.emit("audit_layer", {"mint": mint, "n": i + 1, "state": "running"})
        try: ok, val = await fn()
        except NoData as e:
            ok, val = False, f"no data: {NAMES[i].lower()}"
            if i == 7: await layer8_down()
        L = {"n": i + 1, "name": NAMES[i], "pass": ok, "value": val, "source": SRC[i]}
        layers.append(L); log.info(f"{mint} L{i+1} {val} {int((time.time()-t0)*1000)}ms")
        if emit: bus.emit("audit_layer", {"mint": mint, **L})
        if not ok:
            passed = False; reason = val
            for j in range(i + 1, 8): layers.append({"n": j + 1, "name": NAMES[j], "pass": None, "value": "not checked", "source": SRC[j]})
            break
    j = {"agent": "auditor", "mint": mint, "ts": bus.iso(), "passed": passed, "layersChecked": len([l for l in layers if l["pass"] is not None]),
         "layers": layers, "holders": holders, "reason": reason, "_ctx": ctx}
    log.info(f"{mint} verdict {'pass' if passed else 'red'} {reason}")
    return j
async def layer8_down():
    global layer8_killed
    layer8_killed += 1; store.kv_set("layer8_killed", store.kv_get("layer8_killed", 0) + 1)
    if not store.kv_get("layer8_alerted"):
        store.kv_set("layer8_alerted", True)
        await telegram.push("layer 8 down, every coin is red until rpc_url changes")
async def run():
    global taken, rejected
    while True:
        scan = await bus.auditor.get(); store.beat("auditor")
        mint = scan["mint"]
        if mint in audited: continue
        audited.add(mint); taken += 1
        if not config.get("auditor.enabled"):
            j = {"agent": "auditor", "mint": mint, "passed": True, "layers": [], "skipped": True, "_ctx": {}}
        else:
            j = await audit(scan, store.coin(mint) or {})
        net.drop_rugcheck(mint)
        ctx = j.pop("_ctx", {})
        store.c().execute("INSERT INTO audits(mint,passed,layers_checked,reason,ts,json) VALUES(?,?,?,?,?,?)",
                          (mint, int(j["passed"]), j.get("layersChecked"), j.get("reason"), bus.iso(), json.dumps(j)))
        if j.get("holders") is not None: store.c().execute("UPDATE coins SET holders=? WHERE mint=?", (j["holders"], mint))
        bus.emit("audit", j)
        if j["passed"]: await bus.analyst.put({"scan": scan, "audit": j, "ctx": ctx})
        else:
            rejected += 1; name = scan.get("name") or mint
            store.activity("reject", f"Rejected {name}", f"Auditor · {j['reason']}", "Skipped", mint)
            store.skip(mint, "auditor", f"L{j['layersChecked']} {j['reason']}")
            await telegram.maybe_reject_push(name, mint, f"Auditor · {j['reason']}")
