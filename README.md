# 1xBet Bot

Bot Python untuk login, mengambil pasar sepak bola, memilih rekomendasi, mencatat hasil, dan (jika diaktifkan) memasang taruhan. Tidak ada jaminan keuntungan. `DRY_RUN=1` mencegah pemasangan taruhan, tetapi tetap melakukan login, akses jaringan, dan penulisan data.

## Struktur

- `bot/bot.py`: login, scan, rekomendasi, pencatatan, pemasangan taruhan.
- `bot/config.py`: konfigurasi dari environment.
- `bot/core/`: odds, ranking, alasan rekomendasi.
- `bot/_analytics/`: sumber data dan pengayaan; `fotmob_map.json` merupakan peta sumber yang tetap disertakan.
- `bot/tools/`: settle, laporan, simulasi, status, runner, pemasangan jadwal Windows.
- `bot/data/`: data runtime privat, termasuk ledger `bets.jsonl`, riwayat `log.csv`, cache, laporan, dan sesi.
- `bot/recommendation.json`: hasil scan, bukan source.
- `Dockerfile` dan `run_loop.sh`: instalasi dan loop Docker.
- `doctor.py`: pemeriksaan dependensi, browser, konfigurasi, dan data.

## Instalasi baru dengan Docker

Jalankan dari folder `1xbet`, memakai Docker Desktop. Jangan jalankan prosedur ini untuk menimpa instalasi atau container aktif.

1. Salin `.env.example` menjadi `.env` hanya jika `.env` belum ada. Isi `XBET_LOGIN` dan `XBET_PASSWORD`. Gunakan nilai tanpa komentar inline. Pertahankan `DRY_RUN=1` saat pengujian.
2. Build image:
   ```powershell
   docker build -t xbet-bot .
   ```
3. Jalankan instalasi baru dengan data persisten:
   ```powershell
   docker run -d --name xbet-bot-new --env-file .env -e DRY_RUN=1 --mount "type=bind,source=$($PWD.Path)\bot\data,target=/app/bot/data" xbet-bot
   docker logs --tail 80 xbet-bot-new
   ```
   Folder `bot/data` harus sudah ada. Untuk salinan source tanpa folder tersebut, buat folder kosong dahulu. Jangan gunakan folder data yang sedang dipakai bot lain. `recommendation.json` berada di filesystem container, bukan bind mount data.

Default image: `HEADLESS=1`, `TZ=Asia/Jakarta`. Loop langsung menjalankan `settle.py`, `bot.py`, lalu `status.py`; setelah itu tidur `SCAN_INTERVAL` detik (default `21600`, enam jam). Siklus berikutnya dimulai setelah waktu proses ditambah jeda ini. Loop bukan jadwal Windows, tidak menjalankan simulasi atau `runner.py` otomatis. Kegagalan satu langkah tidak menghentikan loop.

**Perhatian:** loop membaca `DRY_RUN` dari environment. `DRY_RUN=0` dapat langsung memasang taruhan. Tidak ada penguncian otomatis berdasarkan kelulusan gate laporan atau simulasi.

## Konfigurasi

| Variabel | Default source | Keterangan |
|---|---|---|
| `XBET_LOGIN`, `XBET_PASSWORD` | kosong | Wajib sebelum login |
| `XBET_BASE` | `https://1x-bet-indian.com` | Domain situs |
| `XBET_PROXY` | kosong | Proxy Chromium opsional |
| `DRY_RUN` | `1` | Hanya nilai `1` mengaktifkan dry-run |
| `HEADLESS` | `0` (image: `1`) | Browser tanpa jendela jika `1` |
| `STAKE` | `8000` | Nominal per taruhan |
| `MIN_ODD`, `MAX_ODD` | `1.12`, `2.00` | Rentang odds |
| `BANKROLL` | `100000` | Parameter perhitungan, bukan saldo akun |
| `TOP_N` | `5` | Batas rekomendasi |
| `MAX_BETS_DAY` | `100` | Batas taruhan live harian berdasarkan ledger |
| `MIN_BANKROLL` | `10000` | Cadangan saldo untuk guard live |
| `SCAN_INTERVAL` | `21600` | Jeda loop Docker, detik |

Nilai ini bukan pembacaan konfigurasi live. Guard saldo dan ledger tidak menjamin terhindar dari kerugian. Jangan hilangkan ledger saat melanjutkan instalasi lama.

`ODDSPAPI_KEY` opsional. Ketersediaan data eksternal dapat berubah.

## Alternatif lokal dan perawatan

Python 3.10+ diperlukan. Dari folder `1xbet`:

```powershell
py -m pip install -r requirements.txt
py -m playwright install chromium
py doctor.py
```

`doctor.py` meluncurkan Chromium untuk pemeriksaan; bukan pengujian taruhan. Pemeriksaan `.env` tidak berarti seluruh konfigurasi sudah dimuat oleh `config.py`: konfigurasi bot dibaca saat import, jadi ekspor environment sebelum menjalankan bot lokal. Docker memakai `--env-file` untuk memasukkannya sejak proses dimulai.

Perintah berikut dipakai sesuai kebutuhan, bukan dijalankan otomatis saat instalasi:

```powershell
py bot/tools/report.py
py bot/tools/simulate.py
py bot/tools/runner.py --job scan
py bot/tools/runner.py --job settle
py bot/tools/runner.py --job report
```

`report.py` membaca riwayat; simulasi menulis laporan di `bot/data`. Runner menulis log ke `bot/data/runner.log`. `--job scan` memakai dry-run dan melakukan settle terlebih dahulu; settle mengakses jaringan dan memperbarui riwayat. Scheduler Windows opsional ada di `bot/tools/setup_scheduler_opsi1.ps1`; jangan aktifkan bersamaan dengan loop Docker untuk data yang sama.

Laporan cepat tanpa mengubah data:

```powershell
py bot/tools/status.py
```

Menampilkan bet aktif menurut ledger, sepuluh hasil terakhir, dan saldo terakhir yang benar-benar terbaca bot. Daftar aktif belum diverifikasi ke bandar.

## Berbagi dan menjaga data

Bagikan source, `.env.example`, `requirements.txt`, dan file build; bukan salinan mentah folder kerja. `.env`, `bot/data/`, dan `bot/recommendation.json` sudah dihapus dari indeks Git (file lokal tetap ada); `.gitignore` dan `.dockerignore` mencegahnya masuk lagi. Aturan ini tidak menyaring salinan Explorer atau ZIP manual.

Jangan bagikan `.env`, variannya, `*.session*`, seluruh `bot/data/`, `bot/recommendation.json`, log, backup, atau cache. Simpan backup privat `.env` dan seluruh `bot/data/` untuk pemulihan, terutama ledger/riwayat dan sesi. Jangan menghapus data untuk merapikan source.

Kredensial pernah muncul di source/dokumentasi. `endpoints.md` sudah disensor, tetapi rotasi password dan token/API key lama tetap wajib; penyensoran file tidak menghapus salinan atau riwayat Git terdahulu. Log lama juga perlu diperlakukan sebagai data privat.

`endpoints.md` merupakan referensi hasil observasi lama; domain dan endpoint perlu diverifikasi sebelum dipakai. Setup dan perintah aktif dijelaskan di README ini.
