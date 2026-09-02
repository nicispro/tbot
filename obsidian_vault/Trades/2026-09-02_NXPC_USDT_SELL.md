---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:33:21 UTC"
ticker: "NXPC/USDT"
canonical_symbol: "NXPC/USDT"
base_symbol: "NXPC"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.1987
quantity: 3538.0000
order_value: 703.00
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348801132"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - nxpc
  - crypto
  - failed
---

# ⚡ Trade Execution: `NXPC/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:33:21 UTC`
> - **Canonical Instrument:** `NXPC/USDT` (NXPC/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.1987`
> - **Quantity:** `3538.0000` shares/units
> - **Total Value:** `$703.00`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.1987) vs 20-SMA ($0.2055) Deviation -3.31% [SL: $0.2057 | TP: $0.1888 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell at $0.20 with a target of $0.1888 and stop at $0.2057, yielding a risk of $24.60. RSI at 40.97 and price below the 20‑SMA support bearish momentum.
> 
> **Key Catalysts:** *Price below 20‑SMA and RSI under 50*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.20`
- **Actual Fill Price:** `$0.20`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:25 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.20 (+0.4%) | Nearest SSL $0.20 (-0.1%) [Target Score: 1.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 14.5)
BOS/MSS: BOS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.22x displacement, +6.8 pts)
  • BULLISH_MANIPULATION (Wick: 69.2%, Disp: False, +14.5 pts)
  • Liquidity pools: 34 EQH, 10 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.40%, +1.0 pts)
SETUP QUALITY SCORE: 39.80 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
