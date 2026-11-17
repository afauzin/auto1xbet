#!/usr/bin/env python3
"""status.py — bet aktif, 10 hasil terakhir, saldo terakhir dibaca bot. baca bets.jsonl append-only."""
import json, pathlib

LEDGER = pathlib.Path(__file__).parent.parent / "data" / "bets.jsonl"


def main():
    rows = []
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except Exception: pass
    cur = {}
    for r in rows:
        gid = str(r.get("game_id"))
        # skip_* cuma catatan info — jangan overwrite status placed/settled yang sudah ada
        if str(r.get("status", "")).startswith("skip_"):
            cur.setdefault(gid, r)
            continue
        cur[str(r.get("game_id"))] = r  # append-only: baris terakhir non-skip = status terkini
    active = sorted((r for r in cur.values() if r.get("status") == "placed"), key=lambda r: r.get("ts", 0))
    settled = sorted((r for r in cur.values() if str(r.get("status", "")).startswith("settled")), key=lambda r: r.get("ts", 0))
    won = [r for r in settled if r.get("status") == "settled_won"]

    print(f"AKTIF LEDGER {len(active)} (belum diverifikasi di My bets; stake tercatat {sum(int(r.get('stake') or 0) for r in active):,})")
    for r in active:
        print(f"  {r.get('date')} {r.get('event', '')[:46]:46} {r.get('pick')} @{r.get('odd')}")

    print(f"\nHASIL {len(settled)}  W {len(won)} / L {len(settled) - len(won)}  payout {sum(int(r.get('payout') or 0) for r in won):,}")
    for r in settled[-10:]:
        tag = "WIN " if r.get("status") == "settled_won" else "LOSS"
        print(f"  {r.get('date')} {tag} {r.get('event', '')[:46]:46} @{r.get('odd')} payout {int(r.get('payout') or 0):,}")

    balances = [r for r in rows if r.get("status") == "balance_read" and r.get("saldo") is not None]
    if balances:
        last = balances[-1]
        from datetime import datetime, timezone
        when = datetime.fromtimestamp(last["ts"], timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        print(f"\nSALDO terakhir terbaca {int(last['saldo']):,} pada {when} (bukan saldo real-time)")
    else:
        print("\nSALDO: belum ada pembacaan tersimpan")



if __name__ == "__main__":
    main()
