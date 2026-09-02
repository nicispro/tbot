---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:31:02 UTC"
ticker: "FRAX/USDT"
canonical_symbol: "FRAX/USDT"
base_symbol: "FRAX"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.2876
quantity: 2444.0000
order_value: 702.89
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348661658"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 70
tags:
  - trade
  - sell
  - frax
  - crypto
  - failed
---

# ⚡ Trade Execution: `FRAX/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:31:02 UTC`
> - **Canonical Instrument:** `FRAX/USDT` (FRAX/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.2876`
> - **Quantity:** `2444.0000` shares/units
> - **Total Value:** `$702.89`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.2876) vs 20-SMA ($0.2963) Deviation -2.94% [SL: $0.2977 | TP: $0.2732 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 70% Confidence)**
> Sell entry below the 20‑SMA with a target near the 0.2756 support level and a stop above the entry, offering a moderate risk/reward profile.
> 
> **Key Catalysts:** *Price below 20‑SMA (‑2.94% deviation) and ATR‑based volatility support a bearish momentum entry.*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.29`
- **Actual Fill Price:** `$0.29`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: TRANSITIONAL [Score: 12.6]
LIQUIDITY: Nearest BSL $0.29 (+0.1%) | Nearest SSL $0.29 (-0.2%) [Target Score: 0.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 9.2)
BOS/MSS: MSS_BULLISH (Score: 8.1)
FVG: None
LOCATION: PREMIUM
CONFLUENCE:
  • Transitional Market Structure (+4.5 pts)
  • Confirmed MSS_BULLISH (1.03x displacement, +8.1 pts)
  • BEARISH_MANIPULATION (Wick: 25.0%, Disp: False, +9.2 pts)
  • Liquidity pools: 78 EQH, 18 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
SETUP QUALITY SCORE: 37.76 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
