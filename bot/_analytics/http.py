import json, time, urllib.request, urllib.error, ssl, threading
from pathlib import Path

_CTX = ssl._create_unverified_context()
_CACHE_LOCK = threading.Lock()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CACHE_PATH = Path(__file__).parent.parent / "data" / "analytics_cache.json"
OUT_PATH = Path(__file__).parent.parent / "data" / "analytics.json"
TTL = 6 * 3600
_last_req = 0
_THROTTLE_LOCK = threading.Lock()

def _throttle():
    global _last_req
    gap = 0.3
    with _THROTTLE_LOCK:
        now = time.time()
        w = gap - (now - _last_req)
        if w > 0:
            time.sleep(w)
        _last_req = time.time()

def _fetch(url, accept, timeout=10):
    hdr = {"User-Agent": UA, "Accept": accept}
    req = urllib.request.Request(url, headers=hdr)
    for attempt in range(2):
        for ctx in (None, _CTX):
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                    return r.read().decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                if e.code in (403, 429, 500, 502, 503) and attempt == 0:
                    time.sleep(1)
                    break
                return None
            except Exception as err:
                if "CERTIFICATE_VERIFY_FAILED" in str(err) or "SSL" in type(err).__name__:
                    continue
                if attempt == 0:
                    time.sleep(1)
                    break
                return None
        if attempt == 0:
            time.sleep(0.3)
    return None

def fetch_json(url, timeout=10):
    b = _fetch(url, "application/json, text/plain, */*", timeout)
    if not b or not b.strip():
        return None
    try:
        return json.loads(b)
    except: return None

def fetch_text(url, timeout=10):
    return _fetch(url, "text/html,application/xhtml+xml,*/*", timeout)

def fetch_csv(url, timeout=10):
    return _fetch(url, "text/csv,text/plain,*/*", timeout)

def _load_cache():
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except: pass
    return {}

def _save_cache(d):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CACHE_PATH)

def _cache_get(key):
    with _CACHE_LOCK:
        c = _load_cache()
    v = c.get(key)
    if not v: return None
    if time.time() - v.get("ts", 0) > TTL:
        return None
    return v

def _cache_set(key, val):
    with _CACHE_LOCK:
        c = _load_cache()
        c[key] = {**val, "ts": time.time()}
        _save_cache(c)

__all__ = ["UA","CACHE_PATH","OUT_PATH","TTL","_throttle","fetch_json","fetch_text","fetch_csv","_cache_get","_cache_set","_load_cache","_save_cache"]
