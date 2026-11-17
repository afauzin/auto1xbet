#!/usr/bin/env python3
"""
1xBet auto-login + football-only scan + Top5 rank + reasoning (dry-run default)
ponytail: external stats (api-football/Elo) & Pinnacle value — add when hit<55% over 100
"""
import json, re, sys, time
from pathlib import Path as _Path
from urllib.parse import urlencode

sys.path.insert(0, str(_Path(__file__).parent))
from config import BASE, LOGIN, PASSWORD, HEADLESS, DRY_RUN, TOP_N, STAKE, MAX_BETS_DAY, MIN_BANKROLL, browser_args
from core.odds import extract_odds, is_football  # re-export for compat
from core.ranking import analyze  # re-export
from core.reasons import build_reasons  # re-export

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("pip install playwright && playwright install chromium"); sys.exit(1)

def login(page):
    if not LOGIN.strip() or not PASSWORD.strip():
        raise ValueError("XBET_LOGIN dan XBET_PASSWORD wajib diisi melalui environment")
    page.goto(f"{BASE}/en", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    if page.evaluate("() => document.body.innerText.includes('My account') || document.cookie.includes('authenticated')"):
        print("[=] already logged in"); return
    for _ in range(3):
        try: page.get_by_text("Log in", exact=False).first.click(timeout=5000); break
        except: time.sleep(1)
    try: page.wait_for_selector("#modals-container", state="attached", timeout=10000)
    except: pass
    page.wait_for_timeout(1200)
    try: page.wait_for_selector("input#username", timeout=8000)
    except:
        try: page.get_by_text("Log in", exact=False).first.click(timeout=3000)
        except: pass
        page.wait_for_timeout(1000)
    try: page.locator("#modals-container").get_by_text("By email / ID", exact=True).click(timeout=5000)
    except: page.evaluate("()=>{const e=[...document.querySelectorAll('span')].find(s=>s.textContent.trim()==='By email / ID'); if(e) e.click()}")
    time.sleep(0.5)
    page.evaluate("([u,p]) => {const set=(sel,val)=>{const el=document.querySelector(sel); if(!el) return; el.focus(); const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; d.call(el,val); el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}; set('input#username',u); set('input#username-password',p); set('input[type=\"password\"]',p);}", [LOGIN, PASSWORD])
    time.sleep(0.4)
    page.evaluate("()=>{const d=document.querySelector('#modals-container'); const b=[...d.querySelectorAll('button')].find(b=>b.textContent.trim()==='Log in'); if(b) b.click();}")
    page.wait_for_timeout(4000)
    ok = page.evaluate("() => document.body.innerText.includes('My account') || document.cookie.includes('authenticated')")
    if not ok:
        print("[!] login not verified")
        raise SystemExit("login failed")
    print("[+] logged in")

def fetch_opportunities(page, count=40):
    # ponytail: count 40 stable; 60 sometimes empty by time-of-day, add retry
    qss = [
        dict(cfView=3, count=count, fcountry=72, gr=413, grMode=4, lng="en", ref=71),
        dict(cfView=3, count=40,  fcountry=72, gr=1,   grMode=4, lng="en", ref=71),
    ]
    all_games=[]
    for qs in qss:
        for kind in ("main-line-feed","main-live-feed"):
            url = f"{BASE}/service-api/{kind}/v3/games1x2?{urlencode(qs)}"
            try:
                data = page.evaluate("""async (u)=>{
  const c=new AbortController(); const t=setTimeout(()=>c.abort(),15000);
  try{
    const r=await fetch(u,{headers:{'accept':'application/json'},credentials:'include',signal:c.signal});
    const txt=await r.text();
    try{return JSON.parse(txt)}catch(e){return {raw:txt.slice(0,800),status:r.status,url:u}}
  }catch(e){return {raw:String(e).slice(0,800),status:0,url:u}}finally{clearTimeout(t)}
}""", url)
            except Exception as e:
                print("[!] fetch err", url, e); continue
            if isinstance(data, list):
                games=data
            elif isinstance(data, dict):
                if "raw" in data and "status" in data:
                    print(f"[!] non-json {data.get('status')} {str(data.get('raw'))[:120]}")
                    games=[]
                else:
                    games = data.get("Value") or data.get("value") or data.get("games") or data.get("data") or data.get("events") or []
                    if isinstance(games, dict): games=list(games.values())
                    if not games:
                        ks=list(data.keys())[:8]
                        print(f"[=] {kind} keys {ks} -> 0 games (gr={qs.get('gr')})")
                        games=[]
            else:
                games=[]
            print(f"[+] {kind} gr={qs.get('gr')} -> {len(games)} games")
            for g in games[:count]:
                all_games.append({"raw": g, "src": url})
        if len(all_games)>=5:
            break
    return all_games

def _ledger_path():
    import pathlib
    p = pathlib.Path(__file__).parent / "data" / "bets.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _ledger_read():
    """bets.jsonl append-only: list of dict. never overwritten."""
    import json as _j
    p = _ledger_path()
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line: continue
            try: out.append(_j.loads(line))
            except: pass
    return out

def _ledger_append(entry):
    import json as _j
    with open(_ledger_path(), "a", encoding="utf-8") as f:
        f.write(_j.dumps(entry, ensure_ascii=False) + "\n")

def _parse_saldo(page):
    """baca saldo IDR dari body. return float atau None."""
    try:
        body = page.inner_text("body")
        cands = []
        for pat in (r"IDR\s*([\d\s\.,]+)", r"([\d\s\.,]+)\s*IDR"):
            for m in re.finditer(pat, body, re.I):
                raw = m.group(1).replace(" ", "").replace("\u00a0", "")
                # "94,600.00" / "94 600.00" -> keep dot
                num = re.sub(r"[^\d.]", "", raw.replace(",", ""))
                # handle "94600.00" with two dots edge
                if num.count(".") > 1:
                    num = num.replace(".", "", num.count(".") - 1)
                try:
                    v = float(num)
                    if 1000 <= v <= 5_000_000:
                        cands.append(v)
                except Exception:
                    pass
        if cands:
            return max(cands)
    except Exception:
        pass
    return None


def _clear_slip(page):
    """hapus semua selection di bet slip + dismiss modal error stale. idempotent, no-op kalau kosong."""
    try:
        page.locator('button[aria-label="Clear bet slip"]').first.click(timeout=1500)
        page.wait_for_timeout(700)
    except Exception:
        pass
    try:
        page.locator('button[aria-label="Delete"]').first.click(timeout=800)
        page.wait_for_timeout(500)
    except Exception:
        pass
    try:
        page.locator("#modals-container button", has_text=re.compile(r"^(ok|close|cancel)$", re.I)).first.click(timeout=800)
    except Exception:
        pass

def _click_bet(page, rec, stake):
    """clear slip -> navigasi line page -> klik span.dashboard-markets__market (idx 1/X/2) di row match
    -> isi input.ui-number-input__field -> button 'Place a bet'. raise kalau gagal.
    ponytail: index pick 1/X/2 = 0/1/2 verified di DOM 1xBet; rebuild kalau market reorder."""
    title = rec.get("title", "")
    home, _, away = title.partition(" vs ")
    home = home.strip()
    away = away.split(" [")[0].strip()
    idx = {"1": 0, "X": 1, "2": 2}.get(str(rec.get("pick")), 0)
    page.goto(f"{BASE}/en/line/football", wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("li.dashboard-game span.dashboard-markets__market", timeout=20000)
    except Exception:
        page.wait_for_timeout(6000)
    page.wait_for_timeout(1500)
    _clear_slip(page)  # slip menumpuk antar bet -> server reject multi/parlay
    page.evaluate("""([h,a,i])=>{
  const n=s=>(s||'').toLowerCase().trim();
  const rows=[...document.querySelectorAll('li.dashboard-game')];
  const row=rows.find(r=>{const t=n(r.innerText); return h&&a&&t.includes(n(h))&&t.includes(n(a));});
  if(!row) throw new Error('row not found: '+h+' vs '+a+' ('+rows.length+' rows)');
  const m=row.querySelectorAll('span.dashboard-markets__market');
  if(!m[i]) throw new Error('market idx '+i+' missing ('+m.length+')');
  m[i].click();
}""", [home, away, idx])
    page.wait_for_timeout(2000)
    # stake: ketik keyboard nyata (React controlled input tak baca JS value set)
    stake_box = page.locator("input.ui-number-input__field").last
    stake_box.wait_for(state="visible", timeout=8000)
    stake_box.click()
    stake_box.fill("")
    stake_box.type(str(int(stake)), delay=40)
    # pastikan value terbaca React
    got = stake_box.input_value()
    if str(int(stake)) not in got:
        raise RuntimeError("stake input not set, val=" + got)
    page.wait_for_timeout(800)
    btn = page.locator("button", has_text=re.compile(r"place a bet", re.I)).last
    if btn.count() == 0:
        raise RuntimeError("Place a bet button not found")
    btn.click(timeout=5000)
    page.wait_for_timeout(3500)
    # verify: modal error (mis. min stake) atau slip kosong = sukses
    res = page.evaluate("""()=>{
  const modals=[...document.querySelectorAll('[class*="modal"],[class*="popup"],[class*="dialog"],[class*="notification"],[class*="message"]')]
    .map(e=>(e.innerText||'').trim()).filter(t=>t.length>3 && t.length<240);
  const err=modals.find(t=>/error|minimum|insufficient|not enough|reject|invalid|exceed|max/i.test(t));
  const sel=[...document.querySelectorAll('.coupon-bet-header,[class*="coupon-bet__"],[class*="betslip"] [class*="event"]')].length;
  const slip=[...document.querySelectorAll('[class*="coupon"],[class*="betslip"]')].map(e=>e.innerText||'').join(' ');
  const empty=sel===0 || /bet slip is empty|your bet slip is empty/i.test(slip);
  return {err:err||null, empty};
}""")
    if res.get("err"):
        raise RuntimeError("place rejected: " + res["err"].replace("\n", " ")[:180])
    if not res.get("empty"):
        raise RuntimeError("place unverified: slip not empty after place")

def place_bets(page, recs, dry_run=True, stake=None, max_day=MAX_BETS_DAY, min_bankroll=MIN_BANKROLL):
    """bet beneran semua rec yang lolos filter. append-only ledger, dedup, cap harian + cap bankroll."""
    import datetime, json as _j
    if not recs: print("[!] no recommendations"); return
    today = datetime.date.today().isoformat()
    led = _ledger_read()
    placed_ids = {str(e.get("game_id")) for e in led if str(e.get("status")) == "placed"}
    today_count = sum(1 for e in led if e.get("date") == today and str(e.get("status")) == "placed")
    st = int(stake or 0) or 8000
    allowed = max_day - today_count
    if allowed <= 0:
        print(f"[!] cap harian {max_day} tercapai, stop.")
        for rec in recs:
            gid = str(rec.get("game_id") or "").strip()
            base = dict(ts=time.time(), date=today, game_id=gid, event=rec.get("title", "?"),
                        league=rec.get("league"), pick=rec.get("pick"), odd=rec.get("odd"), stake=st)
            _ledger_append({**base, "status": "skip_cap"})
        return
    if not dry_run and min_bankroll and st > 0:
        saldo = _parse_saldo(page)
        if saldo is None:
            print("[!] bankroll guard: saldo tak terbaca, stop demi keamanan")
            for rec in recs:
                gid = str(rec.get("game_id") or "").strip()
                base = dict(ts=time.time(), date=today, game_id=gid, event=rec.get("title", "?"),
                            league=rec.get("league"), pick=rec.get("pick"), odd=rec.get("odd"), stake=st)
                _ledger_append({**base, "status": "skip_balance"})
            return
        _ledger_append({"ts": time.time(), "date": today, "status": "balance_read", "saldo": int(saldo)})
        affordable = int(max(0, (saldo - float(min_bankroll)) // st))
        allowed = min(allowed, affordable)
        if allowed <= 0:
            print(f"[!] stop: saldo {int(saldo)} setelah reserve {int(min_bankroll)} tak cukup untuk stake {st}")
            for rec in recs:
                gid = str(rec.get("game_id") or "").strip()
                base = dict(ts=time.time(), date=today, game_id=gid, event=rec.get("title", "?"),
                            league=rec.get("league"), pick=rec.get("pick"), odd=rec.get("odd"), stake=st)
                _ledger_append({**base, "status": "skip_funds", "saldo": int(saldo)})
            return
        if allowed < max_day - today_count:
            print(f"[!] bankroll guard: saldo {int(saldo)} - reserve {int(min_bankroll)} = {int(saldo - min_bankroll)} -> max {allowed} bet lagi")
    recs = recs[:allowed]
    for i, rec in enumerate(recs, 1):
        gid = str(rec.get("game_id") or "").strip()
        title = rec.get("title", "?")
        base = dict(ts=time.time(), date=today, game_id=gid, event=title,
                    league=rec.get("league"), pick=rec.get("pick"),
                    odd=rec.get("odd"), stake=st)
        if dry_run:
            print(f"[DRY] {i}. {title[:44]} pick={rec['pick']} @{rec['odd']} stake={st}")
            continue
        if gid and gid in placed_ids:
            print(f"[=] skip dup {title[:44]} id={gid}"); _ledger_append({**base, "status": "skip_dup"}); continue
        if today_count >= max_day:
            print(f"[!] cap harian {max_day} tercapai, stop."); _ledger_append({**base, "status": "skip_cap"}); break
        try:
            _click_bet(page, rec, st)
            _ledger_append({**base, "status": "placed"})
            placed_ids.add(gid); today_count += 1
            print(f"[+] LIVE bet {i}. {title[:44]} pick={rec['pick']} @{rec['odd']} stake={st}")
        except Exception as e:
            _ledger_append({**base, "status": "fail", "error": str(e)[:200]})
            print(f"[!] bet fail {title[:44]}: {e}")
        page.wait_for_timeout(2500)

def append_log(recs):
    import csv, datetime, pathlib
    p = pathlib.Path(__file__).parent / "data" / "log.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    # header with kickoff_wib (GMT+7)
    HDR=["date","game_id","league","event","kickoff_wib","pick","odd","prob","gap","margin","risk","kelly","ev","stake","reasons","result","score"]
    # migrate old log without kickoff_wib
    if p.exists() and p.stat().st_size>0:
        try:
            with open(p, encoding="utf-8", newline="") as _f:
                hdr=_f.readline().strip().split(",")
                if "kickoff_wib" not in hdr:
                    rows=list(csv.DictReader(open(p, encoding="utf-8", newline="")))
                    with open(p,"w",newline="",encoding="utf-8") as wf:
                        w=csv.DictWriter(wf, fieldnames=HDR)
                        w.writeheader()
                        for r in rows:
                            r.setdefault("kickoff_wib","")
                            w.writerow({k:r.get(k,"") for k in HDR})
        except: pass
    new = not p.exists() or p.stat().st_size==0
    existing=set()
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    gid=str(row.get("game_id") or "").strip()
                    if gid: existing.add(gid)
                    else:
                        existing.add((row.get("league") or "")+"|"+(row.get("event") or ""))
        except: pass
    with open(p, "a", newline="", encoding="utf-8") as f:
        w=csv.writer(f)
        if new: w.writerow(HDR)
        today=datetime.date.today().isoformat()
        n=0
        for rec in recs:
            gid=str(rec.get("game_id") or "").strip()
            key=gid if gid else (rec.get("league") or "")+"|"+rec["title"]
            if key in existing: print(f"[=] already logged {rec['title']} id={gid}"); continue
            reasons=" | ".join(rec["reasons"][:4])
            w.writerow([today, rec.get("game_id"), rec.get("league"), rec["title"], rec.get("kickoff_wib",""), rec["pick"], rec["odd"], rec["prob"], rec["gap"], rec["margin"], rec["risk"], rec["kelly"], rec["ev"], rec["stake"], reasons, "", ""])
            n+=1
        if n: print(f"[+] appended {n} to {p}")

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS, args=browser_args())
        try:
            ctx = browser.new_context(locale="en-US")
            page = ctx.new_page()
            login(page)
            games = fetch_opportunities(page, count=40)
            print(f"[+] total games fetched: {len(games)}", flush=True)
            try:
                _hits = _Path(__file__).parent / "data" / "hits.jsonl"
                _hits.parent.mkdir(parents=True, exist_ok=True)
                with open(_hits, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": time.time(), "games": games}) + "\n"); fh.flush()
            except Exception as e: print("[!] hits", e)
            ranked = analyze(games, page=page)
            print(f"[+] ranked Top{len(ranked)} football", flush=True)
            for i,r in enumerate(ranked[:TOP_N],1):
                print(f" #{i} {r['title'][:50]:50} pick={r['pick']} odd={r['odd']} p={r['prob']} gap={r['gap']} risk={r['risk']} ev={r['ev']}")
                for rs in r["reasons"][:3]: print("    -", rs[:140])
            best = ranked[:TOP_N]
            if best:
                out=[{k:v for k,v in b.items() if k!="raw"} for b in best]
                out_path = _Path(__file__).parent / "recommendation.json"
                with open(out_path,"w",encoding="utf-8") as f: json.dump(out, f, indent=2, ensure_ascii=False)
                print(f"[+] saved {out_path} (Top {len(out)})")
                append_log(best)
            # bet BENERAN: semua lolos filter (Top N), 1000/match, ledger append-only
            if best: place_bets(page, best, dry_run=DRY_RUN, stake=STAKE)
            if DRY_RUN: page.wait_for_timeout(2000)
        finally:
            try: browser.close()
            except: pass

if __name__ == "__main__":
    main()

# self-check feed v3 football 1X2 groupId 1
assert extract_odds({"raw":{"eventGroups":[{"groupId":1,"events":[[{"cf":3.36}],[{"cf":3.15}],[{"cf":2.3}]]}]}}) == {"1":3.36,"X":3.15,"2":2.3}
assert extract_odds({"raw":{"eventGroups":[{"groupId":101,"events":[[{"cf":1.6}],[{"cf":2.4}]]}]}}) == {"1":1.6,"2":2.4}
