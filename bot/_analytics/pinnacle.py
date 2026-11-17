import os, urllib.parse
from pathlib import Path
from .http import fetch_json, _cache_get, _cache_set

STEAM_BASE = "https://www.steamwatch.io"
ODDS_BASE = "https://api.oddspapi.io"

def _load_env():
    base = Path(__file__).resolve()
    cands = [base.parents[2] / ".env", base.parents[3] / ".env", Path.cwd() / "1xbet" / ".env", Path.cwd() / ".env"]
    seen = set()
    for p in cands:
        if p in seen: continue
        seen.add(p)
        try:
            if not p.exists(): continue
            for line in p.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        except: pass
_load_env()

ODDSPAPI_KEY = os.environ.get("ODDSPAPI_KEY", "")

def _devig(*odds):
    inv = [1 / float(o) for o in odds if o]
    s = sum(inv)
    return [x / s for x in inv] if s else []

def _norm(s): return (s or "").strip().lower()

def _tok(s): return set((s or "").strip().lower().split())

def _side_match(q, h):
    if not q or not h: return False
    if q == h: return True
    qt, ht = _tok(q), _tok(h)
    if len(qt) == 1 or len(ht) == 1:
        return q == h
    # exact subset OR one-word diff via lowercased char containment for abbreviations (manchester ~ man)
    small, big = (qt, ht) if len(qt) <= len(ht) else (ht, qt)
    if small.issubset(big): return True
    # allow 'man city' ~ 'manchester city' via token prefix containment
    def _prefix_match(a, b):
        return any(at.startswith(bt) or bt.startswith(at) for at in a for bt in b)
    # only allow prefix fuzzy when both multi-token and overlap >=1
    if len(small & big) >= 1 and _prefix_match(small - big, big - small):
        return True
    return False

def _steam_match(home, away, m):
    hm, am = _norm(m.get("home_team")), _norm(m.get("away_team"))
    qh, qa = _norm(home), _norm(away)
    return _side_match(qh, hm) and _side_match(qa, am)

def get_steamwatch_close(home, away, league=None):
    """gratis stdlib tanpa key: 1640 closes, true_prob via devig. stdlib 200 proven 2026-11-07."""
    ck = _cache_get("steamwatch:grouped500")
    data = ck["data"] if ck else None
    if not data:
        data = fetch_json(f"{STEAM_BASE}/api/closing-lines/grouped?limit=500")
        if not data: return dict(source="steamwatch", odds=None, reason="fetch fail")
        _cache_set("steamwatch:grouped500", {"data": data})
    matches = data.get("matches", []) if isinstance(data, dict) else []
    cand = [m for m in matches if _steam_match(home, away, m)]
    if league:
        flt = [m for m in cand if _norm(m.get("league")) == _norm(league)]
        if flt: cand = flt
    if not cand: return dict(source="steamwatch", odds=None, reason="no match")
    m = cand[0]
    h2h = m.get("h2h") or {}
    ah = m.get("asian_handicap") or {}
    tot = m.get("totals") or {}
    ch, cd, ca = h2h.get("close_home"), h2h.get("close_draw"), h2h.get("close_away")
    true = _devig(ch, cd, ca) if ch and cd and ca else []
    return dict(source="steamwatch", match_id=m.get("match_id"), league=m.get("league"),
                kickoff=m.get("kickoff_time"), captured_at=h2h.get("captured_at"),
                minutes_before_kickoff=h2h.get("minutes_before_kickoff"),
                close_home=ch, close_draw=cd, close_away=ca,
                true_home=true[0] if len(true)==3 else None,
                true_draw=true[1] if len(true)==3 else None,
                true_away=true[2] if len(true)==3 else None,
                asian_handicap=ah, totals=tot, raw=m)

def get_steamwatch_match_detail(match_id):
    merged = {}
    for suf in ("", "/totals", "/spreads", "/market-context"):
        j = fetch_json(f"{STEAM_BASE}/api/matches/{match_id}{suf}")
        if not j: continue
        if suf == "":
            merged.update(j if isinstance(j, dict) else {"base": j})
        else:
            key = suf.lstrip("/")
            merged[key] = j
    return merged if merged else None

def get_oddspapi_account(api_key=None):
    k = (api_key or ODDSPAPI_KEY or "").strip()
    return fetch_json(f"{ODDS_BASE}/v4/account?apiKey={k}")

def get_oddspapi_hist_close(fixture_id, api_key=None):
    """closing via last price in historical-odds market 101. max 3 bookmakers."""
    k = (api_key or ODDSPAPI_KEY or "").strip()
    j = fetch_json(f"{ODDS_BASE}/v4/historical-odds?fixtureId={urllib.parse.quote(fixture_id)}&bookmakers=pinnacle&apiKey={k}")
    if not j: return dict(source="oddspapi", odds=None, reason="fetch fail")
    bks = j.get("bookmakers") or {}
    pin = bks.get("pinnacle") or {}
    mk = (pin.get("markets") or {}).get("101") or {}
    outs = mk.get("outcomes") or {}
    def last_price(out_id):
        arr = ((outs.get(out_id) or {}).get("players") or {}).get("0") or []
        return float(arr[-1]["price"]) if arr else None
    ch, cd, ca = last_price("101"), last_price("102"), last_price("103")
    true = _devig(ch, cd, ca) if ch and cd and ca else []
    return dict(source="oddspapi", fixtureId=fixture_id, close_home=ch, close_draw=cd, close_away=ca,
                true_home=true[0] if len(true)==3 else None, true_draw=true[1] if len(true)==3 else None,
                true_away=true[2] if len(true)==3 else None, raw=j)

def get_pinnacle_odds(event=None, api_key=None):
    """dispatch: oddspapi jika ada fixtureId, lalu steamwatch."""
    if not event: return dict(source="none", odds=None)
    if isinstance(event, dict) and event.get("fixtureId"):
        r = get_oddspapi_hist_close(event["fixtureId"], api_key)
        if r.get("close_home"): return r
    home = (event.get("home") or event.get("home_team") or "") if isinstance(event, dict) else str(event)
    away = (event.get("away") or event.get("away_team") or "") if isinstance(event, dict) else ""
    league = (event.get("league") or "") if isinstance(event, dict) else ""
    if home and away:
        r = get_steamwatch_close(home, away, league)
        if r.get("close_home"): return r
        if isinstance(event, dict) and event.get("fixtureId"):
            return get_oddspapi_hist_close(event["fixtureId"], api_key)
    return dict(source="none", odds=None)

__all__ = ["get_steamwatch_close","get_steamwatch_match_detail","get_oddspapi_hist_close","get_oddspapi_account","get_pinnacle_odds","STEAM_BASE","ODDS_BASE"]
