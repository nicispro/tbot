---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:40:47 UTC"
ticker: "NIGHT/USDT"
canonical_symbol: "NIGHT/USDT"
base_symbol: "NIGHT"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.0184
quantity: 38205.0000
order_value: 702.97
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349246986"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - night
  - crypto
  - failed
---

# ⚡ Trade Execution: `NIGHT/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:40:47 UTC`
> - **Canonical Instrument:** `NIGHT/USDT` (NIGHT/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.0184`
> - **Quantity:** `38205.0000` shares/units
> - **Total Value:** `$702.97`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.0184) vs 20-SMA ($0.0189) Deviation -2.65% [SL: $0.0190 | TP: $0.0175 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell at $0.02 because the price is 2.65% below the 20‑SMA, offering a 0.0009 profit target against a 0.0006 stop‑loss for a favorable risk/reward.
> 
> **Key Catalysts:** *Price below 20‑SMA indicating bearish momentum*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.02`
- **Actual Fill Price:** `$0.02`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.02 (+0.3%) | Nearest SSL $0.02 (-0.1%) [Target Score: 0.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 5.5)
BOS/MSS: BOS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.58x displacement, +6.8 pts)
  • BEARISH_MANIPULATION (Wick: 0.0%, Disp: False, +5.5 pts)
  • Liquidity pools: 6 EQH, 4 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
SETUP QUALITY SCORE: 29.80 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
