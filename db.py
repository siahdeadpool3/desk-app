import sqlite3, os
PATH = os.environ.get("DESK_DB") or os.path.join(os.path.dirname(__file__), "desk.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS coins(mint TEXT PRIMARY KEY,name TEXT,symbol TEXT,pool TEXT,creator TEXT,
  creator_balance REAL,migrated_at TEXT,signature TEXT,holders INTEGER,first_seen TEXT,h24_change REAL);
CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY,mint TEXT,verdict TEXT,reason TEXT,liq REAL,top10 REAL,h1 REAL,age_min INTEGER,ts TEXT,json TEXT);
CREATE TABLE IF NOT EXISTS audits(id INTEGER PRIMARY KEY,mint TEXT,passed INTEGER,layers_checked INTEGER,reason TEXT,ts TEXT,json TEXT);
CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY,mint TEXT,score INTEGER,passed INTEGER,failed TEXT,model TEXT,input_tokens INTEGER,ts TEXT,json TEXT);
CREATE TABLE IF NOT EXISTS positions(id INTEGER PRIMARY KEY,mint TEXT,name TEXT,mode TEXT,entry_price REAL,size_usd REAL,
  peak REAL,stop_pct REAL,trail_active INTEGER DEFAULT 0,opened_at TEXT,status TEXT,exit_price REAL,exit_reason TEXT,
  pnl_usd REAL,pct REAL,fees_usd REAL,closed_at TEXT,link TEXT);
CREATE TABLE IF NOT EXISTS prices(mint TEXT,ts TEXT,price REAL,volume_m5 REAL);
CREATE INDEX IF NOT EXISTS prices_mint_ts ON prices(mint,ts);
CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY,ts TEXT,kind TEXT,title TEXT,agent_line TEXT,right TEXT,mint TEXT,mode TEXT,link TEXT);
CREATE TABLE IF NOT EXISTS skips(id INTEGER PRIMARY KEY,mint TEXT,agent TEXT,reason TEXT,ts TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS change_log(id INTEGER PRIMARY KEY,ts TEXT,key TEXT,old TEXT,new TEXT,source TEXT);
CREATE TABLE IF NOT EXISTS heartbeats(agent TEXT PRIMARY KEY,ts TEXT,paused INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS nights(id INTEGER PRIMARY KEY,mode TEXT,started TEXT,ended TEXT,start_balance REAL,end_balance REAL);
CREATE TABLE IF NOT EXISTS ws_events(id INTEGER PRIMARY KEY,ts TEXT,kind TEXT);
CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY,ts TEXT,model TEXT,input_tokens INTEGER,cost_usd REAL);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT);
"""
def conn(path=PATH):
    c = sqlite3.connect(path, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL")
    c.executescript(SCHEMA)
    return c
