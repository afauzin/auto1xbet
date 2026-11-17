#!/usr/bin/env python3
"""runner.py: opsi1 08:00 settle, 09:00/13:00/18:00/21:00 scan. stdlib only. ponytail: APScheduler add when need sub-hour jitter"""
import argparse, subprocess, sys, pathlib, datetime, os

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOG = DATA / "runner.log"
def _find_py():
    import shutil
    for c in ("py","python","python3"):
        if shutil.which(c): return c
    return "py"
PY = _find_py()

def _log(msg):
    DATA.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(line+"\n")
    except: pass

def run_scan(dry_run=True, bet=False):
    try: run_settle()
    except: pass
    _log(f"scan start dry_run={dry_run}")
    env = os.environ.copy()
    env["DRY_RUN"]="1" if dry_run else "0"
    env["HEADLESS"]="1"
    base = pathlib.Path(__file__).resolve().parents[2]
    cmd = [PY, "-u", str(ROOT / "bot.py")]
    try:
        r = subprocess.run(cmd, cwd=str(base), env=env, capture_output=True, text=True, timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        _log(out[-4000:])
        if r.returncode != 0:
            _log(f"scan exit {r.returncode}")
            return False
        _log("scan ok")
        return True
    except Exception as e:
        _log(f"scan err {e}")
        return False

def run_daily(live=False):
    """sehari sekali 09:00: settle hasil kemarin -> scan pertandingan baru -> simulate -> bet."""
    _log(f"daily start live={live}")
    ok = run_scan(dry_run=not live, bet=live)
    try: run_report()
    except Exception as e: _log(f"daily report err {e}")
    _log(f"daily done ok={ok}")
    return ok

def run_settle():
    _log("settle start")
    base = pathlib.Path(__file__).resolve().parents[2]
    r = subprocess.run([PY, str(ROOT / "tools" / "settle.py")], cwd=str(base), capture_output=True, text=True, timeout=180)
    out=(r.stdout or "")+(r.stderr or "")
    _log(out[-4000:])
    if r.returncode!=0: _log(f"settle exit {r.returncode}")
    else: _log("settle ok")
    return r.returncode==0

def run_report():
    _log("report start")
    base = pathlib.Path(__file__).resolve().parents[2]
    for script in ["tools/report.py","tools/simulate.py"]:
        r=subprocess.run([PY, str(ROOT / script)], cwd=str(base), capture_output=True, text=True, timeout=60)
        out=(r.stdout or "")+(r.stderr or "")
        _log(f"{script}: {out[-2000:]}")
    _log("report ok")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--job", choices=["scan","settle","report","simulate","daily"], required=True)
    ap.add_argument("--live", action="store_true", help="daily: bet beneran (default dry-run)")
    args=ap.parse_args()
    if args.job=="scan": sys.exit(0 if run_scan() else 1)
    elif args.job=="settle": sys.exit(0 if run_settle() else 1)
    elif args.job=="report": run_report()
    elif args.job=="simulate": run_report()
    elif args.job=="daily": sys.exit(0 if run_daily(live=args.live) else 1)

if __name__=="__main__":
    main()
