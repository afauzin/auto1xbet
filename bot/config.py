import os
BASE = os.getenv("XBET_BASE", "https://1x-bet-indian.com")
LOGIN = os.getenv("XBET_LOGIN", "")
PASSWORD = os.getenv("XBET_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "0") == "1"
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
STAKE = float(os.getenv("STAKE", "8000"))  # 1xBet min stake IDR 8000
MAX_ODD = float(os.getenv("MAX_ODD", "2.00"))
MIN_ODD = float(os.getenv("MIN_ODD", "1.12"))
BANKROLL = float(os.getenv("BANKROLL", "100000"))
TOP_N = int(os.getenv("TOP_N", "5"))
# guard uang nyata: max bet live / hari + min bankroll sisa
MAX_BETS_DAY = int(os.getenv("MAX_BETS_DAY", "100"))
MIN_BANKROLL = float(os.getenv("MIN_BANKROLL", "10000"))

# ponytail: DNS ISP Indonesia hijack 1xBet domains (redirect ke halaman blokir) ->
# resolve host via DoH Cloudflare lalu paksa Chromium pakai IP itu (SNI tetap asli).
_DOH_CACHE = {}
def _resolve_via_doh(host):
    if host in _DOH_CACHE: return _DOH_CACHE[host]
    import urllib.request, json as _j
    ip = None
    for ep in ("https://1.1.1.1/dns-query", "https://dns.google/resolve"):
        try:
            req = urllib.request.Request(f"{ep}?name={host}&type=A", headers={"accept": "application/dns-json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                d = _j.loads(r.read().decode())
            for a in d.get("Answer", []):
                if a.get("type") == 1: ip = a["data"]; break
        except Exception: pass
        if ip: break
    _DOH_CACHE[host] = ip
    return ip

def browser_args():
    from urllib.parse import urlparse
    args = ["--no-sandbox", "--disable-dev-shm-usage"]  # container-friendly
    proxy = os.getenv("XBET_PROXY", "").strip()
    if proxy:
        # gateway rotating: DNS hijack tak relevan (resolve dilakukan proxy), MAP host->IP malah bikin SNI rusak
        return args + [f"--proxy-server={proxy}"]
    try: host = urlparse(BASE).hostname
    except Exception: host = None
    if not host: return args
    ip = _resolve_via_doh(host)
    return args + ([f"--host-resolver-rules=MAP {host} {ip}"] if ip else [])
