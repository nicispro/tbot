---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:31:29 UTC"
ticker: "AIO/USDT"
canonical_symbol: "AIO/USDT"
base_symbol: "AIO"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.0461
quantity: 15253.0000
order_value: 703.16
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348689264"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - aio
  - crypto
  - failed
---

# ⚡ Trade Execution: `AIO/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:31:29 UTC`
> - **Canonical Instrument:** `AIO/USDT` (AIO/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.0461`
> - **Quantity:** `15253.0000` shares/units
> - **Total Value:** `$703.16`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.0461) vs 20-SMA ($0.0472) Deviation -2.33% [SL: $0.0477 | TP: $0.0438 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> The price is below the 20‑SMA and trending downward, offering a short entry with a modest risk‑to‑reward profile (SL 0.0477, TP 0.0438).
> 
> **Key Catalysts:** *Price below 20‑SMA and RSI near 42 indicating potential downward momentum.*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.05`
- **Actual Fill Price:** `$0.05`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 12.5]
LIQUIDITY: Nearest BSL $0.05 (+0.5%) | Nearest SSL $0.05 (-0.1%) [Target Score: 1.1, Pools: 7.0]
MANIPULATION: Sweep (Score: 9.0)
BOS/MSS: MSS_BEARISH (Score: 11.0)
FVG: FVG Active (Score: 16.9)
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed MSS_BEARISH (2.27x displacement, +11.0 pts)
  • BULLISH_MANIPULATION (Wick: 3.3%, Disp: True, +9.0 pts)
  • Liquidity pools: 5 EQH, 7 EQL (+7.0 pts)
  • Bullish Discount FVG ($0.05-$0.05, CE: $0.05, +16.9 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.46%, +1.1 pts)
SETUP QUALITY SCORE: 55.45 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
