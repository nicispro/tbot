---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:39:16 UTC"
ticker: "ALT/USDT"
canonical_symbol: "ALT/USDT"
base_symbol: "ALT"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.0060
quantity: 117162.0000
order_value: 702.97
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349156205"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - alt
  - crypto
  - failed
---

# ⚡ Trade Execution: `ALT/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:39:16 UTC`
> - **Canonical Instrument:** `ALT/USDT` (ALT/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.0060`
> - **Quantity:** `117162.0000` shares/units
> - **Total Value:** `$702.97`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.0060) vs 20-SMA ($0.0062) Deviation -3.23% [SL: $0.0062 | TP: $0.0057 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell signal triggered by price falling below the 20‑SMA with a -3.23% deviation; risk/reward is balanced at 1:1 with SL at 0.0062 and TP at 0.0057.
> 
> **Key Catalysts:** *Price below 20‑SMA, negative momentum, RSI 45.72, support level at 0.0054.*

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
> SESSION: LONDON (11:25 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.01 (+0.7%) | Nearest SSL $0.01 (-0.2%) [Target Score: 1.5, Pools: 7.0]
MANIPULATION: None Detected
BOS/MSS: MSS_BULLISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed MSS_BULLISH (0.00x displacement, +6.8 pts)
  • Liquidity pools: 2 EQH, 7 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.67%, +1.5 pts)
SETUP QUALITY SCORE: 25.83 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
