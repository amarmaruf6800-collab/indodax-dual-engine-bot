# INDODAX DUAL ENGINE — MULTI-ASSET & ACTIVE RESERVE DEPLOYMENT
**Version:** V5.3-MACO R3  
**Market:** Indodax IDR Spot  
**Operating Mode:** PAPER_TRADING  
**Live Trading:** DISABLED (`LIVE_TRADING_ENABLED = False`)  
**Strategy:** Pure Scalping (Engine A) + Extreme Momentum Hunter (Engine B)  
**DCA / Martingale / Leverage:** STRICTLY DISABLED  

---

## 📌 Deskripsi Sistem

**INDODAX DUAL ENGINE V5.3-MACO R3** adalah sistem bot trading otomatis multi-asset yang dirancang khusus untuk pasar IDR Spot Indodax. Bot ini menggabungkan dua mesin trading independen (**Engine A: Pure Scalper** dan **Engine B: Extreme Momentum Hunter**) dengan pengendali risiko portofolio terpusat (**Portfolio Risk Controller**) dan manajemen modal cadangan aktif (**Active Reserve Deployment**).

---

## ⚙️ Fitur Utama & Arsitektur Sistem

### 1. Engine A — Pure Scalping
- **Timeframe:** 1 minute, 5 minutes, 15 minutes.
- **Indikator:** EMA 9, EMA 21, ATR 14, Relative Volume (RVOL), Price Rate of Change (ROC), Candlestick Momentum, Breakout & Retest.
- **Fitur Eksekusi:** Menghitung Bid/Ask spread, kedalaman order book yang executable, serta menyaring transaksi berdasarkan estimasi net return setelah biaya (taker 0.2%, maker 0.1%, slippage).
- **Exit Strategy:** Adaptive take-profit, volatility & structure stop-loss, trailing stop dinamis, dan momentum reversal exit (EMA cross).

### 2. Engine B — Extreme Momentum Hunter
- **Timeframe:** 15 minutes, 1 hour, 4 hours, 1 day.
- **Sistem Scoring Momentum (0 - 100 Poin):**
  - Relative Volume: max 20 poin
  - Breakout Quality: max 20 poin
  - Volatility Expansion: max 15 poin
  - Trend Structure (HH/HL): max 15 poin
  - Order-book Quality: max 15 poin
  - Price Acceleration (ROC): max 15 poin
- **Exit Strategy:** Adaptive trailing stop yang mengejar puncak keuntungan tanpa batas take-profit tetap (biarkan tren pemenang terus tumbuh / *let winners run*).

### 3. Capital Tiers & Position Sizing Slicer
- **TIER 1 (Equity Rp1,000,000 - Rp30,000,000):**
  - Max Engine A allocation: 40% equity
  - Max Engine B allocation: 40% equity
  - Max 1 posisi per engine (maksimal 2 posisi berjalan bersamaan)
- **TIER 2 (Equity > Rp30,000,000 - Rp100,000,000):**
  - Alokasi per asset: 5% - 10% equity
  - Maksimal total eksposur portofolio: 80%
  - Minimum cadangan kas: 20%
- **Formula Shared Position Sizing:**
  $$\text{RISK\_BUDGET} = \text{EQUITY} \times 0.01$$
  $$\text{EXPECTED\_LOSS\_FRACTION} = \text{STOP\_LOSS} + \text{ENTRY\_FEE} + \text{EXIT\_FEE} + \text{SLIPPAGE}$$
  $$\text{POSITION\_BY\_RISK} = \frac{\text{RISK\_BUDGET}}{\text{EXPECTED\_LOSS\_FRACTION}}$$
  $$\text{FINAL\_SIZE} = \min(\text{POSITION\_BY\_RISK}, \text{ALLOCATION\_CAP}, \text{REMAINING\_EXPOSURE}, \text{LIQUIDITY\_CAP}, \text{USABLE\_CASH})$$

### 4. Portfolio Risk Controller & Daily Safety
- **Batas Risiko per Trade:** Maksimal 1% dari total equity.
- **Batas Risiko Portofolio Gabungan:** Maksimal 2% dari total equity.
- **Batas Kerugian Harian (Daily Loss Limit):** Maksimal 2% dari *Start-of-Day Equity* (menghentikan entri baru secara otomatis jika tercapai).
- **Pencegahan Posisi Ganda:** Melarang entri berulang pada aset yang sama (*anti-averaging down* / *anti-DCA*).

### 5. Web & CLI Dashboard Real-Time
- **Web Dashboard (FastAPI + Bootstrap Dark Theme):** Diakses secara lokal melalui browser di `http://localhost:8000`. Menampilkan grafik equity, alokasi kas, tier modal, posisi terbuka, tabel kandidat ranking Engine A & B, log penolakan risiko, status API health, dan tombol **Emergency Stop**.
- **CLI Dashboard:** Tampilan terminal otomatis yang diperbarui setiap siklus pemindaian pasar.

---

## 🚀 Cara Menjalankan Bot

### 1. Prasyarat Dependencies
Pastikan Python 3.10+ terinstall bersama library yang diperlukan:
```bash
pip install requests pandas numpy fastapi uvicorn
```

### 2. Jalankan Mode Paper Trading (Simulasi Pasar Live)
```bash
python -m indodax_bot.main --mode paper --initial-cash 10000000 --port 8000
```
Buka browser dan akses **`http://localhost:8000`** untuk melihat Web Dashboard interaktif secara real-time.

### 3. Jalankan Mode Backtesting
```bash
python -m indodax_bot.main --mode backtest --initial-cash 10000000
```

### 4. Menjalankan Automated Unit Tests
```bash
python -m unittest discover tests
```

---

## 📁 Struktur Proyek
```
bot-coding/
├── indodax_bot/
│   ├── __init__.py
│   ├── config.py            # Parameter konfigurasi V5.3-MACO R3 & aturan risiko
│   ├── indodax_api.py       # Client REST API Indodax publik dengan rate limit & health tracking
│   ├── market_data.py       # Pemindai pasar, agregator lilin, & penguji kedalaman order book
│   ├── indicators.py        # Indikator teknis & sistem scoring momentum 0-100 Engine B
│   ├── engine_a.py          # Mesin strategi Pure Scalper (1m, 5m, 15m)
│   ├── engine_b.py          # Mesin strategi Extreme Momentum Hunter (15m, 1h, 4h, 1d)
│   ├── risk_controller.py   # Pengendali risiko portofolio & alokasi kas cadangan aktif
│   ├── portfolio.py         # Pengelola saldo kas, posisi terbuka, PnL, & persistensi state.json
│   ├── backtester.py        # Kerangka kerja backtesting & penguji performa
│   ├── web_dashboard.py     # Web Dashboard FastAPI
│   ├── cli_dashboard.py     # Tampilan Dashboard Terminal CLI
│   └── main.py              # Orchestrator utama & loop pemindaian pasar
├── tests/                   # Suite pengujian unit otomatis
└── README.md
```

---

## 🛡️ Jaminan Keamanan & Kebijakan Live Trading
Secara bawaan (*default*):
- `LIVE_TRADING_ENABLED = False`
- `OPERATING_MODE = "PAPER_TRADING"`

Semua order dijalankan dalam simulator *paper trading* terisolasi tanpa menyentuh dana riil.
