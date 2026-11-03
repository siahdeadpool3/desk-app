import re, subprocess, os, json, links
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def test_coin_url_has_ref():
    u = links.coin_url("3cJ2uPXFwXbhpuP89orEuQUcwzQtA8dF6UVneDedpump", "solana")
    assert "r=savipww" in u and u.startswith("https://fomo.family/coin?address=") and "chainId=1399811149" in u
def test_signup_and_unknown_chain():
    assert links.SIGNUP_URL == "https://fomo.family/r/savipww"
    assert links.coin_url("x", "dogechain") == links.SIGNUP_URL
def test_profile():
    assert "r=savipww" in links.profile_url("@dont_quote_siah")
def test_repo_fomo_urls():
    """Every fomo URL literal in code/web outside links.py must not exist (only links.py builds them)."""
    bad = []
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in (".venv", ".git", "pages", "logs", "__pycache__", "tests")): continue
        for f in fs:
            if f.endswith((".py", ".html", ".js", ".json")) and f != "links.py":
                s = open(os.path.join(d, f), errors="ignore").read()
                for u in re.findall(r"https?://[^\s\"']*fomo[^\s\"']*", s): bad.append((f, u))
    assert not bad, bad
    for short in ("bit.ly", "t.co/", "tinyurl"): assert short not in open(os.path.join(ROOT, "links.py")).read()
def test_rendered_pushes_carry_ref():
    import asyncio, telegram, store
    asyncio.run(telegram.push("test", [[("Buy on FOMO", links.coin_url("abc", "solana"))]], mode="PAPER"))
    m = telegram.sent[-1]; assert m["text"].startswith("PAPER · ") and "r=savipww" in m["buttons"][0][0][1]
