---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:41:29 UTC"
ticker: "WCT/USDT"
canonical_symbol: "WCT/USDT"
base_symbol: "WCT"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.0359
quantity: 19589.0000
order_value: 703.25
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349288885"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - wct
  - crypto
  - failed
---

# ⚡ Trade Execution: `WCT/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:41:29 UTC`
> - **Canonical Instrument:** `WCT/USDT` (WCT/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.0359`
> - **Quantity:** `19589.0000` shares/units
> - **Total Value:** `$703.25`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.0359) vs 20-SMA ($0.0369) Deviation -2.71% [SL: $0.0372 | TP: $0.0341 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell at $0.04 as price is below the 20‑SMA, indicating bearish momentum, with a 2.1:1 risk‑reward (TP $0.0341, SL $0.0372).
> 
> **Key Catalysts:** *Price below 20‑SMA and trend momentum entry*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.04`
- **Actual Fill Price:** `$0.04`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:25 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.04 (+1.4%) | Nearest SSL $0.04 (-0.8%) [Target Score: 3.2, Pools: 7.0]
MANIPULATION: None Detected
BOS/MSS: BOS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.00x displacement, +6.8 pts)
  • Liquidity pools: 64 EQH, 23 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+1.39%, +3.2 pts)
SETUP QUALITY SCORE: 27.48 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
