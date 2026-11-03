"""In-process bus between agents + event feed for the app (SSE-equivalent, published as events.json)."""
import asyncio, collections, datetime
scanner_out = None; auditor = None; analyst = None; executor = None
events = collections.deque(maxlen=300)
def init():
    global auditor, analyst, executor
    auditor, analyst, executor = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
def now(): return datetime.datetime.now(datetime.timezone.utc)
def iso(): return now().isoformat().replace("+00:00", "Z")
def emit(kind, data): events.append({"event": kind, "ts": iso(), "data": data})
