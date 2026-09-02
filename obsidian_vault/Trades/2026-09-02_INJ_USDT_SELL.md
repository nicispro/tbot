---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:39:31 UTC"
ticker: "INJ/USDT"
canonical_symbol: "INJ/USDT"
base_symbol: "INJ"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 4.7580
quantity: 147.7000
order_value: 702.76
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349170996"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - inj
  - crypto
  - failed
---

# ⚡ Trade Execution: `INJ/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:39:31 UTC`
> - **Canonical Instrument:** `INJ/USDT` (INJ/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$4.7580`
> - **Quantity:** `147.7000` shares/units
> - **Total Value:** `$702.76`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($4.7580) vs 20-SMA ($4.8739) Deviation -2.38% [SL: $4.9245 | TP: $4.5201 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell at $4.76 targeting $4.52 with stop at $4.92; RSI near 45 and price below 20‑SMA suggest bearish momentum.
> 
> **Key Catalysts:** *Price below 20‑SMA and RSI under 50 indicating trend reversal*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$4.76`
- **Actual Fill Price:** `$4.76`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $4.78 (+0.4%) | Nearest SSL $4.75 (-0.1%) [Target Score: 1.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 14.5)
BOS/MSS: BOS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.31x displacement, +6.8 pts)
  • BEARISH_MANIPULATION (Wick: 49.0%, Disp: False, +14.5 pts)
  • Liquidity pools: 46 EQH, 21 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.36%, +1.0 pts)
SETUP QUALITY SCORE: 39.80 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
