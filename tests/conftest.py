import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DESK_DB"] = os.path.join(tempfile.mkdtemp(), "t.db"); os.environ["DESK_TG_DRY"] = "1"
