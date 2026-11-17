from core.odds import is_football, extract_odds, implied_prob, pick_best, kelly_ev, risk_score
from core.reasons import build_reasons

def _adjust_risk(row, ae):
    orig = row["risk"]
    fe = (ae.get("computed") or {}).get("form_edge", 0)
    bias = (ae.get("h2h") or {}).get("bias", 0)
    if row["pick"] == "1" and fe > 0.2: row["risk"] = round(row["risk"] - 0.15, 3)
    elif row["pick"] == "2" and fe < -0.2: row["risk"] = round(row["risk"] - 0.15, 3)
    elif row["pick"] == "1" and fe < -0.2: row["risk"] = round(row["risk"] + 0.20, 3)
    elif row["pick"] == "2" and fe > 0.2: row["risk"] = round(row["risk"] + 0.20, 3)
    if row["pick"] == "1" and bias > 0.2: row["risk"] = round(row["risk"] - 0.10, 3)
    elif row["pick"] == "2" and bias < -0.2: row["risk"] = round(row["risk"] - 0.10, 3)
    elif row["pick"] == "1" and bias < -0.2: row["risk"] = round(row["risk"] + 0.10, 3)
    elif row["pick"] == "2" and bias > 0.2: row["risk"] = round(row["risk"] + 0.10, 3)
    xge = (ae.get("computed") or {}).get("xG_edge", 0)
    if xge and row["pick"] in ("1", "2"):
        sig = xge if row["pick"] == "1" else -xge
        row["risk"] = round(max(0, min(1, row["risk"] - sig * 0.15)), 3)
    # ponytail: pinnacle sharp gate value>0.03 -> de-risk; negative value -> penalize
    pinn = ae.get("pinnacle") or {}
    tp = {"1": pinn.get("true_home"), "X": pinn.get("true_draw"), "2": pinn.get("true_away")}.get(row["pick"])
    if isinstance(tp, (int, float)) and tp > 0:
        value = tp * row["odd"] - 1
        if value > 0.03: row["risk"] = round(max(0, row["risk"] - 0.10), 3)
        elif value < -0.05: row["risk"] = round(min(1, row["risk"] + 0.15), 3)
    # ponytail: lineup_penalty>0 = tim pick lebih banyak absen -> penalize; lawan absen lebih -> de-risk
    lp = (ae.get("computed") or {}).get("lineup_penalty", 0)
    if lp and row["pick"] in ("1", "2"):
        sig = lp if row["pick"] == "1" else -lp
        row["risk"] = round(max(0, min(1, row["risk"] + sig * 0.30)), 3)
    return orig != row["risk"]

def analyze(games, page=None):
    try: from config import MAX_ODD, MIN_ODD, BANKROLL, TOP_N
    except: MAX_ODD=2.00; MIN_ODD=1.12; BANKROLL=100000; TOP_N=5
    rows = []
    fb_total = 0; fb_with_odds = 0
    from datetime import datetime, timezone, timedelta
    WIB = timezone(timedelta(hours=7))
    now = datetime.now(timezone.utc)
    def _game_dt(raw):
        for k in ("startTs","startTimestamp","startTime","startDate","date","kickoff","time","beginTime"):
            v=raw.get(k)
            if v is None: continue
            if isinstance(v,(int,float)) and v>1e9:
                try:
                    tv=float(v); tv/=1000 if tv>1e12 else 1
                    return datetime.fromtimestamp(tv, tz=timezone.utc)
                except: pass
            if isinstance(v,str) and v.isdigit() and int(v)>1e9:
                try:
                    tv=int(v); tv/=1000 if tv>1e12 else 1
                    return datetime.fromtimestamp(tv, tz=timezone.utc)
                except: pass
            if isinstance(v,str):
                try: return datetime.fromisoformat(v.replace("Z","+00:00"))
                except: pass
        return None
    for g in games:
        raw = g.get("raw") if isinstance(g, dict) else g
        if not is_football(raw): continue
        # filter kickoff fut only — skip finished/unknown
        dt=_game_dt(raw)
        if dt is None: continue
        if dt <= now: continue
        fb_total += 1
        odds = extract_odds(g)
        if not odds: continue
        fb_with_odds += 1
        prob, margin = implied_prob(odds)
        pick, p, gap, var = pick_best(prob)
        odd = odds[pick]
        if not (MIN_ODD <= odd <= MAX_ODD): continue
        kelly, ev = kelly_ev(p, odd)
        risk = risk_score(gap, var, margin, kelly)
        stake = round(BANKROLL * kelly, 0) if kelly > 0 else 1
        try:
            from config import STAKE as _STAKE
            if kelly <= 0: stake = _STAKE
        except: pass
        stake = max(1, min(stake, BANKROLL * 0.02, 5000))
        title = ""
        o1 = (raw.get("opponent1") or {}).get("fullName", "")
        o2 = (raw.get("opponent2") or {}).get("fullName", "")
        liga = (raw.get("liga") or {}).get("name", "")
        gid = raw.get("id")
        # ponytail: obscure filter single line; expand when hit<55% after 100 settled
        _obscure_src = f"{liga} {o1} {o2}".lower()
        if any(k in _obscure_src for k in ("afghanistan","uzbekistan","ncaa","youth","u17","u19","u20","u21","u23","u-23","women","bangalore","mongolia","development league","friendlies","friendly","club friendlies","special bets")): print(f"[-] skip obscure {liga}"); continue
        if margin > 1.08: print(f"[-] skip margin {margin:.3f} {liga}"); continue
        if o1 or o2: title = f"{o1} vs {o2}".strip(" vs")
        if liga: title = f"{title} [{liga}]" if title else liga
        reasons = build_reasons(pick, odds, prob, gap, margin, ev, kelly, raw)
        dt_wib = dt.astimezone(WIB)
        kickoff_wib = dt_wib.strftime("%d/%m %H:%M WIB")
        rows.append(dict(game_id=gid, league=liga, pick=pick, odd=odd, prob=round(p, 3), ev=round(ev, 3), kelly=round(kelly, 3),
                         gap=round(gap, 3), var=round(var, 4), margin=round(margin, 3), risk=round(risk, 3),
                         stake=stake, odds=odds, prob_map={k: round(v, 3) for k, v in prob.items()},
                         title=title[:90] or "unknown", reasons=reasons, raw=raw, kickoff_wib=kickoff_wib))
    try: from config import MIN_ODD as _lo, MAX_ODD as _hi
    except: _lo, _hi = 1.12, 2.00
    print(f"[+] football: {fb_total} total, {fb_with_odds} with odds, {len(rows)} after {_lo:.2f}-{_hi:.2f} filter")
    # enrich — lazy import to avoid cycle
    try: from _analytics import get_for_games
    except:
        try:
            import sys as _sys; from pathlib import Path as _P
            _sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
            from _analytics import get_for_games
        except: get_for_games = None
    if get_for_games and rows:
        try:
            cand = rows[:TOP_N * 2]
            enrich = get_for_games([dict(raw=r["raw"]) for r in cand], page=page)
            for r in cand:
                ae = enrich.get(str(r["game_id"])) if isinstance(enrich, dict) else None
                if not ae: continue
                r["analytics"] = {k: v for k, v in ae.items()}
                _adjust_risk(r, ae)
                r["reasons"] = build_reasons(r["pick"], r["odds"], r["prob_map"], r["gap"], r["margin"], r["ev"], r["kelly"], r["raw"], ae)
            print(f"[+] analytics enrich {len([r for r in cand if 'analytics' in r])}/{len(cand)} (form/h2h)")
        except Exception as e:
            print(f"[!] analytics enrich fail {e}")
    rows.sort(key=lambda r: (r["risk"], -r["ev"], -r["prob"]))
    return rows[:TOP_N * 2]
