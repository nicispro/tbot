---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:43:00 UTC"
ticker: "GOOGL/USDT"
canonical_symbol: "GOOGL/USDT"
base_symbol: "GOOGL"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 335.1800
quantity: 2.1000
order_value: 703.88
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788349379610"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - googl
  - crypto
  - failed
---

# ⚡ Trade Execution: `GOOGL/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:43:00 UTC`
> - **Canonical Instrument:** `GOOGL/USDT` (GOOGL/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$335.1800`
> - **Quantity:** `2.1000` shares/units
> - **Total Value:** `$703.88`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($335.1800) vs 20-SMA ($344.3000) Deviation -2.65% [SL: $346.9113 | TP: $318.4210 | Risk: $24.52]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell entry triggered as price falls below the 20‑SMA with moderate bearish momentum; target near 318.42 offers ~5.5% reward while stop at 346.91 limits risk to ~7%.
> 
> **Key Catalysts:** *Price below 20‑SMA and RSI 37.21 indicating bearish momentum*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$335.18`
- **Actual Fill Price:** `$335.18`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:25 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.7]
LIQUIDITY: Nearest BSL $337.00 (+0.5%) | Nearest SSL $334.21 (-0.3%) [Target Score: 1.2, Pools: 7.0]
MANIPULATION: None Detected
BOS/MSS: BOS_BEARISH (Score: 7.2)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.72x displacement, +7.2 pts)
  • Liquidity pools: 212 EQH, 45 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.54%, +1.2 pts)
SETUP QUALITY SCORE: 25.89 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
