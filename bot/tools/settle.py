#!/usr/bin/env python3
"""settle.py — settle pending log.csv dari halaman /en/office/history (butuh login).
Sumber paling akurat: status Win/Loss langsung dari 1xBet (bukan scrape skor).
ponytail: history cuma window periode terbatas; kalau match >30 hari hilang, tambah filter tanggal.
"""
import csv, pathlib, re, sys

LOG = pathlib.Path(__file__).parent.parent / "data" / "log.csv"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from config import BASE, browser_args, HEADLESS  # noqa: E402
from bot import login  # noqa: E402


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def parse_history(body):
    """{norm(home)+norm(away): 'W'|'L'} dari teks halaman bet history."""
    out = {}
    # blok: "<Home> - <Away>\n\n<League>\n\n<Status>"
    for m in re.finditer(r"\n([^\n]+?) - ([^\n]+)\n\n([^\n]+)\n\n(Win|Loss|Returned|Void|Pending)\n", body):
        home, away, _lg, st = m.groups()
        key = _norm(home) + _norm(away)
        out[key] = {"Win": "W", "Loss": "L"}.get(st, "")
    return out


def main():
    if not LOG.exists():
        print(f"[!] {LOG} tidak ada"); return
    rows = list(csv.DictReader(open(LOG, encoding="utf-8")))
    pending = [r for r in rows if not (r.get("result") or "").strip()]
    print(f"total {len(rows)} pending {len(pending)}")
    if not pending:
        print("tidak ada yang perlu di-settle")
        settle_ledger({r["game_id"]: r for r in rows if (r.get("result") or "").strip()})
        return

    from playwright.sync_api import sync_playwright
    body = ""
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=HEADLESS, args=browser_args())
        try:
            pg = br.new_context(locale="en-US").new_page()
            login(pg)
            pg.goto(f"{BASE}/en/office/history", wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(10000)
            body = pg.inner_text("body")
        finally:
            br.close()

    res = parse_history(body)
    print(f"[=] history memuat {len(res)} hasil")
    if not res:
        print("[!] tidak ada result di halaman history — login gagal atau periode kosong.")
        return

    n = 0
    for r in pending:
        ev = r.get("event", "")
        home, _, rest = ev.partition(" vs ")
        away = rest.split(" [")[0].strip()
        key = _norm(home) + _norm(away)
        r_res = res.get(key)
        if not r_res:
            continue
        r["result"] = r_res
        r["score"] = ""
        n += 1
        print(f"  settled {ev[:52]:52} => {r_res}")

    if not n:
        print("[!] tidak ada match pending baru yang cocok di history.")
        settle_ledger({r["game_id"]: r for r in rows if (r.get("result") or "").strip()})
        return

    fieldnames = list(rows[0].keys())
    if "score" not in fieldnames:
        fieldnames.append("score")
    tmp = LOG.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(LOG)
    print(f"[+] updated {LOG} ({n} settled)")

    settle_ledger({r["game_id"]: r for r in rows if (r.get("result") or "").strip()})


def settle_ledger(done):
    """append baris 'settled_won'/'settled_lost' ke bets.jsonl (append-only).
    dedup di place_bets hanya baca status 'placed', jadi aman — baris placed tetap ada."""
    import json
    p = pathlib.Path(__file__).parent.parent / "data" / "bets.jsonl"
    if not p.exists() or not done:
        return
    led = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                led.append(json.loads(line))
            except Exception:
                pass
    already = {e.get("game_id") for e in led if str(e.get("status", "")).startswith("settled")}
    n = 0
    with open(p, "a", encoding="utf-8") as f:
        for e in led:
            gid = str(e.get("game_id"))
            if str(e.get("status")) != "placed" or gid in already or gid not in done:
                continue
            res = done[gid]["result"]
            stake, odd = float(e.get("stake") or 0), float(e.get("odd") or 0)
            payout = round(stake * odd) if res == "W" else 0
            f.write(json.dumps({**e, "status": "settled_won" if res == "W" else "settled_lost",
                                "result": res, "payout": payout}, ensure_ascii=False) + "\n")
            n += 1
    print(f"[+] ledger: {n} bet di-settle")


if __name__ == "__main__":
    main()
