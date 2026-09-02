---
type: trade
date: 2026-09-02
timestamp: "2026-09-02 11:30:45 UTC"
ticker: "KOMA/USDT"
canonical_symbol: "KOMA/USDT"
base_symbol: "KOMA"
asset_class: "CRYPTO"
exchange: "BINANCE"
market_type: "USD_M_FUTURES"
action: "SELL"
price: 0.0129
quantity: 54554.0000
order_value: 703.75
status: "FAILED"
environment: "demo"
order_id: "CRYPTO-1788348645220"
slippage_bps: 0.0
fee_usd: 0.00
ai_sentiment: "BEARISH"
ai_confidence: 75
tags:
  - trade
  - sell
  - koma
  - crypto
  - failed
---

# ⚡ Trade Execution: `KOMA/USDT` (SELL)

> [!summary] **Order Execution Summary**
> - **Date & Time:** `2026-09-02 11:30:45 UTC`
> - **Canonical Instrument:** `KOMA/USDT` (KOMA/USDT (Binance Futures))
> - **Asset Class:** `CRYPTO` | **Exchange:** `BINANCE` (USD_M_FUTURES)
> - **Action:** `SELL` @ `$0.0129`
> - **Quantity:** `54554.0000` shares/units
> - **Total Value:** `$703.75`
> - **Status:** `FAILED` (`FAILED`)
> - **Environment:** `DEMO`


---

## 🎯 Strategy & Technical Context
[DEMO / FUTURE] Trend Momentum Entry (SELL): Price ($0.0129) vs 20-SMA ($0.0135) Deviation -4.44% [SL: $0.0134 | TP: $0.0123 | Risk: $24.60]

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis (BEARISH - 75% Confidence)**
> Short entry below the 20‑SMA with a modest reward (0.0006) to risk (0.0005) profile; RSI is neutral and ATR indicates moderate volatility.
> 
> **Key Catalysts:** *Price below 20‑SMA, ATR‑derived stop/target levels, support at 0.0116*

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
> SESSION: LONDON (11:24 UTC) [Score: 9.0]
STRUCTURE: RANGE [Score: 8.3]
LIQUIDITY: Nearest BSL $0.01 (+0.2%) | Nearest SSL $0.01 (-0.1%) [Target Score: 0.0, Pools: 7.0]
MANIPULATION: Sweep (Score: 14.5)
BOS/MSS: MSS_BULLISH (Score: 6.8)
FVG: FVG Active (Score: 11.8)
LOCATION: DISCOUNT
CONFLUENCE:
  • Confirmed MSS_BULLISH (0.00x displacement, +6.8 pts)
  • BULLISH_MANIPULATION (Wick: 75.0%, Disp: False, +14.5 pts)
  • Liquidity pools: 3 EQH, 6 EQL (+7.0 pts)
  • Bullish Discount FVG ($0.01-$0.01, CE: $0.01, +11.8 pts)
  • London session liquidity window (+9.0 pts)
SETUP QUALITY SCORE: 50.60 / 100
> ```

---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `binanceusdm {"code":-2014,"msg":"API-key format invalid."}`
