import json
import re
from pathlib import Path
from . import http

BASE = "https://www.fotmob.com/api/data"
_MAP = None
_MAP_PATH = Path(__file__).parent / "fotmob_map.json"
# ponytail: skip reserve/youth team when search returns many
_JUNK_SUFFIX = (" ii", " b", " u19", " u20", " u21", " u23", " u-23", " youth", " academy", " reservoir")

def _load_map():
    global _MAP
    if _MAP is not None:
        return _MAP
    try:
        _MAP = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
        _MAP = {k.lower(): v for k, v in _MAP.items()}
    except Exception:
        _MAP = {}
    return _MAP

def lookup_fotmob_id(name):
    if not name:
        return None
    m = _load_map()
    n = name.strip().lower()
    if n in m:
        return m[n]
    for k, v in m.items():
        if n in k or k in n:
            return v
    return search_team_id(name)

def _save_map(m):
    try:
        _MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _MAP_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(m, ensure_ascii=False, indent=0), encoding="utf-8")
        tmp.replace(_MAP_PATH)
    except Exception:
        pass

def search_team_id(name):
    """FotMob search/suggest -> team id. Persist ke map (auto-expand)."""
    if not name:
        return None
    n = name.strip().lower()
    # exact-in-name cache hit
    m = _load_map()
    if n in m:
        return m[n]
    k = re.sub(r"\s+", "%20", name.strip())
    http._throttle()
    d = http.fetch_json(f"{BASE}/search/suggest?term={k}")
    cands = []
    for g in (d or []):
        for x in g.get("suggestions") or []:
            if x.get("type") == "team" and x.get("id"):
                cands.append((str(x["id"]), (x.get("name") or "").strip()))
    if not cands:
        return None
    pick = None
    for cid, cname in cands:  # prefer non-junk
        if not any(cname.lower().endswith(s) or s in f" {cname.lower()}" for s in _JUNK_SUFFIX):
            pick = (cid, cname); break
    if not pick:
        pick = cands[0]
    m[n] = pick[0]
    _save_map(m)
    global _MAP
    _MAP = {kk.lower(): vv for kk, vv in m.items()}
    return pick[0]

def _to_events(raw):
    # raw: fixtures list from FotMob -> form_h2h compatible
    out = []
    for fx in raw or []:
        st = fx.get("status") or {}
        if not st.get("finished"):
            continue
        utc = st.get("utcTime")
        if not utc:
            continue
        hs = aw = None
        sstr = st.get("scoreStr") or ""
        if sstr and "-" in sstr:
            try:
                a, b = sstr.split("-")
                hs = int(a.strip()); aw = int(b.strip())
            except Exception:
                pass
        if hs is None:
            hs = (fx.get("home") or {}).get("score")
            aw = (fx.get("away") or {}).get("score")
        if hs is None:
            hv = fx.get("homeScore"); av = fx.get("awayScore")
            if isinstance(hv, dict): hv = hv.get("current")
            if isinstance(av, dict): av = av.get("current")
            hs = hv; aw = av
        if hs is None or aw is None:
            continue
        try:
            hs = int(hs); aw = int(aw)
        except Exception:
            continue
        home = fx.get("home") or fx.get("homeTeam") or {}
        away = fx.get("away") or fx.get("awayTeam") or {}
        out.append(dict(homeTeam=dict(id=home.get("id"), name=home.get("name", "")), awayTeam=dict(id=away.get("id"), name=away.get("name", "")), homeScore=dict(current=hs), awayScore=dict(current=aw), status=dict(type="finished"), date=utc))
        if len(out) >= 5:
            break
    return out

def _resolve_tid(team_id, team_name=None):
    if team_id and str(team_id).isdigit():
        return str(team_id)
    if team_name:
        fid = lookup_fotmob_id(team_name)
        if fid:
            return str(fid)
    if team_id and isinstance(team_id, str) and ":" in team_id:
        # espn:/tspdb: id can't be used directly, try name
        if team_name:
            fid = lookup_fotmob_id(team_name)
            if fid:
                return str(fid)
    return None

def get_fotmob_events(team_name):
    tid = lookup_fotmob_id(team_name)
    if not tid:
        return None, "none"
    res = get_fotmob_fixtures(tid)
    if res.get("source") == "fotmob" and res.get("events"):
        return res["events"], "fotmob"
    if res.get("events_raw"):
        return res["events_raw"], "fotmob"
    return None, "none"

def get_fotmob_fixtures(team_id, team_name=None):
    # ponytail: search when FotMob search api found (currently only direct id like 8634=Barcelona)
    tid = _resolve_tid(team_id, team_name)
    if not tid:
        return dict(source="none", events_raw=None, events=None)
    key = f"fotmob:fixtures:{tid}"
    hit = http._cache_get(key)
    if hit and hit.get("source") == "fotmob":
        return hit
    http._throttle()
    data = http.fetch_json(f"{BASE}/teams?id={tid}&ccode3=IDN")
    if not data:
        return dict(source="none", events_raw=None)
    # fixtures.allFixtures is dict with 'fixtures' or list
    fixtures = None
    try:
        af = data.get("fixtures") or {}
        if isinstance(af, dict):
            # allFixtures wrapper
            allf = af.get("allFixtures")
            if isinstance(allf, dict):
                fixtures = allf.get("fixtures") or allf.get("all") or []
            elif isinstance(allf, list):
                fixtures = allf
            else:
                fixtures = af.get("fixtures") or []
        if not fixtures:
            ov = data.get("overview") or {}
            fixtures = (ov.get("fixtures") or {}).get("allFixtures") or ov.get("nextMatch") or []
            if isinstance(fixtures, dict):
                fixtures = [fixtures]
    except Exception:
        fixtures = None
    # fallback: data["fixtures"] may be direct list
    if not fixtures:
        # try data["fixtures"] as list
        v = data.get("fixtures")
        if isinstance(v, list):
            fixtures = v
    if not fixtures:
        # try overviewFixtures
        v = data.get("overview") or {}
        if isinstance(v, dict) and isinstance(v.get("overviewFixtures"), list):
            fixtures = v.get("overviewFixtures")
    evs = _to_events(fixtures) if fixtures else []
    if not evs:
        res = dict(source="none", events_raw=None, events=None)
        http._cache_set(key, res)
        return res
    events_raw = [{"date": e["date"], "ev": {"date": e["date"]}} for e in evs]
    table = data.get("table")
    res = dict(source="fotmob", events_raw=events_raw, events=evs, table=table)
    http._cache_set(key, res)
    return res

def _raw_fixtures(tid):
    # raw fixtures (with opponent.id + fixture.id) for H2H match lookup; not the _to_events filtered shape
    key = f"fotmob:rawfix:{tid}"
    hit = http._cache_get(key)
    if hit and hit.get("fixtures") is not None:
        return hit["fixtures"]
    http._throttle()
    data = http.fetch_json(f"{BASE}/teams?id={tid}&ccode3=IDN")
    fx = []
    if data:
        try:
            af = (data.get("fixtures") or {}).get("allFixtures") or {}
            fx = af.get("fixtures") or []
        except Exception:
            fx = []
    http._cache_set(key, {"fixtures": fx})
    return fx

def _pick_match_id(fid_self, fid_opp):
    if not fid_self or not fid_opp:
        return None
    for fx in _raw_fixtures(fid_self):
        opp = fx.get("opponent") or {}
        if str(opp.get("id")) == str(fid_opp):
            return fx.get("id")
    return None

def _h2h_from_summary(summary, our_id, header_teams):
    try:
        s0, d, s1 = int(summary[0]), int(summary[1]), int(summary[2])
    except Exception:
        return None
    t0 = (header_teams or [{}])[0]
    if str(t0.get("id")) == str(our_id):
        A, B = s0, s1
    else:
        A, B = s1, s0
    n = A + d + B
    return dict(record=dict(A=A, D=d, B=B), bias=round((A - B) / n, 2) if n else 0, n=n)

def _h2h_from_matches(matches, our_id):
    evs = []
    for m in matches or []:
        st = m.get("status") or {}
        if not (st.get("finished") or m.get("finished")):
            continue
        if st.get("cancelled"):
            continue
        hs = (m.get("home") or {}).get("score")
        aw = (m.get("away") or {}).get("score")
        if hs is None or aw is None:
            continue
        home = m.get("home") or {}
        away = m.get("away") or {}
        evs.append(dict(homeTeam=dict(id=home.get("id"), name=home.get("name", "")), awayTeam=dict(id=away.get("id"), name=away.get("name", "")), homeScore=dict(current=int(hs)), awayScore=dict(current=int(aw)), status=dict(type="finished"), date=st.get("utcTime")))
        if len(evs) >= 5:
            break
    if not evs:
        return None
    from . import form_h2h
    rec = form_h2h._h2h_record(evs, our_id)
    rec["events"] = evs
    return rec

def _match_h2h(match_id, our_id):
    if not match_id:
        return None
    http._throttle()
    d = http.fetch_json(f"{BASE}/matchDetails?matchId={match_id}")
    if not d:
        return None
    h = (d.get("content") or {}).get("h2h") or {}
    header_teams = (d.get("header") or {}).get("teams") or []
    rec = None
    if isinstance(h.get("summary"), list) and len(h["summary"]) == 3:
        rec = _h2h_from_summary(h["summary"], our_id, header_teams)
    matches = h.get("matches") or []
    if rec is None:
        rec = _h2h_from_matches(matches, our_id)
    elif not rec.get("events"):
        m = _h2h_from_matches(matches, our_id)
        if m:
            rec["events"] = m.get("events", [])
    if rec and not rec.get("events"):
        rec["events"] = []
    return rec

def get_fotmob_lineup(match_id):
    """FotMob matchDetails -> content.lineup (starters/subs/unavailable/formation). no-key."""
    if not match_id:
        return None
    key = f"fotmob:lineup:{match_id}"
    hit = http._cache_get(key)
    if hit is not None:
        return hit.get("lu")
    http._throttle()
    d = http.fetch_json(f"{BASE}/matchDetails?matchId={match_id}")
    lu = ((d or {}).get("content") or {}).get("lineup") if d else None
    if not lu:
        http._cache_set(key, {"lu": None}); return None
    def _side(t):
        t = t or {}
        return dict(
            team=t.get("name"), formation=t.get("formation"),
            starters=len(t.get("starters") or []),
            subs=len(t.get("subs") or []),
            unavailable=[dict(name=u.get("name"), type=(u.get("unavailability") or {}).get("type"),
                              expected_return=(u.get("unavailability") or {}).get("expectedReturn"))
                         for u in (t.get("unavailable") or [])],
        )
    val = dict(source="fotmob", type=lu.get("lineupType"), home=_side(lu.get("homeTeam")), away=_side(lu.get("awayTeam")))
    http._cache_set(key, {"lu": val})
    return val

def get_fotmob_h2h(name1, name2):
    fid1 = lookup_fotmob_id(name1)
    fid2 = lookup_fotmob_id(name2)
    if not fid1 or not fid2:
        return None
    a, b = sorted([str(fid1), str(fid2)])
    key = f"fotmob:h2h:{a}:{b}"
    hit = http._cache_get(key)
    if hit and hit.get("record") is not None:
        return hit
    match_id = _pick_match_id(fid1, fid2)
    rec = None
    if match_id:
        rec = _match_h2h(match_id, fid1)
    if not rec:
        match_id = _pick_match_id(fid2, fid1)
        if match_id:
            rec = _match_h2h(match_id, fid1)
    if not rec or not rec.get("n"):
        return None
    rec["source"] = "fotmob"
    http._cache_set(key, rec)
    return rec

def get_lineup_by_names(name1, name2):
    """Resolve fotmob ids by name -> pick their match -> lineup. None bila tak ketemu/ belum ada."""
    fid1 = lookup_fotmob_id(name1)
    fid2 = lookup_fotmob_id(name2)
    if not fid1 or not fid2:
        return None
    mid = _pick_match_id(fid1, fid2) or _pick_match_id(fid2, fid1)
    if not mid:
        return None
    return get_fotmob_lineup(mid)

__all__ = ["get_fotmob_fixtures", "get_fotmob_events", "lookup_fotmob_id", "search_team_id", "get_fotmob_h2h", "get_fotmob_lineup", "get_lineup_by_names"]
