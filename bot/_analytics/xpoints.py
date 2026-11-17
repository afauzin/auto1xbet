import re, urllib.parse
from . import http
try:
    from . import xg as _xg
except Exception:
    _xg = None

ANALYST_URL = "https://theanalyst.com/competition/premier-league/table?view=expected"
TSPDB_TABLE = "https://www.thesportsdb.com/api/v1/json/123/lookuptable.php?l=4328"
STATZ_SLUG_RE = re.compile(r"projected,\s*(\d+)\s*pts", re.I)

def _norm(s): return re.sub(r"\s+", " ", re.sub(r"\s*\(women\)\s*", " ", s, flags=re.I)).strip().lower()
def _slug(s): return re.sub(r"[^a-z0-9]+", "-", _norm(s).replace(" fc","")).strip("-")

def _parse_analyst_text(txt, norm):
    low = txt.lower()
    idx = low.find(norm)
    if idx == -1:
        # token overlap
        for tok in norm.split():
            if tok in low:
                idx = low.find(tok)
                break
    if idx == -1: return None
    chunk = txt[idx:idx+600]
    vals = re.findall(r"[+\-]?\d+\.\d+|\d+", chunk)
    if len(vals) < 4: return None
    # seq: xPOS POS xPTS PTS ±PTS xGD GD xGF GF xGA GA PL
    try:
        xpts = float(vals[2]); pts = int(float(vals[3]))
        xgd = float(vals[5]) if len(vals) > 5 else None
        xgf = float(vals[7]) if len(vals) > 7 else None
        xga = float(vals[9]) if len(vals) > 9 else None
        return dict(source="analyst", xPTS=xpts, PTS=pts, xGD=xgd, xGF=xgf, xGA=xga, team=norm)
    except: return None

def _parse_analyst_all(txt):
    # brute: find each known line, extract xPTS via above
    out = {}
    # split by lines containing numbers
    for m in re.finditer(r"([A-Za-z &']+)\s*\(?[A-Z]{2,3}\)?\s*\n?\s*\d+\s+\d+\s+\d+\.\d+", txt):
        name = m.group(1).strip().lower()
        if len(name) < 3: continue
        chunk = txt[m.start():m.start()+600]
        vals = re.findall(r"[+\-]?\d+\.\d+|\d+", chunk)
        if len(vals) < 4: continue
        try:
            xpts = float(vals[2])
            out[_norm(name)] = dict(source="analyst", xPTS=xpts, PTS=int(float(vals[3])), xGD=float(vals[5]) if len(vals)>5 else None)
        except: continue
    return out

def get_xpoints_analyst(name, page=None):
    # ponytail: disabled in threaded enrich — Playwright page is thread-unsafe (greenlet error) + ABORTED spam
    # fallback TSPDB/statz/xG is sufficient; re-enable only with single-thread + dedicated page
    return None

def _get_tspdb(name):
    norm=_norm(name); key=f"xpoints:tspdb:{norm}"
    hit=http._cache_get(key)
    if hit and "xPTS" in hit: return hit
    http._throttle()
    data=http.fetch_json(TSPDB_TABLE)
    if not data: return None
    table=data.get("table") or []
    best=None
    for r in table:
        nm=(r.get("strTeam") or "").lower()
        if not nm: continue
        if norm==nm or norm in nm or nm in norm or (set(norm.split()) & set(nm.split())):
            try:
                pts=int(r.get("intPoints") or 0)
                best=dict(source="tspdb", xPTS=float(pts), PTS=pts, team=r.get("strTeam"))
                break
            except: continue
    if best:
        http._cache_set(key, best); return best
    return None

def _get_statz_proj(name):
    norm=_norm(name); key=f"xpoints:statz:{norm}"
    hit=http._cache_get(key)
    if hit and "xPTS" in hit: return hit
    slug=_slug(name)
    http._throttle()
    html=http.fetch_text(f"https://statsultra.com/forecasts/clubs/{slug}/")
    if not html: return None
    m=STATZ_SLUG_RE.search(html)
    if not m: return None
    try:
        pts=int(m.group(1))
        res=dict(source="statz_proj", xPTS=float(pts), PTS=pts, team=name)
        http._cache_set(key, res); return res
    except: return None

def get_xpoints(name, page=None):
    norm=_norm(name); key=f"xpoints:{norm}"
    hit=http._cache_get(key)
    if hit and hit.get("source") in ("analyst","tspdb","statz_proj","xG_poisson","none"): return hit
    r=get_xpoints_analyst(name, page=page)
    if r:
        http._cache_set(key, r); return r
    r=_get_tspdb(name)
    if r:
        http._cache_set(key, r); return r
    r=_get_statz_proj(name)
    if r:
        http._cache_set(key, r); return r
    # ponytail poisson via xG
    if _xg:
        xv=_xg.get_xg(name)
        v=xv.get("xG_per90") or xv.get("xG_avg") if xv else None
        if isinstance(v,(int,float)):
            # proxy: xPoints ~ xG*9*1.2 (placeholder)
            proxy=round(v*10.8,1)
            res=dict(source="xG_poisson", xPTS=proxy, PTS=None, team=name)
            http._cache_set(key, res); return res
    none=dict(source="none", xPTS=None)
    http._cache_set(key, none); return none

__all__=["get_xpoints","get_xpoints_analyst"]

if __name__=="__main__":
    assert _parse_analyst_text("Arsenal (ARS) 1 1 18.1 24 +5.9 +7.6 +9 14.9 14 7.2 5 9","arsenal")["xPTS"]==18.1
    print("[self-check xpoints] ok")
