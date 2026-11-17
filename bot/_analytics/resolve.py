import re, urllib.parse
from . import http

SOFASCORE_BASE = "https://api.sofascore.com/api/v1"
ESPN_SEARCH = "https://site.web.api.espn.com/apis/common/v3/search"
TSPDB_SEARCH = "https://www.thesportsdb.com/api/v1/json/123/searchteams.php"

def _normalize(name):
    s = re.sub(r"\s*\(women\)\s*", " ", name, flags=re.I)
    return re.sub(r"\s+", " ", s).strip().lower()

def _sofascore_search(norm, queries):
    for q in queries:
        data = http.fetch_json(f"{SOFASCORE_BASE}/search/all?q={urllib.parse.quote(q)}")
        if not data: continue
        results = data.get("results") or data.get("data") or []
        best = None; best_score = -1
        for r in results:
            typ = (r.get("type") or r.get("entityType") or "").lower()
            entity = r.get("entity") or r
            if typ != "team":
                if entity.get("type") == "team":
                    entity = entity.get("entity") or entity
                    typ = "team"
                else: continue
            en = entity.get("name") or ""; eid = entity.get("id")
            if not eid or not en: continue
            el = en.lower(); score = -1
            if norm == el: score = 100
            elif norm in el or el in norm: score = 80
            else:
                ov = len(set(norm.split()) & set(el.split()))
                if ov: score = ov*12
                else: continue
            if score > best_score: best_score = score; best = (eid, en)
        if best: return best[0], best[1], "sofascore"
    return None

def _espn_search(norm, queries):
    for q in queries:
        http._throttle()
        data = http.fetch_json(f"{ESPN_SEARCH}?query={urllib.parse.quote(q)}")
        if not data: continue
        best = None; best_score = -1
        for it in data.get("items") or []:
            if (it.get("type") or "").lower() != "team": continue
            if (it.get("sport") or "").lower() != "soccer": continue
            en = it.get("displayName") or it.get("name") or ""
            eid = it.get("id"); league = it.get("league") or ""
            if not eid or not en: continue
            el = en.lower(); score = -1
            if norm == el: score = 100
            elif norm in el or el in norm: score = 80
            else:
                ov = len(set(norm.split()) & set(el.split()))
                if ov: score = ov*12
                else: continue
            if score > best_score: best_score = score; best = (f"espn:{eid}:{league}", en, league)
        if best: return best
    return None

def _tspdb_search(norm, queries):
    for q in queries:
        http._throttle()
        data = http.fetch_json(f"{TSPDB_SEARCH}?t={urllib.parse.quote(q)}")
        if not data: continue
        teams = data.get("teams") or []
        if not isinstance(teams, list): continue
        best = None; best_score = -1
        for t in teams:
            en = t.get("strTeam") or ""; eid = t.get("idTeam")
            if not eid or not en: continue
            el = en.lower(); score = -1
            if norm == el: score = 100
            elif norm in el or el in norm: score = 80
            else:
                ov = len(set(norm.split()) & set(el.split()))
                if ov: score = ov*12
                else: continue
            if score > best_score: best_score = score; best = (f"tspdb:{eid}", en)
        if best: return best[0], best[1], "tspdb"
    return None

def search_team_id(name):
    norm = _normalize(name)
    key = f"search:{norm}"
    hit = http._cache_get(key)
    if hit and hit.get("id"):
        return hit["id"], hit.get("name", name), "cache"
    queries = []
    for q in [name, norm, name.split(" (")[0].strip(), norm.replace(" fc","").strip()]:
        if q and q not in queries: queries.append(q)
    http._throttle()
    s = _sofascore_search(norm, queries)
    if s:
        http._cache_set(key, {"id": s[0], "name": s[1]})
        return s[0], s[1], s[2]
    e = _espn_search(norm, queries)
    if e:
        http._cache_set(key, {"id": e[0], "name": e[1], "league": e[2]})
        return e[0], e[1], "espn"
    t = _tspdb_search(norm, queries)
    if t:
        http._cache_set(key, {"id": t[0], "name": t[1]})
        return t[0], t[1], t[2]
    return None, None, "none"

__all__ = ["search_team_id", "_normalize"]
