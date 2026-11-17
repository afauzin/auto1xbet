#!/usr/bin/env python3
"""Doctor — preflight check sebelum pasang di PC baru. stdlib only.
Usage:
  py 1xbet/doctor.py               # cek lokal
  py 1xbet/doctor.py --json        # output JSON
  py 1xbet/doctor.py --fix         # tulis missing files kosong (log.csv header, analytics.json)
Exit 0 = ok (boleh pasang scheduler), 2 = ada blocker.
"""
import sys, os, json, pathlib, shutil, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOT = ROOT / "bot"
DATA = BOT / "data"
ENV = ROOT / ".env"
ENV_EX = ROOT / ".env.example"

def _has(mod): return importlib.util.find_spec(mod) is not None

def check():
    issues = []  # (level, msg) level=block|warn
    info = {}
    # python
    info["python"] = sys.version.split()[0]
    if sys.version_info < (3,10):
        issues.append(("block", f"Python {info['python']} < 3.10 — upgrade"))
    # pip deps
    has_pw = _has("playwright")
    info["playwright"] = has_pw
    if not has_pw: issues.append(("block", "playwright belum install — py -m pip install playwright && py -m playwright install chromium"))
    # chromium
    if has_pw:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                b.close()
            info["chromium"] = True
        except Exception as e:
            info["chromium"] = False
            info["chromium_err"] = str(e)[:400]
            issues.append(("block", f"Chromium belum terpasang — py -m playwright install chromium ({e})"))
    else:
        info["chromium"] = None
    # env
    env = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k,v = line.strip().split("=",1)
                env[k.strip()] = v.strip()
    else:
        if ENV_EX.exists():
            issues.append(("block", ".env belum ada — copy .env.example -> .env lalu isi token (lihat README)"))
        else:
            issues.append(("block", ".env tidak ada"))
    info["env_path"] = str(ENV)
    # required keys
    for k in ("XBET_LOGIN", "XBET_PASSWORD"):
        if not (os.environ.get(k) or env.get(k, "")).strip():
            issues.append(("block", f"{k} kosong, isi environment atau .env"))
    # data files
    info["log_csv"] = (DATA / "log.csv").exists()
    info["sim_report"] = (DATA / "sim_report.json").exists()
    if not (DATA / "log.csv").exists():
        issues.append(("warn", "log.csv belum ada — scan pertama akan buat otomatis; simulate butuh minimal 1 pick"))
    # requirements
    info["requirements"] = (ROOT / "requirements.txt").exists()
    if not (ROOT / "requirements.txt").exists():
        issues.append(("warn","requirements.txt tidak ada — buat: playwright==1.62.0"))
    # gitignore secrets
    gi = ROOT / ".gitignore"
    root_gi = ROOT.parent / ".gitignore"
    txt = ""
    for p in (gi, root_gi):
        if p.exists():
            try: txt += p.read_text(encoding="utf-8", errors="ignore") + "\n"
            except: pass
    if ".env" not in txt: issues.append(("warn",".gitignore belum mengignore .env — risiko bocor secrets ke git"))
    # task scheduler detection
    info["scheduler_exists"] = False
    if os.name=="nt":
        try:
            import subprocess
            r = subprocess.run(["schtasks","/query","/tn","1xbet-scan-0900"], capture_output=True, text=True, timeout=5)
            info["scheduler_exists"] = (r.returncode==0)
        except: pass
    return info, issues

def main():
    as_json = "--json" in sys.argv
    do_fix = "--fix" in sys.argv
    info, issues = check()
    if do_fix:
        DATA.mkdir(parents=True, exist_ok=True)
        log = DATA / "log.csv"
        if not log.exists():
            log.write_text("timestamp,date,game_id,league,title,pick,odd,prob,gap,margin,EV,kelly,stake,result,score\n", encoding="utf-8")
            print(f"created {log}")
        aj = DATA / "analytics.json"
        if not aj.exists():
            aj.write_text("{}\n", encoding="utf-8")
            print(f"created {aj}")
        # recheck
        info, issues = check()
    blocks = [m for lvl,m in issues if lvl=="block"]
    warns = [m for lvl,m in issues if lvl=="warn"]
    if as_json:
        print(json.dumps({"info":info,"blocks":blocks,"warns":warns,"ok":len(blocks)==0}, indent=2, ensure_ascii=False))
    else:
        print(f"Python {info.get('python')} | playwright={info.get('playwright')} chromium={info.get('chromium')}")
        print(f"env: {info.get('env_path')} exists={Path(info.get('env_path','')).exists()} | scheduler={info.get('scheduler_exists')}")
        if blocks:
            print("\n[BLOCK] harus diperbaiki sebelum pasang scheduler:")
            for m in blocks: print(f"  - {m}")
        if warns:
            print("\n[WARN] tidak blokir, tapi perbaiki:")
            for m in warns: print(f"  - {m}")
        if not blocks and not warns:
            print("\n[OK] siap pasang — jalankan: powershell -ExecutionPolicy Bypass -File \"bot/tools/setup_scheduler_opsi1.ps1\"")
        elif not blocks:
            print("\n[OK-WARN] boleh pasang, tapi cek WARN di atas")
        else:
            print(f"\n[FAIL] {len(blocks)} blocker — perbaiki dulu, lalu py 1xbet/doctor.py lagi")
    sys.exit(0 if not blocks else 2)

if __name__=="__main__": main()
