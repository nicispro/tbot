---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:42:06 UTC"
ticker: "BANK/USDT"
canonical_symbol: "BANK/USDT"
base_symbol: "BANK"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.0348
quantity: 20200.0000
order_value: 702.96
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349326164"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - bank
  - crypto
  - failed
---

# ⚡ Trade Execution: `BANK/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:42:06 UTC`
> - **Canonical Instrument:** `BANK/USDT` (BANK/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.0348`
> - **Quantity:** `20200.0000` shares/units
> - **Total Value:** `$702.96`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.0348) vs 20-SMA ($0.0360) Deviation -3.33% [SL: $0.0360 | TP: $0.0331 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell entry below 20‑SMA with -3.33% deviation offers a clear risk/reward (SL $0.0360, TP $0.0331) and modest downside bias.
> 
> **Key Catalysts:** *Trend Momentum Entry (SELL) triggered by price falling below the 20‑SMA*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.03`
- **Actual Fill Price:** `$0.03`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.03 (+0.1%) | Nearest SSL $0.03 (-0.1%) [Target Score: 0.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 5.8)
BOS/MSS: MSS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed MSS_BEARISH (0.24x displacement, +6.8 pts)
  • BEARISH_MANIPULATION (Wick: 12.5%, Disp: False, +5.8 pts)
  • Liquidity pools: 22 EQH, 30 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
SETUP QUALITY SCORE: 30.13 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
