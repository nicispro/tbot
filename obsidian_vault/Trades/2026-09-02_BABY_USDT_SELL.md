---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:39:44 UTC"
ticker: "BABY/USDT"
canonical_symbol: "BABY/USDT"
base_symbol: "BABY"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.0112
quantity: 62765.0000
order_value: 702.97
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349183517"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 80
tags:
  - trade
  - sell
  - baby
  - crypto
  - failed
---

# ⚡ Trade Execution: `BABY/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:39:44 UTC`
> - **Canonical Instrument:** `BABY/USDT` (BABY/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.0112`
> - **Quantity:** `62765.0000` shares/units
> - **Total Value:** `$702.97`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.0112) vs 20-SMA ($0.0116) Deviation -3.45% [SL: $0.0116 | TP: $0.0106 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 80% Confidence)**
> Sell entry below the 20‑SMA with moderate bearish momentum; target 0.0106 offers a 1.5× reward‑to‑risk ratio, supported by RSI under 50 and price below the 20‑SMA.
> 
> **Key Catalysts:** *Price below 20‑SMA and RSI under 50 indicating bearish momentum*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.01`
- **Actual Fill Price:** `$0.01`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.01 (+0.1%) | Nearest SSL $0.01 (-0.5%) [Target Score: 0.0, Pools: 6.0]
MANIPULATION: Sweep (Score: 5.5)
BOS/MSS: BOS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.19x displacement, +6.8 pts)
  • BEARISH_MANIPULATION (Wick: 0.0%, Disp: False, +5.5 pts)
  • Liquidity pools: 3 EQH, 1 EQL (+6.0 pts)
  • London session liquidity window (+9.0 pts)
SETUP QUALITY SCORE: 28.80 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
