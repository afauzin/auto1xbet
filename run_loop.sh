#!/bin/sh
# loop 6 jam: settle hasil lama -> scan -> pasang bet. gagal 1 siklus tidak mematikan container.
set -u
INTERVAL="${SCAN_INTERVAL:-21600}"
while :; do
  echo "=== $(date -u '+%F %T UTC') settle ==="
  python bot/tools/settle.py || echo "[!] settle gagal, lanjut"
  echo "=== $(date -u '+%F %T UTC') scan+bet ==="
  python bot/bot.py || echo "[!] scan gagal, lanjut"
  echo "=== laporan status ==="
  python bot/tools/status.py || echo "[!] status gagal"
  echo "=== tidur ${INTERVAL}s ==="
  sleep "$INTERVAL"
done
