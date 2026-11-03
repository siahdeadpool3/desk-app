import asyncio, httpx, json, logging
import config
log = logging.getLogger("net")
_client = None
def client():
    global _client
    if _client is None: _client = httpx.AsyncClient(timeout=20, headers={"User-Agent": "desk/1.0"})
    return _client
class RateLimited(Exception): pass
async def get_json(url, **kw):
    r = await client().get(url, **kw)
    if r.status_code == 429: raise RateLimited(url)
    r.raise_for_status(); return r.json()
_rpc_lock = asyncio.Semaphore(4)
async def rpc(method, params, timeout=30):
    async with _rpc_lock:
        r = await client().post(config.get("desk.rpc_url"), json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=timeout)
        if r.status_code == 429: raise RateLimited(method)
        r.raise_for_status(); j = r.json()
        if "error" in j: raise RuntimeError(f"rpc {method}: {j['error']}")
        return j["result"]
async def dex_pairs(mints):
    """{mint: best pumpswap pair} from batched /tokens/v1 calls (30 per call)."""
    out = {}
    for i in range(0, len(mints), 30):
        chunk = mints[i:i+30]
        pairs = await get_json("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(chunk))
        for p in pairs or []:
            if p.get("dexId") != "pumpswap": continue
            m = (p.get("baseToken") or {}).get("address")
            if m not in chunk: continue
            if m not in out or ((p.get("liquidity") or {}).get("usd") or 0) > ((out[m].get("liquidity") or {}).get("usd") or 0):
                out[m] = p
    return out
def pair_fields(p):
    g = lambda *ks: _dig(p, ks)
    f = lambda v: float(v) if v is not None else None
    return {"pool": p.get("pairAddress"), "name": g("baseToken","name"), "symbol": g("baseToken","symbol"),
            "priceUsd": f(p.get("priceUsd")), "liquidityUsd": f(g("liquidity","usd")), "marketCap": f(p.get("marketCap")),
            "v5": f(g("volume","m5")), "v1": f(g("volume","h1")), "b5": g("txns","m5","buys"), "s5": g("txns","m5","sells"),
            "b1": g("txns","h1","buys"), "s1": g("txns","h1","sells"), "p5": f(g("priceChange","m5")),
            "p1": f(g("priceChange","h1")), "p24": f(g("priceChange","h24")), "pairCreatedAt": p.get("pairCreatedAt")}
def _dig(d, ks):
    for k in ks:
        if not isinstance(d, dict): return None
        d = d.get(k)
    return d
_rc = {}
async def rugcheck(mint, which):
    """Each RugCheck endpoint fetched once per audit (cached per mint)."""
    k = (mint, which)
    if k not in _rc:
        path = "report" if which == "report" else "insiders/graph"
        _rc[k] = await get_json(f"https://api.rugcheck.xyz/v1/tokens/{mint}/{path}")
    return _rc[k]
def drop_rugcheck(mint):
    for w in ("report", "graph"): _rc.pop((mint, w), None)
