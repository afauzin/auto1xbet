#!/usr/bin/env python3
"""build_dataset — join log+analytics+hits → dataset.csv ponytail: ML when 300+ settled"""
import csv, json, pathlib
LOG=pathlib.Path(__file__).parent.parent/"data/log.csv"
ANA=pathlib.Path(__file__).parent.parent/"data/analytics.json"
OUT=pathlib.Path(__file__).parent.parent/"data/dataset.csv"
def main():
    if not LOG.exists(): print("no log"); return
    rows=list(csv.DictReader(open(LOG, encoding="utf-8")))
    print(f"rows {len(rows)} -> {OUT} (stub, need 300+ settled)")
if __name__=="__main__": main()
