---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:29:33 UTC"
ticker: "CLANKER/USDT"
canonical_symbol: "CLANKER/USDT"
base_symbol: "CLANKER"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 12.3700
quantity: 56.8000
order_value: 702.62
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348573332"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 80
tags:
  - trade
  - sell
  - clanker
  - crypto
  - failed
---

# ⚡ Trade Execution: `CLANKER/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:29:33 UTC`
> - **Canonical Instrument:** `CLANKER/USDT` (CLANKER/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$12.3700`
> - **Quantity:** `56.8000` shares/units
> - **Total Value:** `$702.62`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($12.3700) vs 20-SMA ($12.8225) Deviation -3.53% [SL: $12.8029 | TP: $11.7515 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 80% Confidence)**
> Sell trade justified by price below the 20‑SMA and RSI under 50, offering a favorable risk/reward of ~1.4.
> 
> **Key Catalysts:** *Price below 20‑SMA and RSI indicating bearish momentum*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$12.37`
- **Actual Fill Price:** `$12.37`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: BULLISH [Score: 20.0]
LIQUIDITY: Nearest BSL $12.38 (+0.1%) | Nearest SSL $12.33 (-0.3%) [Target Score: 0.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 14.5)
BOS/MSS: MSS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed Bullish Structure (4 HH / 7 HL swings, +13.2 pts)
  • Confirmed MSS_BEARISH (0.53x displacement, +6.8 pts)
  • BEARISH_MANIPULATION (Wick: 66.7%, Disp: False, +14.5 pts)
  • Liquidity pools: 0 EQH, 6 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
SETUP QUALITY SCORE: 50.50 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
