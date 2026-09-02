---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:35:52 UTC"
ticker: "IN/USDT"
canonical_symbol: "IN/USDT"
base_symbol: "IN"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "BUY"
price: 0.0341
quantity: 20606.0000
order_value: 702.66
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348952143"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BULLISH"
ai_confidence: 70
tags:
  - trade
  - buy
  - in
  - crypto
  - failed
---

# ⚡ Trade Execution: `IN/USDT` (BUY)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:35:52 UTC`
> - **Canonical Instrument:** `IN/USDT` (IN/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `BUY` @ `$0.0341`
> - **Quantity:** `20606.0000` shares/units
> - **Total Value:** `$702.66`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (BUY): Price ($0.0341) vs 20-SMA ($0.0323) Deviation +5.57% [SL: $0.0329 | TP: $0.0358 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BULLISH - 70% Confidence)**
> The entry is above the 20‑period SMA with a modest 5.6% deviation, indicating upward momentum, and the price sits near support while the target is below resistance, offering a favorable risk‑reward profile.
> 
> **Key Catalysts:** *Price above 20‑SMA, RSI near neutral, ATR indicating low volatility, and proximity to support level*

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
STRUCTURE: RANGE [Score: 10.7]
LIQUIDITY: Nearest BSL None | Nearest SSL $0.03 (-1.4%) [Target Score: 3.1, Pools: 7.0]
MANIPULATION: Sweep (Score: 11.4)
BOS/MSS: BOS_BULLISH (Score: 9.2)
FVG: None
LOCATION: PREMIUM
CONFLUENCE:
  • Confirmed BOS_BULLISH (1.40x displacement, +9.2 pts)
  • BULLISH_MANIPULATION (Wick: 33.3%, Disp: False, +11.4 pts)
  • Liquidity pools: 10 EQH, 4 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+1.38%, +3.1 pts)
SETUP QUALITY SCORE: 41.23 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
