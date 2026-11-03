import logging, os, asyncio
import net
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def logger(name):
    l = logging.getLogger(name)
    if not l.handlers:
        os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
        h = logging.FileHandler(os.path.join(ROOT, "logs", f"{name}.log")); h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        l.addHandler(h); l.setLevel(logging.INFO); l.propagate = False
    return l
async def top10_pct(mint, pool, supply_ui=None):
    """getTokenLargestAccounts, drop accounts owned by the pool or the bonding curve, sum top 10 % of supply."""
    sup = await net.rpc("getTokenSupply", [mint]); total = float(sup["value"]["uiAmountString"])
    if total <= 0: return None, total
    big = (await net.rpc("getTokenLargestAccounts", [mint]))["value"]
    infos = (await net.rpc("getMultipleAccounts", [[a["address"] for a in big], {"encoding": "jsonParsed"}]))["value"]
    curve = bonding_curve(mint)
    amts = []
    for a, inf in zip(big, infos):
        owner = (((inf or {}).get("data") or {}).get("parsed") or {}).get("info", {}).get("owner")
        if owner in (pool, curve): continue
        amts.append(float(a["uiAmountString"]))
    return round(100 * sum(sorted(amts, reverse=True)[:10]) / total, 2), total
def bonding_curve(mint):
    try:
        from solders.pubkey import Pubkey
        pid = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
        return str(Pubkey.find_program_address([b"bonding-curve", bytes(Pubkey.from_string(mint))], pid)[0])
    except Exception:
        return None
