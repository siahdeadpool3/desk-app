"""FOMO on Solana fees, per side, then minus the ref discount. Gas = 0."""
def side_fee(ticket: float, ref_discount: float = 0.10) -> float:
    if ticket <= 0: return 0.0
    if ticket < 47.50: f = 0.02 * ticket
    elif ticket <= 190: f = 0.95
    else: f = 0.005 * ticket
    return round(f * (1 - ref_discount), 6)
def round_trip(entry_usd: float, exit_usd: float, ref_discount: float = 0.10) -> float:
    return round(side_fee(entry_usd, ref_discount) + side_fee(exit_usd, ref_discount), 6)
