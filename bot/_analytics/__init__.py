import json, time, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from . import http, resolve, form_h2h, xg, xpoints, elo

def _xg_val(d):
    if not d: return None
    if "xG_per90" in d: return d["xG_per90"]
    if "xG_avg" in d: return d["xG_avg"]
    v=d.get("xG")
    return v if isinstance(v,(int,float)) else None

def _xpts_val(d):
    if not d: return None
    v=d.get("xPTS")
    return v if isinstance(v,(int,float)) else None

def _parse_game_date(raw):
    for k in ("startTs","startTimestamp","startTime","startDate","date","kickoff","time","beginTime"):
        v=raw.get(k)
        if v is None: continue
        if isinstance(v,(int,float)) and v>1e9:
            try:
                tv=float(v);  tv/=1000 if tv>1e12 else 1
                return datetime.fromtimestamp(tv, tz=timezone.utc)
            except: pass
        if isinstance(v,str):
            s=v.strip()
            if s.isdigit() and int(s)>1e9:
                try:
                    tv=int(s); tv/=1000 if tv>1e12 else 1
                    return datetime.fromtimestamp(tv, tz=timezone.utc)
                except: pass
            for fmt in ("%Y-%m-%dT%H:%M:%SZ","%Y-%m-%dT%H:%M:%S%z","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
                try:
                    if "T" in fmt and "T" not in s: continue
                    if "%H" in fmt and len(s) < 13: continue
                    return datetime.strptime(s[:19] if "T" in s else s[:10], fmt)
                except: continue
            try: return datetime.fromisoformat(s.replace("Z","+00:00"))
            except: pass
    return None

def _parse_event_date(ev_wrap):
    ev=ev_wrap.get("ev") if isinstance(ev_wrap, dict) and "ev" in ev_wrap else ev_wrap
    if not isinstance(ev, dict): return None
    for k in ("date","startTimestamp","startTime","dateEvent","strTimestamp","timestamp"):
        v=ev.get(k)
        if v is None: continue
        if isinstance(v,(int,float)) and v>1e9:
            try:
                tv=float(v); tv/=1000 if tv>1e12 else 1
                return datetime.fromtimestamp(tv, tz=timezone.utc)
            except: pass
        if isinstance(v,str):
            s=v.strip()
            if s.isdigit() and int(s)>1e9:
                try:
                    tv=int(s); tv/=1000 if tv>1e12 else 1
                    return datetime.fromtimestamp(tv, tz=timezone.utc)
                except: pass
            try:
                if "T" in s: return datetime.fromisoformat(s.replace("Z","+00:00"))
                return datetime.strptime(s[:10], "%Y-%m-%d")
            except: continue
    return None

def _rest_days(game_dt, events_raw):
    if not game_dt or not events_raw: return None
    last=_parse_event_date(events_raw[-1]) if events_raw else None
    if not last: return None
    try:
        if last.tzinfo is None: last=last.replace(tzinfo=timezone.utc)
        if game_dt.tzinfo is None: game_dt=game_dt.replace(tzinfo=timezone.utc)
        d=(game_dt-last).days
        return d if d>=0 else None
    except: return None

def _write_out(out):
    try:
        http.OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp=http.OUT_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(http.OUT_PATH)
    except: pass

def _enrich_one(g, idx, n, page=None):
    raw=g.get("raw") if isinstance(g, dict) and "raw" in g else g
    if not isinstance(raw, dict): return None
    gid=raw.get("id")
    liga=(raw.get("liga") or {}).get("name","")
    o1=(raw.get("opponent1") or {}).get("fullName","")
    o2=(raw.get("opponent2") or {}).get("fullName","")
    title=f"{o1} vs {o2}".strip(" vs")
    if liga: title=f"{title} [{liga}]" if title else liga
    stat_id=(raw.get("statisticInfo") or {}).get("gameId")
    try:
        tid1, name1, src1 = resolve.search_team_id(o1) if o1 else (None,None,"none")
        tid2, name2, src2 = resolve.search_team_id(o2) if o2 else (None,None,"none")
        ev1, esrc1 = form_h2h.get_team_last_events(tid1) if tid1 else (None,"none")
        ev2, esrc2 = form_h2h.get_team_last_events(tid2) if tid2 else (None,"none")
        f1=form_h2h.parse_form(ev1, team_id=tid1, team_name=o1) if ev1 else None
        f2=form_h2h.parse_form(ev2, team_id=tid2, team_name=o2) if ev2 else None
        if (not f1 or f1.get("n",0) < 2) and o1:
            try:
                from .fotmob import lookup_fotmob_id as _fmid, get_fotmob_fixtures as _fmf
                _fid=_fmid(o1)
                if _fid:
                    _fb=_fmf(_fid, team_name=o1)
                    if _fb.get("source")=="fotmob" and _fb.get("events"):
                        _ff=form_h2h.parse_form(_fb["events"], team_id=_fid, team_name=o1)
                        if _ff and _ff.get("n",0) > (f1.get("n",0) if f1 else 0):
                            ev1=_fb["events"]; esrc1="fotmob"; f1=_ff
            except Exception: pass
        if (not f2 or f2.get("n",0) < 2) and o2:
            try:
                from .fotmob import lookup_fotmob_id as _fmid2, get_fotmob_fixtures as _fmf2
                _fid2=_fmid2(o2)
                if _fid2:
                    _fb2=_fmf2(_fid2, team_name=o2)
                    if _fb2.get("source")=="fotmob" and _fb2.get("events"):
                        _ff2=form_h2h.parse_form(_fb2["events"], team_id=_fid2, team_name=o2)
                        if _ff2 and _ff2.get("n",0) > (f2.get("n",0) if f2 else 0):
                            ev2=_fb2["events"]; esrc2="fotmob"; f2=_ff2
            except Exception: pass
        f1_home=f1_away=None; f1_home_ok=f1_away_ok=False
        if f1 and f1.get("events_raw"):
            hr=[u for u in f1["events_raw"] if u["is_home"]]; ar=[u for u in f1["events_raw"] if not u["is_home"]]
            if len(hr)>=2:
                f1_home=dict(W=sum(1 for u in hr if u["res"]=="W"),D=sum(1 for u in hr if u["res"]=="D"),L=sum(1 for u in hr if u["res"]=="L"),GF=sum(u["gf"] for u in hr),GA=sum(u["ga"] for u in hr),n=len(hr),form_score=round(sum((0.9**i)*u["pts"] for i,u in enumerate(hr)),2)); f1_home_ok=True
            if len(ar)>=2:
                f1_away=dict(W=sum(1 for u in ar if u["res"]=="W"),D=sum(1 for u in ar if u["res"]=="D"),L=sum(1 for u in ar if u["res"]=="L"),GF=sum(u["gf"] for u in ar),GA=sum(u["ga"] for u in ar),n=len(ar),form_score=round(sum((0.9**i)*u["pts"] for i,u in enumerate(ar)),2)); f1_away_ok=True
        split1="ok" if (f1_home_ok and f1_away_ok) else ("partial" if (f1_home_ok or f1_away_ok) else "insufficient")
        f2_home=f2_away=None; f2_home_ok=f2_away_ok=False
        if f2 and f2.get("events_raw"):
            hr=[u for u in f2["events_raw"] if u["is_home"]]; ar=[u for u in f2["events_raw"] if not u["is_home"]]
            if len(hr)>=2:
                f2_home=dict(W=sum(1 for u in hr if u["res"]=="W"),D=sum(1 for u in hr if u["res"]=="D"),L=sum(1 for u in hr if u["res"]=="L"),GF=sum(u["gf"] for u in hr),GA=sum(u["ga"] for u in hr),n=len(hr),form_score=round(sum((0.9**i)*u["pts"] for i,u in enumerate(hr)),2)); f2_home_ok=True
            if len(ar)>=2:
                f2_away=dict(W=sum(1 for u in ar if u["res"]=="W"),D=sum(1 for u in ar if u["res"]=="D"),L=sum(1 for u in ar if u["res"]=="L"),GF=sum(u["gf"] for u in ar),GA=sum(u["ga"] for u in ar),n=len(ar),form_score=round(sum((0.9**i)*u["pts"] for i,u in enumerate(ar)),2)); f2_away_ok=True
        split2="ok" if (f2_home_ok and f2_away_ok) else ("partial" if (f2_home_ok or f2_away_ok) else "insufficient")
        try: print(f"[{idx}/{n}] {o1} vs {o2} [{liga}]", flush=True)
        except: pass
        h2h=form_h2h.get_h2h(tid1,tid2,gameId_fallback=stat_id,ev1=ev1,ev2=ev2,name1=o1,name2=o2) if (o1 and o2) else dict(record=dict(A=0,D=0,B=0),bias=0,n=0,events=[],source="none")
        xgA=xg.get_xg(o1) if o1 else dict(source="none",xG=None)
        xgB=xg.get_xg(o2) if o2 else dict(source="none",xG=None)
        xvA=_xg_val(xgA); xvB=_xg_val(xgB)
        xG_edge=round((xvA-xvB)/max(xvA,xvB,1),2) if xvA is not None and xvB is not None else 0
        try: xptsA=xpoints.get_xpoints(o1, page=page) if o1 else dict(source="none",xPTS=None)
        except: xptsA=dict(source="none",xPTS=None)
        try: xptsB=xpoints.get_xpoints(o2, page=page) if o2 else dict(source="none",xPTS=None)
        except: xptsB=dict(source="none",xPTS=None)
        xvA2=_xpts_val(xptsA); xvB2=_xpts_val(xptsB)
        xPoints_edge=round((xvA2-xvB2)/max(abs(xvA2),abs(xvB2),1),2) if xvA2 is not None and xvB2 is not None else 0
        try: eloA=elo.get_elo(o1) if o1 else dict(source="none",elo=None)
        except: eloA=dict(source="none",elo=None)
        try: eloB=elo.get_elo(o2) if o2 else dict(source="none",elo=None)
        except: eloB=dict(source="none",elo=None)
        elo_prob_val=None
        try:
            av=eloA.get("elo"); bv=eloB.get("elo")
            if isinstance(av,(int,float)) and isinstance(bv,(int,float)): elo_prob_val=round(elo.elo_prob(av,bv),3)
        except: pass
        pinn=None
        try:
            from . import pinnacle as _pin
            pr=_pin.get_pinnacle_odds(dict(home=o1, away=o2, league=liga)) if (o1 and o2) else {}
            if pr.get("true_home") is not None:
                pinn=dict(source=pr.get("source"), true_home=round(pr["true_home"],3), true_draw=round(pr.get("true_draw") or 0,3), true_away=round(pr.get("true_away") or 0,3), close_home=pr.get("close_home"), close_draw=pr.get("close_draw"), close_away=pr.get("close_away"))
        except Exception: pinn=None
        lineup=None
        try:
            from . import fotmob as _fm
            lf=_fm.get_lineup_by_names(o1, o2) if (o1 and o2) else None
            if lf: lineup=lf
        except Exception: lineup=None
        game_dt=_parse_game_date(raw)
        restA=_rest_days(game_dt, f1["events_raw"] if f1 and f1.get("events_raw") else None)
        restB=_rest_days(game_dt, f2["events_raw"] if f2 and f2.get("events_raw") else None)
        if restA is None and o1:
            try:
                from .fotmob import get_fotmob_fixtures as _fb, lookup_fotmob_id as _mid
                fid=_mid(o1); tgt=fid or (tid1 if tid1 and str(tid1).isdigit() else None)
                if tgt:
                    fb=_fb(tgt, team_name=o1)
                    if fb.get("source")=="fotmob" and (fb.get("events_raw") or fb.get("events")):
                        restA=_rest_days(game_dt, fb.get("events_raw") or fb.get("events"))
            except Exception: pass
        if restB is None and o2:
            try:
                from .fotmob import get_fotmob_fixtures as _fb2, lookup_fotmob_id as _mid2
                fid2=_mid2(o2); tgt2=fid2 or (tid2 if tid2 and str(tid2).isdigit() else None)
                if tgt2:
                    fb2=_fb2(tgt2, team_name=o2)
                    if fb2.get("source")=="fotmob" and (fb2.get("events_raw") or fb2.get("events")):
                        restB=_rest_days(game_dt, fb2.get("events_raw") or fb2.get("events"))
            except Exception: pass
        rest_edge=round((restA-restB)/max(restA or 1,restB or 1,1),2) if isinstance(restA,int) and isinstance(restB,int) else 0
        ll=(liga or "").lower()
        if any(k in ll for k in ("cup","friendly","fa cup","efl","copa","pokal")): motivation="cup_rotation"
        elif "champions" in ll or "europa" in ll: motivation="continental"
        else: motivation="league"
        s1=f1["form_score"] if f1 else 0; s2=f2["form_score"] if f2 else 0
        form_edge=round((s1-s2)/max(s1,s2,1),2) if (f1 or f2) else 0
        lineup_penalty=0
        if lineup:
            ua=len((lineup.get("home") or {}).get("unavailable") or []); ub=len((lineup.get("away") or {}).get("unavailable") or [])
            lineup_penalty=round((ua-ub)*0.05,2)
        entry=dict(game_id=gid, league=liga, title=title[:90], teamA=dict(name=o1, sofascore_id=tid1, form={k:v for k,v in f1.items() if k!="events_raw"} if f1 else None, form_home=f1_home, form_away=f1_away, split=split1, xg=xgA, xpoints=xptsA, elo=eloA, rest_days=restA), teamB=dict(name=o2, sofascore_id=tid2, form={k:v for k,v in f2.items() if k!="events_raw"} if f2 else None, form_home=f2_home, form_away=f2_away, split=split2, xg=xgB, xpoints=xptsB, elo=eloB, rest_days=restB), h2h=h2h, pinnacle=pinn, lineup=lineup, computed=dict(form_edge=form_edge, h2h_bias=h2h.get("bias",0), xG_edge=xG_edge, xG_poisson=None, xPoints_edge=xPoints_edge, elo_prob=elo_prob_val, rest_edge=rest_edge, motivation=motivation, lineup_penalty=lineup_penalty), source=dict(formA=src1, formB=src2, eventsA=esrc1, eventsB=esrc2, h2h=h2h.get("source","none"), xgA=xgA.get("source","none"), xgB=xgB.get("source","none"), xpointsA=xptsA.get("source","none"), xpointsB=xptsB.get("source","none"), eloA=eloA.get("source","none"), eloB=eloB.get("source","none"), pinnacle=(pinn or {}).get("source","none"), lineup=(lineup or {}).get("source","none")), fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    except Exception as e:
        entry=dict(game_id=gid, league=liga, title=title[:90] if 'title' in locals() else "", error=str(e)[:200], teamA=dict(name=o1 if 'o1' in locals() else "", xg=dict(source="none",xG=None), xpoints=dict(source="none",xPTS=None), elo=dict(source="none",elo=None), rest_days=None), teamB=dict(name=o2 if 'o2' in locals() else "", xg=dict(source="none",xG=None), xpoints=dict(source="none",xPTS=None), elo=dict(source="none",elo=None), rest_days=None), h2h=dict(n=0,bias=0,source="none"), computed=dict(form_edge=0,h2h_bias=0,xG_edge=0,xG_poisson=None,xPoints_edge=0,elo_prob=None,rest_edge=0,motivation="unknown"), source=dict(error="exception"), fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return entry

def get_for_games(games, page=None, workers=4):
    n=len(games); results={}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, n or 1))) as ex:
        futs={ex.submit(_enrich_one, g, idx, n, page): idx for idx,g in enumerate(games,1)}
        for fut in as_completed(futs):
            idx=futs[fut]
            try: entry=fut.result()
            except Exception: entry=None
            if entry:
                results[idx]=entry
                _write_out([results[i] for i in sorted(results)])
    out=[results[i] for i in sorted(results)]
    _write_out(out)
    enrich={}
    for entry in out:
        gid=entry.get("game_id")
        if gid: enrich[str(gid)]=entry
    return enrich

__all__=["get_for_games"]
