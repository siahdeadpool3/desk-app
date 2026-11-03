import config, store
from agents.executor import size, ticket_check
def S(over=None):
    return lambda k: (over or {}).get(k, config.DEFAULTS["executor." + k][0])
def test_200_bump():
    assert size(200, 0, 1e9, S()) == (47.5, "bump", "sent", None)   # 8% of 200 = $16 < 47.50 -> bump
def test_200_skip():
    s = size(200, 0, 1e9, S({"below_min": "skip"})); assert s[2] == "skipped"
def test_pool_cap():
    assert size(100000, 0, 40000, S())[0] == 800
def test_paper_skip_warning():
    c = store.c(); config.set_("executor.below_min", "skip")
    assert "every coin will be skipped" in ticket_check(c)
    config.set_("executor.below_min", "bump"); assert ticket_check(c).startswith("tickets bumped to $47.50 = 23.8% of stack")
