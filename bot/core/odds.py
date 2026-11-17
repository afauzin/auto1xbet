import statistics

def is_football(raw):
    sp = raw.get("sport") if isinstance(raw, dict) else None
    if isinstance(sp, dict): return sp.get("id") == 1
    if isinstance(sp, int): return sp == 1
    return False

def extract_odds(game_raw):
    g = game_raw.get("raw") if isinstance(game_raw, dict) and "raw" in game_raw else game_raw
    if not isinstance(g, dict): return None
    egs = g.get("eventGroups") or []
    for eg in egs:
        if eg.get("groupId") == 1:
            try:
                evts = eg.get("events") or []
                if len(evts) == 3:
                    cf1 = float(evts[0][0]["cf"]); cfx = float(evts[1][0]["cf"]); cf2 = float(evts[2][0]["cf"])
                    if 1.01 < cf1 < 50 and 1.01 < cfx < 50 and 1.01 < cf2 < 50:
                        return {"1": cf1, "X": cfx, "2": cf2}
            except: pass
    for eg in egs:
        if eg.get("groupId") == 101:
            try:
                evts = eg.get("events") or []
                cf1 = float(evts[0][0]["cf"]); cf2 = float(evts[1][0]["cf"])
                if 1.01 < cf1 < 50 and 1.01 < cf2 < 50: return {"1": cf1, "2": cf2}
            except: pass
    for eg in egs:
        evts = eg.get("events") or []
        if len(evts) == 3:
            try:
                cf1 = float(evts[0][0]["cf"]); cfx = float(evts[1][0]["cf"]); cf2 = float(evts[2][0]["cf"])
                if 1.01 < cf1 < 50 and 1.01 < cfx < 50 and 1.01 < cf2 < 50: return {"1": cf1, "X": cfx, "2": cf2}
            except: pass
    return None

def implied_prob(odds):
    imp = {k: 1 / v for k, v in odds.items()}
    margin = sum(imp.values())
    prob = {k: imp[k] / margin for k in imp}
    return prob, margin

def pick_best(prob):
    pick = max(prob, key=prob.get)
    p = prob[pick]
    sp = sorted(prob.values(), reverse=True)
    gap = sp[0] - sp[1] if len(sp) > 1 else 0
    var = statistics.variance(list(prob.values())) if len(prob) > 1 else 0
    return pick, p, gap, var

def kelly_ev(p, odd):
    b = odd - 1; q = 1 - p
    kelly = (b * p - q) / b if b > 0 else 0
    kelly = max(0, min(kelly, 0.25))
    ev = p * b - q
    return kelly, ev

def risk_score(gap, var, margin, kelly):
    return (1 - gap) * 0.5 + var * 2 + (margin - 1) * 1.0 - kelly * 0.3

def stake_for(kelly, bankroll, fallback=1):
    # ponytail: cap 2% bankroll + 5000 — keep identical to bot.py:266
    br = bankroll
    stake = round(br * kelly, 0) if kelly > 0 else fallback
    return max(1, min(stake, br * 0.02, 5000))

# self-check feed v3 football 1X2 groupId 1
assert extract_odds({"raw": {"eventGroups": [{"groupId": 1, "events": [[{"cf": 3.36}], [{"cf": 3.15}], [{"cf": 2.3}]]}]}}) == {"1": 3.36, "X": 3.15, "2": 2.3}
assert extract_odds({"raw": {"eventGroups": [{"groupId": 101, "events": [[{"cf": 1.6}], [{"cf": 2.4}]]}]}}) == {"1": 1.6, "2": 2.4}
