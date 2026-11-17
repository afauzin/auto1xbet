from . import http
import re

ESPN_SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{tid}/schedule?xhr=1"
TSPDB_LAST = "https://www.thesportsdb.com/api/v1/json/123/eventslast.php"
SOFASCORE_BASE = "https://api.sofascore.com/api/v1"

def _tid_num(tid):
    if tid is None: return None
    if isinstance(tid, int): return tid
    if isinstance(tid, str) and tid.startswith("espn:"):
        try: return int(tid.split(":")[1])
        except: return None
    if isinstance(tid, str) and tid.startswith("tspdb:"): return tid
    try: return int(tid)
    except: return tid

def _score_of(ev, side):
    sc = ev.get(f"{side}Score") or {}
    if isinstance(sc, dict):
        for k in ("current","display","normaltime","score"):
            v = sc.get(k)
            if isinstance(v, (int,float)): return int(v)
        if "current" in sc and isinstance(sc["current"], dict):
            try: return int(sc["current"].get("value",0))
            except: pass
    if isinstance(sc, (int,float)): return int(sc)
    return None

def _espn_to_events(data, limit=5):
    evs=[]
    for e in (data.get("events") or [])[::-1]:
        comp=(e.get("competitions") or [{}])[0] if e.get("competitions") else {}
        status=comp.get("status") or {}
        typ=status.get("type") or {}
        if not (typ.get("completed") or typ.get("state")=="post"): continue
        comps=comp.get("competitors") or []
        if len(comps)<2: continue
        home=away=None
        for c in comps:
            if c.get("homeAway")=="home": home=c
            elif c.get("homeAway")=="away": away=c
        if not home or not away: continue
        hs=home.get("score") or {}; aw=away.get("score") or {}
        hv=hs.get("value") if isinstance(hs, dict) else hs
        av=aw.get("value") if isinstance(aw, dict) else aw
        if hv is None or av is None: continue
        try: hv=int(float(hv)); av=int(float(av))
        except: continue
        evs.append(dict(homeTeam=dict(id=int(home["team"]["id"]) if str(home["team"].get("id","")).isdigit() else home["team"]["id"], name=home["team"].get("displayName") or home["team"].get("name","")), awayTeam=dict(id=int(away["team"]["id"]) if str(away["team"].get("id","")).isdigit() else away["team"]["id"], name=away["team"].get("displayName") or away["team"].get("name","")), homeScore=dict(current=hv), awayScore=dict(current=av), status=dict(type="finished"), date=e.get("date")))
        if len(evs)>=limit: break
    return evs

def _tspdb_to_events(data, limit=5):
    evs=[]
    for r in (data.get("results") or data.get("events") or [])[:limit]:
        hs=r.get("intHomeScore"); aw=r.get("intAwayScore")
        if hs is None or aw is None: continue
        try: hs=int(hs); aw=int(aw)
        except: continue
        evs.append(dict(homeTeam=dict(id=r.get("idHomeTeam") or r.get("strHomeTeam"), name=r.get("strHomeTeam","")), awayTeam=dict(id=r.get("idAwayTeam") or r.get("strAwayTeam"), name=r.get("strAwayTeam","")), homeScore=dict(current=hs), awayScore=dict(current=aw), status=dict(type="finished"), date=r.get("dateEvent") or r.get("strTimestamp")))
    return evs

def get_team_last_events(team_id):
    key=f"events:{team_id}"
    hit=http._cache_get(key)
    if hit and hit.get("events") is not None: return hit["events"], "cache"
    if isinstance(team_id, str) and team_id.startswith("espn:"):
        parts=team_id.split(":"); tid=parts[1] if len(parts)>1 else ""; league=parts[2] if len(parts)>2 and parts[2] else "eng.1"
        if not league or "." not in league: league="eng.1"
        for lg in [league,"eng.1","esp.1","ger.1","ita.1","fra.1","aus.1","ned.1","por.1","uefa.champions","uefa.europa"]:
            http._throttle()
            data=http.fetch_json(ESPN_SCHEDULE.format(league=lg, tid=tid))
            if data and data.get("events"):
                evs=_espn_to_events(data, limit=5)
                if evs:
                    http._cache_set(key, {"events": evs, "id": team_id})
                    return evs, "espn"
            if lg==league: continue
        return None, "none"
    if isinstance(team_id, str) and team_id.startswith("tspdb:"):
        num=team_id.split(":")[1] if ":" in team_id else ""
        http._throttle()
        data=http.fetch_json(f"{TSPDB_LAST}?id={num}")
        if data:
            evs=_tspdb_to_events(data, limit=5)
            if evs:
                http._cache_set(key, {"events": evs, "id": team_id})
                return evs, "tspdb"
            http._throttle()
            data2=http.fetch_json(f"https://www.thesportsdb.com/api/v1/json/123/eventsnext.php?id={num}")
            if data2:
                evs=_tspdb_to_events(data2, limit=5)
                if evs:
                    http._cache_set(key, {"events": evs, "id": team_id})
                    return evs, "tspdb"
        return None, "none"
    http._throttle()
    data=http.fetch_json(f"{SOFASCORE_BASE}/team/{team_id}/events/last/0")
    if not data: return None, "none"
    events=data.get("events") or data.get("data") or []
    if isinstance(events, list) and events: http._cache_set(key, {"events": events, "id": team_id})
    return events, "sofascore"

def parse_form(events, team_id=None, team_name=None, limit=5):
    if not events: return None
    used=[]
    for ev in events:
        typ=(ev.get("status") or {}).get("type") if isinstance(ev.get("status"), dict) else str(ev.get("status"))
        if typ and typ not in ("finished","ft","ended","Fin","FT"):
            if _score_of(ev,"home") is None: continue
        hs=_score_of(ev,"home"); aw=_score_of(ev,"away")
        if hs is None or aw is None: continue
        ht=ev.get("homeTeam") or {}; at=ev.get("awayTeam") or {}
        nid=_tid_num(team_id); ht_id=ht.get("id"); at_id=at.get("id")
        is_home=None
        if team_id is not None and (ht_id==nid or at_id==nid or ht_id==team_id or at_id==team_id or str(ht_id)==str(nid) or str(at_id)==str(nid)):
            is_home=(str(ht_id)==str(nid) or ht_id==nid)
        elif team_name:
            tn=team_name.lower(); htl=(ht.get("name") or "").lower(); atl=(at.get("name") or "").lower()
            if tn in htl or htl in tn: is_home=True
            elif tn in atl or atl in tn: is_home=False
            else: continue
        else: continue
        gf=hs if is_home else aw; ga=aw if is_home else hs
        res="W" if gf>ga else "D" if gf==ga else "L"; pts=3 if res=="W" else 1 if res=="D" else 0
        used.append(dict(is_home=is_home, gf=gf, ga=ga, res=res, pts=pts, hs=hs, aw=aw, ev=ev))
        if len(used)>=limit: break
    if not used: return None
    W=sum(1 for u in used if u["res"]=="W"); D=sum(1 for u in used if u["res"]=="D"); L=sum(1 for u in used if u["res"]=="L")
    GF=sum(u["gf"] for u in used); GA=sum(u["ga"] for u in used)
    pts_list=[u["pts"] for u in used]
    form_score=round(sum((0.9**i)*p for i,p in enumerate(pts_list)),2)
    return dict(W=W,D=D,L=L,GF=GF,GA=GA,pts=pts_list,form_score=form_score,n=len(used),events_raw=used)

def _h2h_record(events, team_id):
    nid=_tid_num(team_id); A=D=B=n=0
    for ev in events[:5]:
        hs=_score_of(ev,"home"); aw=_score_of(ev,"away")
        if hs is None or aw is None: continue
        if hs==aw: D+=1
        else:
            ht=ev.get("homeTeam") or {}; at=ev.get("awayTeam") or {}
            is_a_home=str(ht.get("id"))==str(nid) or ht.get("id")==nid
            is_a_away=str(at.get("id"))==str(nid) or at.get("id")==nid
            if not (is_a_home or is_a_away): continue
            winner_home=hs>aw
            if is_a_home:
                if winner_home: A+=1
                else: B+=1
            elif is_a_away:
                if not winner_home: A+=1
                else: B+=1
        n+=1
    return dict(record=dict(A=A,D=D,B=B), bias=round((A-B)/n,2) if n else 0, n=n)

def _derive_h2h(ev1, ev2, tid1, tid2, name1, name2):
    seen=set(); out=[]
    for ev in (ev1 or [])+(ev2 or []):
        ht=(ev.get("homeTeam") or {}).get("name",""); at=(ev.get("awayTeam") or {}).get("name","")
        n1=(name1 or "").lower(); n2=(name2 or "").lower()
        has1=n1 in ht.lower() or n1 in at.lower() or str((ev.get("homeTeam") or {}).get("id"))==str(_tid_num(tid1)) or str((ev.get("awayTeam") or {}).get("id"))==str(_tid_num(tid1))
        has2=n2 in ht.lower() or n2 in at.lower() or str((ev.get("homeTeam") or {}).get("id"))==str(_tid_num(tid2)) or str((ev.get("awayTeam") or {}).get("id"))==str(_tid_num(tid2))
        if has1 and has2:
            key=f"{ht}|{at}|{ev.get('homeScore',{}).get('current')}-{ev.get('awayScore',{}).get('current')}"
            if key not in seen:
                seen.add(key); out.append(ev)
                if len(out)>=5: break
    if out:
        rec=_h2h_record(out, tid1); rec["events"]=out[:5]; rec["source"]="derived"; return rec
    return None

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

def _espn_split_id(tid):
    # "espn:3307:ger.1" -> ("3307","ger.1"); else (None,None)
    if isinstance(tid, str) and tid.startswith("espn:"):
        parts = tid.split(":")
        return parts[1], (parts[2] if len(parts) > 2 and parts[2] else None)
    return None, None

def _espn_schedule_events(league, tid):
    if not league: return []
    http._throttle()
    d = http.fetch_json(f"{ESPN_SITE}/{league}/teams/{tid}/schedule")
    return (d or {}).get("events") or []

def _espn_find_meeting(league, id_a, id_b):
    for e in _espn_schedule_events(league, id_a):
        comps = (e.get("competitions") or [{}])[0]
        ids = [str((c.get("team") or {}).get("id")) for c in comps.get("competitors") or []]
        if str(id_a) in ids and str(id_b) in ids:
            return e.get("id")
    return None

def _espn_h2h_from_events(h2h_events, id1):
    """hitung W/D/L untuk id1 dari daftar pertemuan ESPN (robust, tak tergantung urutan judul)."""
    A = D = B = n = 0
    for e in h2h_events or []:
        cs = e.get("competitors") or []
        if len(cs) < 2: continue
        mine = next((c for c in cs if str((c.get("team") or {}).get("id")) == str(id1)), None)
        if not mine: continue
        if mine.get("winner"): A += 1
        elif any(c.get("winner") for c in cs): B += 1
        else: D += 1
        n += 1
        if n >= 5: break
    return A, D, B, n

def get_espn_h2h(name1, name2):
    """H2H gratis no-key via ESPN seasonseries. Butuh kedua tim di liga ESPN sama."""
    from .resolve import search_team_id
    t1 = search_team_id(name1); t2 = search_team_id(name2)
    id1, lg1 = _espn_split_id(t1[0]); id2, lg2 = _espn_split_id(t2[0])
    if not id1 or not id2 or not lg1:
        return None
    key = f"espnh2h2:{min(id1,id2)}:{max(id1,id2)}"  # v2: {"rec": rec|None}
    hit = http._cache_get(key)
    if hit is not None:
        return hit.get("rec")  # None bila negatif ter-cache (kontrak: always None|rec)
    eid = _espn_find_meeting(lg1, id1, id2) or (lg2 and _espn_find_meeting(lg2, id2, id1))
    if not eid:
        http._cache_set(key, {"rec": None})
        return None
    http._throttle()
    d = http.fetch_json(f"{ESPN_SITE}/{lg1}/summary?event={eid}")
    ss = (d or {}).get("seasonseries") or []
    h = next((s for s in ss if s.get("type") == "head-to-head"), None)
    if not h:
        http._cache_set(key, {"rec": None})
        return None
    a, dd, b, n = _espn_h2h_from_events(h.get("events"), id1)
    if n == 0:
        # fallback: parse "TeamX leads series 3-1-1" + orientasi via title-left
        try:
            a, dd, b = [int(x) for x in (h.get("seriesScore") or "").split("-")]
            n = a + dd + b
            left = (h.get("title") or "").split(" vs.")[0].strip().lower()
            if left and not (left in name1.lower() or name1.lower() in left):
                a, b = b, a
        except Exception:
            http._cache_set(key, {"rec": None}); return None
    rec = dict(record=dict(A=a, D=dd, B=b), bias=round((a - b) / n, 2) if n else 0, n=n, events=[], source="espn")
    http._cache_set(key, {"rec": rec})
    return rec

def get_h2h(team_id, opp_id, gameId_fallback=None, ev1=None, ev2=None, name1=None, name2=None):
    if team_id and opp_id and not (isinstance(team_id,str) and team_id.startswith(("espn:","tspdb:"))):
        for path in [f"/team/{team_id}/events/h2h/{opp_id}", f"/team/{team_id}/head-to-head/{opp_id}"]:
            http._throttle()
            data=http.fetch_json(SOFASCORE_BASE+path)
            if not data: continue
            events=data.get("events") or data.get("data") or data.get("h2h") or []
            if isinstance(events, dict): events=events.get("events") or []
            if isinstance(events, list) and events:
                rec=_h2h_record(events, team_id); rec["events"]=events[:5]; rec["source"]="sofascore"; return rec
    if ev1 is not None or ev2 is not None:
        d=_derive_h2h(ev1,ev2,team_id,opp_id,name1,name2)
        if d: return d
    if gameId_fallback:
        http._throttle()
        data=http.fetch_json(f"https://1-x-bet-india.com/service-api/line/statistic/getGameStat?id={gameId_fallback}&lng=en")
        if data:
            h2h=data.get("headToHead") or data.get("h2h") or data.get("results") or []
            if isinstance(h2h, list) and h2h:
                return dict(record={"A":0,"D":0,"B":0}, bias=0, n=len(h2h[:5]), events=h2h[:5], source="1xbet")
    if name1 and name2:
        try:
            r=get_espn_h2h(name1, name2)
            if r and r.get("n"): return r
        except Exception: pass
    if name1 and name2:
        try:
            from .fotmob import get_fotmob_h2h
            r=get_fotmob_h2h(name1, name2)
            if r and r.get("n"): r["source"]="fotmob"; return r
        except Exception: pass
    return dict(record={"A":0,"D":0,"B":0}, bias=0, n=0, events=[], source="none")

__all__=["get_team_last_events","parse_form","get_h2h","get_espn_h2h"]
