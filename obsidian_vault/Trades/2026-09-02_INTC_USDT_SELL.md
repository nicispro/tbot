---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:37:03 UTC"
ticker: "INTC/USDT"
canonical_symbol: "INTC/USDT"
base_symbol: "INTC"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 88.0100
quantity: 8.0000
order_value: 704.08
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349022103"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - intc
  - crypto
  - failed
---

# ⚡ Trade Execution: `INTC/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:37:03 UTC`
> - **Canonical Instrument:** `INTC/USDT` (INTC/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$88.0100`
> - **Quantity:** `8.0000` shares/units
> - **Total Value:** `$704.08`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($88.0100) vs 20-SMA ($92.7845) Deviation -5.15% [SL: $91.0904 | TP: $83.6095 | Risk: $24.58]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Price is $5.15% below the 20‑SMA with RSI at 39, supporting a short bias; target offers ~1.4:1 reward‑to‑risk.
> 
> **Key Catalysts:** *Breakdown below 20‑SMA and bearish momentum indicated by RSI <40*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$88.01`
- **Actual Fill Price:** `$88.01`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:25 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $88.77 (+0.9%) | Nearest SSL $87.50 (-0.6%) [Target Score: 2.0, Pools: 7.0]
MANIPULATION: None Detected
BOS/MSS: BOS_BEARISH (Score: 6.8)
FVG: FVG Active (Score: 18.4)
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.17x displacement, +6.8 pts)
  • Liquidity pools: 34 EQH, 57 EQL (+7.0 pts)
  • Bullish Discount FVG ($87.86-$87.96, CE: $87.91, +18.4 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.86%, +2.0 pts)
SETUP QUALITY SCORE: 44.69 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
