"""Desk process. Plan B publisher: every 15s copy web/ + data JSON into an orphan gh-pages
commit under /d/{DATA_PATH}/ and force-push, only when content changed. DATA_PATH lives only
in .secrets and the gh-pages tree (never in main)."""
import os, json, shutil, subprocess, hashlib, time, datetime, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); PAGES = os.path.join(ROOT, "pages")
REMOTE = "https://github.com/siahdeadpool3/desk-app.git"
def secrets():
    return dict(l.strip().split("=",1) for l in open(os.path.join(ROOT,".secrets")) if "=" in l)
def git(*a): return subprocess.run(["git","-C",PAGES,*a],check=True,capture_output=True,text=True).stdout
def init_pages():
    if not os.path.isdir(os.path.join(PAGES,".git")):
        os.makedirs(PAGES, exist_ok=True); subprocess.run(["git","init","-q","-b","gh-pages",PAGES],check=True)
        git("remote","add","origin",REMOTE); git("config","user.name","desk"); git("config","user.email","desk@local")
_last = None
def publish(data: dict):
    """data: {filename: obj}. Returns True if pushed."""
    global _last
    init_pages(); dp = secrets()["DATA_PATH"]
    for f in os.listdir(PAGES):
        if f != ".git": p=os.path.join(PAGES,f); shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    shutil.copytree(os.path.join(ROOT,"web"), PAGES, dirs_exist_ok=True)
    dd = os.path.join(PAGES,"d",dp); os.makedirs(dd)   # no index in /d/ -> 404
    for name,obj in data.items(): open(os.path.join(dd,name),"w").write(json.dumps(obj,separators=(",",":")))
    h = hashlib.sha256(subprocess.run(["bash","-c",f"cd {PAGES} && find . -path ./.git -prune -o -type f -print0 | sort -z | xargs -0 sha256sum"],capture_output=True,text=True).stdout.encode()).hexdigest()
    if h == _last: return False
    git("add","-A")
    # single orphan commit each time: keeps the branch tiny, history never accumulates
    tree = git("write-tree").strip(); c = git("commit-tree",tree,"-m","publish").strip()
    git("update-ref","refs/heads/gh-pages",c); git("push","-qf","origin","gh-pages")
    _last = h; return True
def state_snapshot(balance, mode="PAPER", note=None):
    return {"state.json":{"mode":mode,"balance":round(balance,2),"ts":datetime.datetime.now(datetime.timezone.utc).isoformat(),"note":note}}
if __name__ == "__main__":
    bal = 200.0
    while True:
        try: publish(state_snapshot(bal)); 
        except Exception as e: print("publish failed", e, file=sys.stderr, flush=True)
        time.sleep(15)
