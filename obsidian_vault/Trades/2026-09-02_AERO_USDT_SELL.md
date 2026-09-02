---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:36:33 UTC"
ticker: "AERO/USDT"
canonical_symbol: "AERO/USDT"
base_symbol: "AERO"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.4551
quantity: 1544.0000
order_value: 702.67
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348993051"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 72
tags:
  - trade
  - sell
  - aero
  - crypto
  - failed
---

# ⚡ Trade Execution: `AERO/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:36:33 UTC`
> - **Canonical Instrument:** `AERO/USDT` (AERO/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.4551`
> - **Quantity:** `1544.0000` shares/units
> - **Total Value:** `$702.67`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.4551) vs 20-SMA ($0.4666) Deviation -2.46% [SL: $0.4710 | TP: $0.4323 | Risk: $24.59]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 72% Confidence)**
> Sell at $0.46 with SL $0.4710 and TP $0.4323 yields a ~2.5:1 reward‑to‑risk ratio, supported by bearish price deviation below the 20‑SMA and a near‑neutral but slightly bearish RSI.
> 
> **Key Catalysts:** *Trend Momentum Entry (price below 20‑SMA) and RSI 46.9*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `$0.46`
- **Actual Fill Price:** `$0.46`
- **Execution Slippage:** `+0.0 bps`
- **Exchange/Broker Fee:** `$0.00`
- **Execution Latency:** `0.0 ms`

---

## 🧠 Smart Money & Market Structure Intelligence
> [!quote] **Market Structure Narrative**
> ```text
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.46 (+0.5%) | Nearest SSL $0.45 (-0.1%) [Target Score: 1.1, Pools: 7.0]
MANIPULATION: Sweep (Score: 14.6)
BOS/MSS: MSS_BEARISH (Score: 6.8)
FVG: None
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed MSS_BEARISH (0.43x displacement, +6.8 pts)
  • BEARISH_MANIPULATION (Wick: 32.1%, Disp: True, +14.6 pts)
  • Liquidity pools: 16 EQH, 3 EQL (+7.0 pts)
  • London session liquidity window (+9.0 pts)
  • Range boundary liquidity target (+0.46%, +1.1 pts)
SETUP QUALITY SCORE: 39.91 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
