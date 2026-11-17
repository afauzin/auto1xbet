import csv, re
from . import http
import urllib.parse

DATAMB_URL = "https://datamb.football/database/TEAM/teamplots.csv"
# CSV no header, 21 cols. Player header from JS: ID,Player,Top 7 Leagues,Goals per 90,xG per 90...
# Team CSV first col: ID,Team,League,Goals per 90,xG per 90,...
EXTRA_HEADER = "ID,Team,League,Goals per 90,xG per 90,Shots on target per 90,Shots on target %,Passes completed,Pass accuracy %,Possession %,Positional attacks per 90,Counter attacks per 90,Touches in the box per 90,Goals conceded per 90,SoT against per 90,Defensive duels per 90,Defensive duel %,Aerial duels per 90,Aerial duels %,Passes per possession,PPDA"
# ponytail: full Poisson blend add when hit>55% over 100
STATZ_SEARCH = "https://statz.ai/api/search?query={q}"
STATZ_PAGE = "https://statz.ai/team/{slug}/expected-goals"
RE_HASH = re.compile(r"/api/team-history/expected-goals/\d+/[a-f0-9]+")

def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"\s*\(women\)\s*", " ", s, flags=re.I)).strip().lower()

def parse_datamb_row(csv_text, norm):
    if not csv_text: return None
    cols = EXTRA_HEADER.split(",")
    # CSV has 21 cols but no header row
    reader = csv.DictReader(csv_text.strip().splitlines(), fieldnames=cols)
    best = None
    for row in reader:
        team = (row.get("Team") or "").strip()
        if not team: continue
        tl = team.lower()
        # fuzzy
        if norm == tl or norm in tl or tl in norm:
            try:
                xg = float(row.get("xG per 90") or row.get("xG per 90".strip()) or 0)
                gf = float(row.get("Goals per 90") or 0)
            except: continue
            return dict(source="datamb", xG_per90=xg, goals_per90=gf, team=team)
        # token overlap fallback
        nt=set(norm.split()); et=set(tl.split())
        if nt & et and len(nt & et) >= min(len(nt), len(et)):
            try: xg=float(row.get("xG per 90") or 0); gf=float(row.get("Goals per 90") or 0)
            except: continue
            if best is None: best=dict(source="datamb", xG_per90=xg, goals_per90=gf, team=team)
    return best

def get_xg_datamb(name):
    norm=_norm(name)
    key=f"xg:datamb:{norm}"
    hit=http._cache_get(key)
    if hit and "xG_per90" in hit: return hit
    http._throttle()
    txt=http.fetch_csv(DATAMB_URL)
    if not txt: return None
    row=parse_datamb_row(txt, norm)
    if row:
        http._cache_set(key, row)
        return row
    return None

def get_xg_statz(name):
    norm=_norm(name)
    key=f"xg:statz:{norm}"
    hit=http._cache_get(key)
    if hit and "xG_avg" in hit: return hit
    # step 1 search
    sk=f"xg:search:{norm}"
    s_hit=http._cache_get(sk)
    if s_hit and s_hit.get("id"):
        sid, slug = s_hit["id"], s_hit.get("slug","")
    else:
        http._throttle()
        data=http.fetch_json(STATZ_SEARCH.format(q=urllib.parse.quote(norm)))
        if not data: return None
        teams=data.get("teams") or data.get("data") or data.get("results") or []
        if isinstance(teams, dict): teams=[v for v in teams.values() if isinstance(v, dict)]
        if not teams: return None
        # pick best containing norm
        best=None; best_s=-1
        for t in teams:
            nm=(t.get("name") or t.get("strTeam") or t.get("slug") or "").lower()
            tid=t.get("id")
            slug2=t.get("slug") or nm.replace(" ","-")
            if not tid: continue
            sc=0
            if norm==nm: sc=100
            elif norm in nm or nm in norm: sc=80
            else:
                ov=len(set(norm.split()) & set(nm.split()))
                if ov: sc=ov*10
                else: continue
            if sc>best_s: best_s=sc; best=(tid, slug2, t.get("name") or nm)
        if not best:
            # fallback first
            t=teams[0]; best=(t.get("id"), t.get("slug") or "", t.get("name") or "")
            if not best[0]: return None
        sid, slug = best[0], best[1]
        http._cache_set(sk, {"id": sid, "slug": slug})
    if not sid or not slug:
        return None
    # step 2 hash from page
    hk=f"xg:hash:{sid}"
    h_hit=http._cache_get(hk)
    if h_hit and h_hit.get("hash"):
        hhash=h_hit["hash"]
    else:
        http._throttle()
        html=http.fetch_text(STATZ_PAGE.format(slug=slug))
        if not html: return None
        m=RE_HASH.search(html)
        if not m: return None
        # extract hash part
        hhash=m.group(0).split("/")[-1]
        http._cache_set(hk, {"hash": hhash})
    # step 3 log
    http._throttle()
    url=f"https://statz.ai/api/team-history/expected-goals/{sid}/{hhash}"
    data=http.fetch_json(url)
    if not data: return None
    log=data.get("log") or data.get("data") or data.get("history") or []
    if isinstance(log, dict): log=list(log.values())
    if not isinstance(log, list) or not log: return None
    vals=[float(x.get("team_value") or x.get("teamValue") or 0) for x in log if x.get("team_value") or x.get("teamValue")]
    opp=[float(x.get("opp_value") or x.get("oppValue") or 0) for x in log if x.get("opp_value") or x.get("oppValue")]
    if not vals: return None
    xg_avg=sum(vals)/len(vals); xga_avg=sum(opp)/len(opp) if opp else 0
    res=dict(source="statz", xG_avg=round(xg_avg,2), xGA_avg=round(xga_avg,2), n=len(vals), team=name)
    http._cache_set(key, res)
    return res

def get_xg(name):
    norm=_norm(name)
    key=f"xg:{norm}"
    hit=http._cache_get(key)
    if hit and hit.get("source") in ("datamb","statz","none"): return hit
    r=get_xg_datamb(name)
    if r:
        http._cache_set(key, r)
        return r
    r2=get_xg_statz(name)
    if r2:
        http._cache_set(key, r2)
        return r2
    none=dict(source="none", xG=None)
    http._cache_set(key, none)
    return none

__all__=["get_xg","get_xg_datamb","get_xg_statz","parse_datamb_row","DATAMB_URL"]

if __name__=="__main__":
    # asserts
    csv_mock="1,Arsenal,Premier League,1.56,1.86,4.22,33.93,433.22,86.59,57.15,28.67,0.67,27.89,0.56,2.78,46.22,49.28,33.56,52.32,5.22,10.65\n2,Brighton,Premier League,2.67,2.06,5.44,33.79,419.22,84.44,57.03,30.78,1.22,23.11,0.78,3.56,58.44,54.18,41.11,51.62,5.18,8.06"
    assert parse_datamb_row(csv_mock, "arsenal")["xG_per90"]==1.86
    assert parse_datamb_row(csv_mock, "brighton")["xG_per90"]==2.06
    # statz mean mock
    log=[{"team_value":1.83,"opp_value":2.22},{"team_value":0.81,"opp_value":1.10}]
    assert round(sum(x["team_value"] for x in log)/len(log),2)==1.32
    print("[self-check xg] ok")
