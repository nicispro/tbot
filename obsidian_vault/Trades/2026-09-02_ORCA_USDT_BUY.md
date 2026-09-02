---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:32:09 UTC"
ticker: "ORCA/USDT"
canonical_symbol: "ORCA/USDT"
base_symbol: "ORCA"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "BUY"
price: 1.2080
quantity: 581.9000
order_value: 702.94
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348729069"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BULLISH"
ai_confidence: 70
tags:
  - trade
  - buy
  - orca
  - crypto
  - failed
---

# ⚡ Trade Execution: `ORCA/USDT` (BUY)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:32:09 UTC`
> - **Canonical Instrument:** `ORCA/USDT` (ORCA/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `BUY` @ `$1.2080`
> - **Quantity:** `581.9000` shares/units
> - **Total Value:** `$702.94`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (BUY): Price ($1.2080) vs 20-SMA ($1.1953) Deviation +1.06% [SL: $1.1657 | TP: $1.2684 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BULLISH - 70% Confidence)**
> Entry above the 20‑SMA with a +1.06% deviation and a reward‑to‑risk ratio of roughly 1.4:1 suggests a favorable upside potential. The trade is supported by a neutral RSI and moderate ATR, indicating manageable volatility.
> 
> **Key Catalysts:** *Price above 20‑SMA (+1.06% deviation), ATR of 0.0864 indicating moderate volatility, and clear support (1.009) and resistance (1.458) levels.*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$1.21`
- **Actual Fill Price:** `$1.21`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 9.0]
LIQUIDITY: Nearest BSL $1.21 (+0.3%) | Nearest SSL $1.20 (-0.9%) [Target Score: 1.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 11.4)
BOS/MSS: BOS_BEARISH (Score: 7.5)
FVG: FVG Active (Score: 13.1)
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed BOS_BEARISH (0.82x displacement, +7.5 pts)
  • BEARISH_MANIPULATION (Wick: 33.3%, Disp: False, +11.4 pts)
  • Liquidity pools: 10 EQH, 1 EQL (+7.0 pts)
  • Bullish Discount FVG ($1.20-$1.20, CE: $1.20, +13.1 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.33%, +1.0 pts)
SETUP QUALITY SCORE: 50.48 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
