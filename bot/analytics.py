#!/usr/bin/env python3
"""shim — backward compat, delegates to _analytics package."""
from _analytics import get_for_games
from _analytics.xg import get_xg, get_xg_datamb, get_xg_statz
from _analytics.form_h2h import parse_form, get_h2h, get_team_last_events
from _analytics.resolve import search_team_id
__all__=["get_for_games","get_xg","get_xg_datamb","get_xg_statz","parse_form","get_h2h","get_team_last_events","search_team_id"]
if __name__=="__main__":
    import sys, re, json
    from pathlib import Path
    mock=[{"homeTeam":{"id":1,"name":"Sydney"},"awayTeam":{"id":2,"name":"Wellington"},"homeScore":{"current":2},"awayScore":{"current":0},"status":{"type":"finished"}},{"homeTeam":{"id":3,"name":"X"},"awayTeam":{"id":1,"name":"Sydney"},"homeScore":{"current":1},"awayScore":{"current":1},"status":{"type":"finished"}},{"homeTeam":{"id":1,"name":"Sydney"},"awayTeam":{"id":4,"name":"Y"},"homeScore":{"current":0},"awayScore":{"current":1},"status":{"type":"finished"}}]
    pf=parse_form(mock, team_id=1, limit=3); assert pf["W"]==1 and pf["D"]==1 and pf["L"]==1, pf
    assert abs(pf["form_score"]-(3*1+1*0.9))<0.01
    hm=[{"homeTeam":{"id":1},"awayTeam":{"id":2},"homeScore":{"current":1},"awayScore":{"current":0},"status":{"type":"finished"}},{"homeTeam":{"id":2},"awayTeam":{"id":1},"homeScore":{"current":2},"awayScore":{"current":2},"status":{"type":"finished"}}]
    from _analytics.form_h2h import _h2h_record
    hr=_h2h_record(hm,1); assert hr["record"]["A"]==1 and hr["record"]["D"]==1
    from _analytics.xg import parse_datamb_row
    csv_mock="1,Arsenal,Premier League,1.56,1.86,4.22,33.93,433.22,86.59,57.15\n2,Brighton,Premier League,2.67,2.06,5.44,33.79,419.22,84.44,57.03"
    # pad to 21 cols for parse (function tolerates short)
    assert parse_datamb_row(csv_mock, "arsenal")["xG_per90"]==1.86
    print("[self-check] ok")
    if "--from-rec" in sys.argv:
        p=Path(__file__).parent/"recommendation.json"
        if not p.exists(): p=Path("1xbet/bot/recommendation.json")
        games=[]
        if p.exists():
            rec=json.loads(p.read_text(encoding="utf-8"))
            if isinstance(rec, dict): rec=[rec]
            for r in rec:
                gid=r.get("game_id")
                title=r.get("title","")
                m=re.match(r"(.+?)\s+vs\s+(.+?)(?:\s*\[|$)", title)
                if m:
                    o1=m.group(1).strip(); o2=m.group(2).strip()
                    games.append({"raw":{"id":gid,"opponent1":{"fullName":o1},"opponent2":{"fullName":o2},"liga":{"name":r.get("league","")},"statisticInfo":{}}})
        if games:
            print(f"[analytics] enriching {len(games)} from rec")
            get_for_games(games)
            from _analytics.http import OUT_PATH
            print(f"[analytics] wrote {OUT_PATH}")
        else: print("no games from rec")
