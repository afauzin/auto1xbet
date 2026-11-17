import json, re, unicodedata, time
from pathlib import Path
from . import http

# beyondELO public dataset (CSV, no key) — semua klub UEFA, satu fetch.
# kolom: rank,country_rank,slug,name,country_code,elo,rd,hfa,is_ranked,last_match_date,as_of
_SRC = "https://public-api.beyondelo.com/v1/datasets/club-ratings.csv"
_GENERIC = {"fc", "cf", "sc", "ac", "afc", "sv", "club", "if"}
# tabel besar disimpan di file SENDIRI (bukan analytics_cache.json) supaya
# _cache_set lain tak menulis-ulang 1472 baris tiap kali.
_TABLE_PATH = Path(__file__).parent.parent / "data" / "elo_ratings.json"
_ROWS_TTL = 6 * 3600
_ROWS_MEM = None


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def _parse_rows(txt):
    rows = []
    for line in (txt or "").splitlines()[1:]:
        p = line.split(",")
        if len(p) < 7:
            continue
        try:
            elo = float(p[5])
        except ValueError:
            continue
        ranked = len(p) > 8 and p[8].strip().lower() == "true"
        rows.append([p[3].strip(), p[2].strip(), elo, ranked])
    return rows


def _rows():
    global _ROWS_MEM
    if _ROWS_MEM:
        return _ROWS_MEM
    try:
        if _TABLE_PATH.exists():
            d = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
            if d.get("rows") and time.time() - d.get("ts", 0) < _ROWS_TTL:
                _ROWS_MEM = d["rows"]
                return _ROWS_MEM
    except Exception:
        pass
    rows = _parse_rows(http.fetch_csv(_SRC))
    if rows:
        _TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _TABLE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ts": time.time(), "rows": rows}), encoding="utf-8")
        tmp.replace(_TABLE_PATH)
        _ROWS_MEM = rows
    return rows


def _match(name, rows):
    n = _norm(name)
    if not n:
        return None
    nt = set(n.split()) - _GENERIC
    best = None
    best_score = 0.0
    for nm, slug, elo, ranked in rows:
        if n == _norm(nm) or n == _norm(slug):
            return (nm, elo, ranked)
        ct = set(_norm(nm).split()) - _GENERIC
        if nt and ct:
            inter = len(nt & ct)
            if inter:
                score = inter / max(len(nt | ct), 1)
                if score > best_score:
                    best_score = score
                    best = (nm, elo, ranked)
    return best if best_score >= 0.5 else None


def get_elo(name):
    key = f"elo_beyond:{_norm(name)}"
    hit = http._cache_get(key)
    if hit and "elo" in hit:
        return hit
    try:
        m = _match(name, _rows())
    except Exception:
        m = None
    if not m:
        res = dict(source="none", elo=None)
    else:
        nm, elo, ranked = m
        res = dict(source="beyondelo", elo=round(elo, 1), team=nm, ranked=ranked)
    http._cache_set(key, res)
    return res


def elo_prob(a, b):
    if a is None or b is None:
        return None
    return 1 / (1 + 10 ** (-(a - b) / 400))


__all__ = ["get_elo", "elo_prob"]
