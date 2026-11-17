import statistics

def _reason_odds(pick, odds, prob, gap, margin, ev, kelly, raw, bankroll):
    r = []
    fav_odd = odds[pick]
    opp = {k: v for k, v in odds.items() if k != pick}
    opp_s = ", ".join(f"{k} {v}" for k, v in opp.items())
    opp_prob_max = max(prob[k] for k in opp) if opp else 0
    r.append(f"Odds {pick} {fav_odd} vs {opp_s} — prob margin-removed {prob[pick]:.1%} vs {opp_prob_max:.1%} (gap {gap:.1%}, var {statistics.variance(list(prob.values())):.4f} jika 3-way)")
    r.append(f"Margin {margin:.3f} (overround {margin-1:.1%}) — {'rendah, fee bandar kecil' if margin < 1.07 else 'tinggi, skip jika >1.08'}")
    b = fav_odd - 1
    r.append(f"EV {ev:+.3f} = p*b - q = {prob[pick]:.3f}*{b:.2f} - {1-prob[pick]:.3f} — {'positif tipis (edge pasar)' if ev > 0 else 'negatif (tanpa edge eksternal underdog sering upset)'}")
    r.append(f"Kelly {kelly:.3f} (cap 25%) → stake {round(bankroll*kelly) if kelly > 0 else 1:.0f} cap 2% bankroll (~{(bankroll*0.02):.0f})")
    return r

def _reason_market(raw):
    r = []
    try: ec = raw.get("eventsCount", 0); r.append(f"Market depth {ec} pasaran — {'likuid (>200), odd stabil' if ec > 200 else 'sepi, rawan gerak'}")
    except: pass
    try:
        loc = (raw.get("matchInfo") or {}).get("location", "")
        o1 = (raw.get("opponent1") or {}).get("fullName", "")
        if loc and o1 and o1.split()[0].lower() in loc.lower(): r.append(f"Home advantage: {o1} main di {loc} (kandang)")
        elif loc: r.append(f"Lokasi {loc} — cek home/away, cuaca {(raw.get('matchInfo') or {}).get('weatherDescription','')}")
    except: pass
    try:
        liga = (raw.get("liga") or {}).get("name", "")
        if liga: r.append(f"Liga {liga} — filter liga top, hindari friendly jika margin tinggi")
    except: pass
    return r

def _reason_analytics(analytics_entry):
    r = []
    if not analytics_entry: return r
    try:
        fA = analytics_entry.get("teamA", {}).get("form"); fB = analytics_entry.get("teamB", {}).get("form")
        h2h = analytics_entry.get("h2h", {}); comp = analytics_entry.get("computed", {})
        src = analytics_entry.get("source", {})
        if fA or fB:
            fa_s = f"{fA['W']}-{fA['D']}-{fA['L']} GF{fA['GF']} GA{fA['GA']} score{fA['form_score']}" if fA else "n/a"
            fb_s = f"{fB['W']}-{fB['D']}-{fB['L']} GF{fB['GF']} GA{fB['GA']} score{fB['form_score']}" if fB else "n/a"
            fe = comp.get("form_edge", 0)
            spA = analytics_entry.get("teamA", {}).get("split", ""); spB = analytics_entry.get("teamB", {}).get("split", "")
            spl = ""
            fa_home = analytics_entry.get("teamA", {}).get("form_home"); fa_away = analytics_entry.get("teamA", {}).get("form_away")
            fb_home = analytics_entry.get("teamB", {}).get("form_home"); fb_away = analytics_entry.get("teamB", {}).get("form_away")
            if fa_home: spl += f" | {analytics_entry['teamA']['name']} home {fa_home['W']}-{fa_home['D']}-{fa_home['L']}"
            if fa_away: spl += f" away {fa_away['W']}-{fa_away['D']}-{fa_away['L']}"
            if fb_home: spl += f" | {analytics_entry['teamB']['name']} home {fb_home['W']}-{fb_home['D']}-{fb_home['L']}"
            if fb_away: spl += f" away {fb_away['W']}-{fb_away['D']}-{fb_away['L']}"
            r.append(f"Form 5: {analytics_entry['teamA']['name']} {fa_s} vs {analytics_entry['teamB']['name']} {fb_s} — edge {fe:+.2f} (1.1: W3 D1 L0, weight 0.9^age){spl} src {src.get('eventsA')}/{src.get('eventsB')}")
        if h2h and h2h.get("n", 0) > 0:
            rec = h2h.get("record", {}); bias = h2h.get("bias", 0)
            r.append(f"H2H {h2h['n']} pertemuan: A {rec.get('A',0)} D {rec.get('D',0)} B {rec.get('B',0)} bias {bias:+.2f} ({'A dominan' if bias>0.2 else 'B dominan' if bias<-0.2 else 'imbang'}) src {h2h.get('source','')}")
        elif h2h and h2h.get("source") == "none":
            r.append("H2H tidak ditemukan (5 laga tak ada irisan) — netral")
        try:
            xa = analytics_entry.get("teamA", {}).get("xg"); xb = analytics_entry.get("teamB", {}).get("xg")
            xge = (analytics_entry.get("computed") or {}).get("xG_edge", 0)
            def _xv(d):
                if not d: return None
                return d.get("xG_per90") if "xG_per90" in d else d.get("xG_avg") if "xG_avg" in d else d.get("xG")
            xvA = _xv(xa); xvB = _xv(xb)
            if xvA is not None and xvB is not None:
                r.append(f"xG: {analytics_entry['teamA']['name']} {xvA} vs {analytics_entry['teamB']['name']} {xvB} — edge {xge:+.2f} ({xa.get('source','')}/{xb.get('source','')})")
            elif xvA is not None:
                r.append(f"xG: {analytics_entry['teamA']['name']} {xvA} ({xa.get('source','')}) vs n/a")
            elif xvB is not None:
                r.append(f"xG: {analytics_entry['teamB']['name']} {xvB} ({xb.get('source','')}) vs n/a")
        except: pass
        try:
            xa = analytics_entry.get("teamA", {}).get("xpoints"); xb = analytics_entry.get("teamB", {}).get("xpoints")
            xpe = (analytics_entry.get("computed") or {}).get("xPoints_edge", 0)
            if xa and xb and xa.get("xPTS") is not None and xb.get("xPTS") is not None:
                r.append(f"xPoints: {analytics_entry['teamA']['name']} {xa['xPTS']} vs {analytics_entry['teamB']['name']} {xb['xPTS']} — edge {xpe:+.2f} ({xa.get('source','')}/{xb.get('source','')})")
        except: pass
        try:
            xa = analytics_entry.get("teamA", {}).get("elo"); xb = analytics_entry.get("teamB", {}).get("elo")
            ep = (analytics_entry.get("computed") or {}).get("elo_prob")
            if xa and xb and xa.get("elo") is not None and xb.get("elo") is not None:
                r.append(f"Elo: {xa['elo']} vs {xb['elo']} — P(A) {ep:.1%}" if ep is not None else f"Elo: {xa['elo']} vs {xb['elo']}")
        except: pass
        try:
            ra = analytics_entry.get("teamA", {}).get("rest_days"); rb = analytics_entry.get("teamB", {}).get("rest_days")
            re_ = (analytics_entry.get("computed") or {}).get("rest_edge", 0)
            mot = (analytics_entry.get("computed") or {}).get("motivation", "")
            if ra is not None or rb is not None:
                r.append(f"Rest {ra}d vs {rb}d edge {re_:+.2f} — {mot}")
            elif mot and mot != "league":
                r.append(f"Motivasi {mot}")
        except: pass
    except Exception as e:
        r.append(f"Analytics parse err {e}")
    return r

def build_reasons(pick, odds, prob, gap, margin, ev, kelly, raw, analytics_entry=None, bankroll=None):
    if bankroll is None:
        try: from config import BANKROLL as bankroll
        except: bankroll = 100000
    r = []
    r.extend(_reason_odds(pick, odds, prob, gap, margin, ev, kelly, raw, bankroll))
    r.extend(_reason_market(raw))
    r.extend(_reason_analytics(analytics_entry))
    if pick in ("1", "2"):
        try: from config import MIN_ODD as _lo, MAX_ODD as _hi
        except: _lo, _hi = 1.12, 2.00
        r.append(f"Rekomendasi {pick} ({'tuan rumah' if pick=='1' else 'tamu/tim unggulan'}) karena gap terbesar & margin rendah — bandar paling yakin, risiko upset paling kecil di window {_lo:.2f}-{_hi:.2f}")
    elif pick == "X":
        r.append("Rekomendasi X (seri) — jarang low-risk, hanya jika gap X vs rival kecil tapi kelly positif (kasus langka)")
    r.append("Basis: prob = 1/odd / margin (market-implied). Akurat untuk ranking relatif, belum true prob — butuh value vs Pinnacle/Elo untuk +EV long-term")
    return r
