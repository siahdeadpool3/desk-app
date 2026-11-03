"""Field mapping proven from logs/raw samples (2026-11-03). None = key not present in raw; never guessed."""
MIGRATION = {  # pumpportal subscribeMigration message
    "mint": "mint", "signature": "signature", "txType": "txType",
    "pool": None,     # raw 'pool' is the string "pump-amm" (venue label), NOT a pool address -> pool address from DexScreener pairAddress
    "creator": None,  # not in message -> RugCheck report.creator
}
DEX = {  # DexScreener /tokens/v1/solana/{mints} -> list of pairs; pick dexId=='pumpswap', max liquidity.usd
    "pairAddress": "pairAddress", "dexId": "dexId", "mint": "baseToken.address",
    "name": "baseToken.name", "symbol": "baseToken.symbol", "priceUsd": "priceUsd",
    "liquidityUsd": "liquidity.usd", "marketCap": "marketCap",
    "volume_m5": "volume.m5", "volume_h1": "volume.h1", "volume_h24": "volume.h24",
    "buys_m5": "txns.m5.buys", "sells_m5": "txns.m5.sells",
    "buys_h1": "txns.h1.buys", "sells_h1": "txns.h1.sells",
    "priceChange_m5": "priceChange.m5",  # ABSENT in sample (m5 omitted when no m5 trades) -> treat missing as None
    "priceChange_h1": "priceChange.h1", "priceChange_h24": "priceChange.h24",
    "pairCreatedAt": "pairCreatedAt",  # epoch ms
}
RUGCHECK_REPORT = {
    "creator": "creator", "creatorBalance": "creatorBalance",
    "markets": "markets", "market_pool": "markets[].pubkey", "market_type": "markets[].marketType",  # pumpswap = 'pump_fun_amm'
    "lp_locked_pct": "markets[].lp.lpLockedPct", "lp_burned_pct": None,  # no burned-pct key; lpLockedPct covers locked/burned
    "topHolders": "topHolders", "holder_owner": "topHolders[].owner", "holder_pct": "topHolders[].pct",
    "mintAuthority": "mintAuthority", "freezeAuthority": "freezeAuthority", "totalHolders": "totalHolders",
}
RUGCHECK_GRAPH = {  # top level is a LIST of networks
    "networks": "[]", "nodes": "[].nodes", "node_wallet": "[].nodes[].id", "node_holdings": "[].nodes[].holdings",
    "edges": "[].links",  # key is 'links' (NOT 'edges'); each {source,target}
}
RPC_MINT = {  # getAccountInfo jsonParsed
    "mintAuthority": "result.value.data.parsed.info.mintAuthority",
    "freezeAuthority": "result.value.data.parsed.info.freezeAuthority",
    "supply": "result.value.data.parsed.info.supply",  # string, raw units
    "decimals": "result.value.data.parsed.info.decimals",
    "program": "result.value.owner",  # pump mints are Token-2022
}
def get(d, path):
    for p in path.split("."):
        if d is None: return None
        d = d.get(p) if isinstance(d, dict) else None
    return d
