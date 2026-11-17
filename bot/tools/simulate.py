#!/usr/bin/env python3
"""simulate.py — Monte Carlo 1000x flat 1% bankroll 100k stdlib only. ponytail: Kelly live add when edge>0.03+100 settled"""
import csv, json, pathlib, random, statistics, math

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "log.csv"
ANA = ROOT / "data" / "analytics.json"
OUT_JSON = ROOT / "data" / "sim_report.json"
OUT_MD = ROOT / "data" / "sim_report.md"
N = 1000
SEED = 42
BANKROLL0 = 100000
STAKE_FLAT = 1000  # 1% best practice cap 2%=2000

def _clamp(v, lo=0.05, hi=0.95): return max(lo, min(hi, v))

def _blend_ptrue(row, ana_map):
    gid = (row.get("game_id") or "").strip()
    pick = (row.get("pick") or "").strip().upper()
    p_market = float(row.get("prob") or 0) or 0.5
    rec = ana_map.get(gid)
    if not rec:
        return p_market, "WARN_fallback_market_no_analytics"
    c = rec.get("computed") or {}
    # individual probs for A win
    elo_p = c.get("elo_prob")  # already 0-1 for A
    form_edge = c.get("form_edge")  # -1..1
    xg_edge = c.get("xG_edge")  # -1..1
    h2h_bias = c.get("h2h_bias", 0)  # -1..1 approx
    parts = []
    wsum = 0
    # elo 0.4
    if isinstance(elo_p, (int,float)):
        parts.append((elo_p, 0.4)); wsum += 0.4
    # form 0.3 -> 0.5+edge*0.25
    if isinstance(form_edge, (int,float)):
        fp = _clamp(0.5 + float(form_edge)*0.25, 0.35, 0.65)
        parts.append((fp, 0.3)); wsum += 0.3
    # xG 0.2
    if isinstance(xg_edge, (int,float)):
        xp = _clamp(0.5 + float(xg_edge)*0.25, 0.35, 0.65)
        parts.append((xp, 0.2)); wsum += 0.2
    # h2h 0.1 -> 0.5+bias*0.1
    if isinstance(h2h_bias, (int,float)) and rec.get("h2h",{}).get("n",0) >= 2:
        hp = _clamp(0.5 + float(h2h_bias)*0.1, 0.4, 0.6)
        parts.append((hp, 0.1)); wsum += 0.1
    # pinnacle 0.5 -> sharpest signal (steamwatch devig)
    pinn = rec.get("pinnacle") or {}
    pp = pinn.get("true_home")
    if isinstance(pp, (int,float)) and pp > 0:
        parts.append((_clamp(float(pp), 0.05, 0.95), 0.5)); wsum += 0.5
    if wsum == 0:
        return p_market, "WARN_fallback_market_no_signal"
    blend = sum(p*w for p,w in parts)/wsum  # prob A wins
    # map to pick
    if pick == "1":
        p = _clamp(blend)
    elif pick == "2":
        p = _clamp(1 - blend)
    elif pick == "X":
        # no draw model -> fallback market
        return p_market, "WARN_fallback_market_draw_no_model"
    else:
        p = _clamp(blend)
    return p, "blend"

def load_picks():
    if not LOG.exists(): return [], {}, ["no_log"]
    rows = list(csv.DictReader(open(LOG, encoding="utf-8", newline="")))
    ana_map = {}
    if ANA.exists():
        try:
            data = json.loads(ANA.read_text(encoding="utf-8"))
            lst = data if isinstance(data, list) else []
            for e in lst:
                gid = str(e.get("game_id") or "")
                if gid: ana_map[gid] = e
        except: pass
    picks = []
    warns = set()
    for r in rows:
        try:
            odd = float(r.get("odd") or 0)
            if odd < 1.01: continue
            p_true, flag = _blend_ptrue(r, ana_map)
            if flag.startswith("WARN"): warns.add(flag)
            picks.append(dict(
                gid=r.get("game_id"), league=r.get("league"), event=r.get("event"),
                pick=r.get("pick"), odd=odd, p_market=float(r.get("prob") or 0),
                p_true=p_true, flag=flag, gap=r.get("gap"), margin=r.get("margin")
            ))
        except Exception as e:
            warns.add(f"skip:{e}")
            continue
    return picks, ana_map, sorted(warns)

def simulate(picks, n=N, seed=SEED, bankroll0=BANKROLL0, stake=STAKE_FLAT):
    rnd = random.Random(seed)
    finals, rois, hits, dds, streaks = [], [], [], [], []
    ruin = 0
    profit_cnt = 0
    for _ in range(n):
        br = bankroll0
        peak = br
        max_dd = 0
        cur_streak = max_streak = 0
        wins = 0
        tot_stake = 0
        tot_profit = 0
        for p in picks:
            # flat 1% cap 2% running
            s = min(stake, int(br*0.02)) if br*0.02 < stake else stake
            s = max(1, int(s))
            tot_stake += s
            win = rnd.random() < p["p_true"]
            if win:
                profit = s * (p["odd"] - 1)
                wins += 1
                cur_streak = 0
            else:
                profit = -s
                cur_streak += 1
                max_streak = max(max_streak, cur_streak)
            tot_profit += profit
            br += profit
            peak = max(peak, br)
            dd = (peak - br)/peak if peak else 0
            max_dd = max(max_dd, dd)
        finals.append(br)
        roi = tot_profit/tot_stake if tot_stake else 0
        rois.append(roi)
        hit = wins/len(picks) if picks else 0
        hits.append(hit)
        dds.append(max_dd)
        streaks.append(max_streak)
        if br < 50000: ruin += 1
        if br > bankroll0: profit_cnt += 1
    def qs(v):
        s = sorted(v)
        def q(p): 
            k = int(len(s)*p)
            k = max(0, min(len(s)-1, k))
            return s[k]
        return dict(p5=q(0.05), p50=q(0.50), p95=q(0.95), mean=statistics.mean(s) if s else 0, min=min(s) if s else 0, max=max(s) if s else 0, stdev=statistics.pstdev(s) if len(s)>1 else 0)
    out = dict(
        bankroll=qs(finals),
        roi=qs(rois),
        hit=qs(hits),
        max_drawdown=qs(dds),
        max_losing_streak=qs(streaks),
        prob_ruin=ruin/n, prob_profit=profit_cnt/n,
        sharpe=(statistics.mean(rois)/statistics.pstdev(rois) if len(rois)>1 and statistics.pstdev(rois) else 0),
        ev_per_pick=statistics.mean([p["p_true"]*p["odd"]-1 for p in picks]) if picks else 0,
    )
    return out

def main():
    picks, ana_map, warns = load_picks()
    if not picks:
        print("no picks in log.csv")
        OUT_JSON.write_text(json.dumps(dict(error="no_picks"), indent=2), encoding="utf-8")
        return
    n_settled = sum(1 for r in csv.DictReader(open(LOG, encoding="utf-8", newline="")) if (r.get("result") or "").strip().upper() in ("W","L"))
    res = simulate(picks)
    meta = dict(N=N, seed=SEED, bankroll_awal=BANKROLL0, stake_rule="flat1% cap2% (1000/2000)", n_picks=len(picks), n_settled=n_settled, n_analytics=len(ana_map), warns=warns)
    if n_settled < 30:
        meta["warn"] = f"WARN_insufficient_data n_settled={n_settled} need 30+ ; CI lebar, butuh 100 settled (RENCANA 3C) utk klaim 55%"
    if len(picks) < 5:
        meta["warn2"] = "n_picks<5 — tambah 3 hari dry-run 6 runs ~30 picks baru representative"
    # blend vs fallback ratio
    nb = sum(1 for p in picks if p["flag"]=="blend")
    meta["blend_ratio"] = f"{nb}/{len(picks)}"
    report = dict(meta=meta, picks=picks[:10], **res)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # md
    b=res["bankroll"]; roi=res["roi"]; hit=res["hit"]
    md = f"""# Sim report — 100k flat 1% N={N} seed {SEED}
- picks: {len(picks)} (settled {n_settled}) analytics {len(ana_map)} blend {nb}/{len(picks)} warns: {', '.join(warns) or '-'}
- stake: {STAKE_FLAT} (1% cap {int(BANKROLL0*0.02)}) bankroll awal {BANKROLL0}
- EV/pick (true*odd-1): {res['ev_per_pick']:+.3f}
- bankroll p5/p50/p95: {b['p5']:.0f} / {b['p50']:.0f} / {b['p95']:.0f} mean {b['mean']:.0f} min {b['min']:.0f} max {b['max']:.0f}
- ROI mean {roi['mean']:+.1%} p5 {roi['p5']:+.1%} p95 {roi['p95']:+.1%}
- hit mean {hit['mean']:.1%} p5 {hit['p5']:.1%}
- max DD p50 {res['max_drawdown']['p50']:.1%} max {res['max_drawdown']['max']:.1%} streak p95 {res['max_losing_streak']['p95']:.0f}
- prob_profit {res['prob_profit']:.1%} prob_ruin(<50k) {res['prob_ruin']:.1%} sharpe {res['sharpe']:.2f}
"""
    if "warn" in meta: md += f"\n> {meta['warn']}\n"
    md += f"\n## gate\n"
    gate_ok = n_settled>=20 and hit['mean']>=0.55 and roi['mean']>0.02 and res['prob_ruin']<=0.05
    md += f"- GATE_FULL {'LOLOS' if gate_ok else 'BLOCKED'} (need settled>=20 hit>=55% ROI>2% ruin<=5%)\n"
    provisional = res['prob_profit']>0.6 and b['p5']>80000
    md += f"- GATE_PROVISIONAL_MICRO {'LOLOS 1k stake' if provisional else 'BLOCKED'} (need prob_profit>60% p5>80k)\n"
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"written {OUT_JSON} + {OUT_MD}")

if __name__ == "__main__":
    main()
