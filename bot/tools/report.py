#!/usr/bin/env python3
"""report.py — hitung hit rate / ROI / gate dari data/log.csv (stdlib only)"""
import csv, pathlib, statistics, json

LOG = pathlib.Path(__file__).parent.parent / "data" / "log.csv"
REC = pathlib.Path(__file__).parent.parent / "recommendation.json"

def load():
    if not LOG.exists():
        print(f"[!] {LOG} belum ada — jalankan bot.py dulu"); return []
    with open(LOG, encoding="utf-8", newline="") as f:
        r = list(csv.DictReader(f))
    return r

def profit(row):
    try: stake=float(row["stake"]); odd=float(row["odd"])
    except: return 0
    res=(row.get("result") or "").strip().upper()
    if res=="W": return stake*(odd-1)
    if res=="L": return -stake
    return 0

def settle_note(rows):
    # ringkas hasil settled untuk report: 2-3 contoh terakhir
    settled=[r for r in rows if (r.get("result") or "").strip().upper() in ("W","L")]
    if not settled: return ""
    last=settled[-5:]
    lines=[f"  {r.get('event','')[:40]} {r.get('kickoff_wib','')} pick={r.get('pick')} @{r.get('odd')} -> {r.get('result')} {r.get('score','')}" for r in last]
    return "\n".join(lines)

def main():
    rows = load()
    if not rows:
        print("empty log — jalankan bot.py dulu"); return
    total=len(rows)
    settled=[r for r in rows if (r.get("result") or "").strip().upper() in ("W","L")]
    wins=[r for r in settled if r["result"].strip().upper()=="W"]
    pending=total-len(settled)

    hit = len(wins)/len(settled) if settled else 0
    stakes = [float(r["stake"]) for r in settled if r.get("stake")]
    profits = [profit(r) for r in settled]
    tot_stake=sum(stakes) if stakes else 0
    tot_profit=sum(profits)
    roi = tot_profit/tot_stake if tot_stake else 0

    def avg(k, flt=settled):
        vals=[float(r[k]) for r in flt if r.get(k) not in (None,"")]
        return statistics.mean(vals) if vals else 0

    avg_odd=avg("odd")
    avg_margin=avg("margin")
    avg_gap=avg("gap")

    mx=cur=0
    for r in rows:
        if (r.get("result") or "").strip().upper()=="L": cur+=1; mx=max(mx,cur)
        elif (r.get("result") or "").strip().upper()=="W": cur=0

    print("=== 1xBet dry-run report (football Top5) ===")
    print(f"log       : {LOG}")
    print(f"total     : {total}  settled: {len(settled)}  pending: {pending}  wins: {len(wins)}")
    print(f"hit rate  : {hit:.1%}  ({len(wins)}/{len(settled) if settled else 0})")
    print(f"profit    : {tot_profit:+.0f} / stake {tot_stake:.0f}  ROI {roi:+.1%}")
    print(f"avg odd   : {avg_odd:.2f}  margin {avg_margin:.3f}  gap {avg_gap:.3f}  max L streak {mx}")
    if settled:
        last=settled[-7:]
        lhits=sum(1 for r in last if r["result"].strip().upper()=="W")
        print(f"last 7    : {lhits}/{len(last)} ({lhits/len(last):.0%})" if last else "")

    print("\n--- gate ---")
    if not settled or len(settled)<7:
        print("BELUM CUKUP DATA — butuh >=7 settled. Lanjut dry-run + settle.py tiap pagi.")
    elif hit>=0.55 and roi>0:
        print("PERTAHANKAN — lanjut minggu 2, bankroll virtual 500k.")
    elif hit>=0.50:
        print("UPGRADE 3A ringan: tambah gap>=0.15, blacklist liga jelek, pre-match only.")
    else:
        print("UPGRADE 3B berat: butuh value vs Pinnacle / Elo. JANGAN live.")

    if settled:
        print("\n--- by odd bucket ---")
        for lo,hi in [(1.12,1.30),(1.30,1.50),(1.50,1.65)]:
            b=[r for r in settled if lo <= float(r["odd"]) < hi]
            w=sum(1 for r in b if r["result"].strip().upper()=="W")
            print(f" {lo:.2f}-{hi:.2f}: {w}/{len(b)}  {w/len(b):.0%}" if b else f" {lo:.2f}-{hi:.2f}: -")
        print("\n--- by league ---")
        from collections import Counter
        leagues=Counter(r.get("league","?") for r in settled)
        for lg,c in leagues.most_common(5):
            sub=[r for r in settled if r.get("league")==lg]
            w=sum(1 for r in sub if r["result"].strip().upper()=="W")
            print(f" {lg[:28]:28} {w}/{len(sub)} {w/len(sub):.0%}")

    if pending:
        print(f"\n[!] {pending} baris pending — jalankan: python 1xbet/bot/tools/settle.py (otomatis, tanpa manual)")
        print("    Hasil dicek otomatis tiap SCAN (08:00/09:00/13:00/18:00/21:00) — settled muncul di REPORT/SCAN berikutnya.")

    # show settled samples
    note=settle_note(rows)
    if note:
        print("\n--- last settled ---")
        print(note)

    # show Top5 reasons from latest recommendation
    rec_path = REC
    if rec_path.exists():
        try:
            data=json.loads(open(rec_path, encoding="utf-8").read())
            lst=data if isinstance(data, list) else [data]
            print("\n--- Top5 reasons (latest run) ---")
            for i,r in enumerate(lst[:5],1):
                print(f"\n #{i} {r.get('title','?')} pick={r.get('pick')} odd={r.get('odd')} p={r.get('prob')} gap={r.get('gap')} risk={r.get('risk')}")
                for rs in (r.get("reasons") or [])[:5]:
                    print(f"    - {rs[:160]}")
        except: pass

if __name__=="__main__":
    main()
