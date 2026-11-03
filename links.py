"""The only place FOMO URLs are built. Every URL carries the ref r=savipww."""
REF = "savipww"
SIGNUP_URL = f"https://fomo.family/r/{REF}"
CHAINS = {"solana"}
def coin_url(mint: str, chain: str = "solana") -> str:
    if chain not in CHAINS or not mint:
        return SIGNUP_URL
    return f"https://fomo.family/tokens/{chain}/{mint}?r={REF}"
def profile_url(handle: str) -> str:
    return f"https://fomo.family/{handle.lstrip('@')}?r={REF}"
