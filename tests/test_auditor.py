import asyncio
from agents import auditor
class Fake:
    async def mint_info(self, m): return {"mintAuthority": None, "freezeAuthority": "FrZ111", "supply": "1000000000000000", "decimals": 6}
def test_freeze_red_layer2():
    S = lambda k: {"retries": 0, "max_dev_pct": 5, "max_top10_pct": 25, "min_lp_locked_pct": 99, "min_pool_age_min": 10, "max_bundled": 5, "max_delegated_accounts": 10}[k]
    j = asyncio.run(auditor.audit({"mint": "M", "pool": "P"}, {}, Fake(), S, emit=False))
    assert not j["passed"] and j["layersChecked"] == 2 and j["reason"] == "freeze not revoked"
    assert [l["value"] for l in j["layers"][2:]] == ["not checked"] * 6
    print(j["layers"])
def test_graph_links():
    g = [{"nodes": [{"id": a, "holdings": 1} for a in "ABCDEF"], "links": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]}]
    assert auditor.biggest_group(g) == 3
    try: auditor.biggest_group([{"nodes": []}]); assert False
    except auditor.NoData: pass
