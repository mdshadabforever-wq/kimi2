\## IIIS v4.6 — Institutional Intraday Intelligence System with Big Money Detection



\*\*Version:\*\* v4.6 (Corrected from v4.4/v4.5, Big Money Module Added)  

\*\*Status:\*\* FROZEN — Ready for Phase 1 Implementation  

\*\*Last Updated:\*\* 2026-06-15  

\*\*Previous Versions:\*\* v4.4 (Original), v4.5 (Corrected), v4.6 (Big Money + Final)



---



```

You are building IIIS v4.6 - Institutional 

Intraday Intelligence System with Big Money Detection.



Read this complete specification carefully.

Then confirm you understand it.

Then ask me which phase to start.

Do NOT write any code until I say start.

```



---



\## TABLE OF CONTENTS



1\. What is IIIS

2\. Technology Stack

3\. Environment Variables

4\. Daily Timeline

5\. Live Scan — 16 Steps Every 60 Seconds

6\. Market Regime Engine

7\. Composite Score \& Weightings

8\. Risk Gates

9\. Big Money Detection Module

10\. Big Money Confluence Score

11\. ARC Engine — Claude API

12\. GEIE Engine — Gemini API

13\. GEIE Master Map — All 50 Stocks

14\. Telegram Alert Format

15\. Risk Grade Definitions

16\. Alert Validity \& Cooldown Rules

17\. Risk Management

18\. Database Schema — 16 Tables

19\. Ghost Mode

20\. Monitoring

21\. Session End Protocol

22\. Development Phases in Order

23\. Non-Negotiable Rules

24\. Errata (v4.4 → v4.6 Changes)



---



\## 1. WHAT IS IIIS



IIIS is a trading intelligence alert system for NIFTY 50 stocks.



The system:

\- Monitors all 50 NIFTY stocks every minute

\- Finds high quality trade opportunities

\- Detects institutional (Big Money) activity

\- Sends alerts via Telegram

\- NEVER places trades automatically

\- Human always executes trades manually



Simple analogy:

IIIS is a smart munshi who watches 50 stocks all day, tracks where institutions are putting money, and calls you when a good opportunity appears. You decide to trade or not.



---



\## 2. TECHNOLOGY STACK



| Component | Technology |

|-----------|------------|

| Language | Python 3.11+ |

| Database | PostgreSQL + TimescaleDB |

| Cache | Redis |

| Container | Docker |

| Primary VPS | DigitalOcean Mumbai — 8GB RAM, 4CPU, 160GB SSD |

| Backup VPS | AWS Lightsail Mumbai — 4GB RAM, 2CPU, 80GB SSD |

| Market Data | Upstox API V3 |

| News | Perplexity API |

| Event Analysis | Gemini API (GEIE) |

| Research | Claude API (ARC) |

| Alerts | Telegram Bot API |

| FII/DII Data | NSE Official Website |

| Bulk Deals | NSE India Website |



---



\## 3. ENVIRONMENT VARIABLES



Create `.env` file with these:



```env

\# Upstox API

UPSTOX\_API\_KEY=your\_actual\_key\_here

UPSTOX\_API\_SECRET=your\_actual\_secret\_here

UPSTOX\_REDIRECT\_URI=http://localhost:8000/callback



\# AI APIs

PERPLEXITY\_API\_KEY=your\_actual\_key\_here

GEMINI\_API\_KEY=your\_actual\_key\_here

CLAUDE\_API\_KEY=your\_actual\_key\_here



\# Telegram

TELEGRAM\_BOT\_TOKEN=your\_actual\_token\_here

TELEGRAM\_ADMIN\_CHAT\_ID=your\_chat\_id\_here



\# Database

DB\_HOST=localhost

DB\_PORT=5432

DB\_NAME=iiis

DB\_USER=iiis\_user

DB\_PASSWORD=strong\_password\_here



\# Redis

REDIS\_HOST=localhost

REDIS\_PORT=6379



\# Risk Settings

CAPITAL=1000000

RISK\_PCT=0.5

MAX\_DAILY\_RISK\_PCT=2.0

HARD\_STOP\_LOSSES=3



\# System

TIMEZONE=Asia/Kolkata

```



---



\## 4. DAILY TIMELINE



| Time | Activity |

|------|----------|

| 07:00 AM | Global news scan (Perplexity) |

| 08:00 AM | India news scan (Perplexity) |

| 08:05 AM | GEIE run (Gemini) — Cache result in Redis, valid all day |

| 08:10 AM | Sector ranking calculation |

| 08:15 AM | FII/DII data fetch (NSE) — Store in database |

| 08:20 AM | Watchlist generation + ARC batch review (Claude) + Send pre-market brief Telegram |

| 09:15 AM | Market opens. No alerts. |

| 09:25 AM | Live scanning starts — Every 60 seconds, all 50 NIFTY stocks |

| 03:14 PM | Queue lock |

| 03:15 PM | Stop all alerts |

| 03:30 PM | Freeze session and reset counters |

| 04:00 PM | ARC post-market review |

| 04:30 PM | Generate and send EOD report |



---



\## 5. LIVE SCAN — 16 STEPS EVERY 60 SECONDS



Run for all 50 stocks simultaneously:



\### STEP 1 — GET LIVE DATA

\- Source: Upstox WebSocket V3

\- Get: Price, OHLC, Volume, VIX

\- Latency must be under 100ms



\### STEP 2 — MULTI TIMEFRAME ENGINE

\- Calculate trends on: Daily, 1 Hour, 15 Minute, 5 Minute

\- Minimum 3 of 4 timeframes must align in the SAME DIRECTION (all bullish or all bearish)

\- Output: Alignment score 0-100



\### STEP 3 — SMC ENGINE

Detect on both 5m and 15m charts:



\- \*\*BOS\*\*: Close above previous swing high OR below previous swing low. Use 5 bar lookback.

\- \*\*CHOCH\*\*: Change of market structure

\- \*\*Order Block\*\*: Last opposite candle before impulse move

\- \*\*FVG\*\*: Fair Value Gap between candles



\*\*MANDATORY CROSS TIMEFRAME RULE:\*\*

Need minimum 2 confirmations.

\- At least 1 must be from 15m chart

\- At least 1 must be from 5m chart



\*\*PASS examples:\*\*

\- 5m BOS + 15m Order Block = PASS

\- 5m CHOCH + 15m FVG = PASS



\*\*FAIL examples:\*\*

\- 5m BOS + 5m FVG = FAIL

\- 15m BOS + 15m OB = FAIL



\*\*Signal Direction Mapping:\*\*

\- Bullish BOS/CHOCH + bullish OB/FVG = LONG signal

\- Bearish BOS/CHOCH + bearish OB/FVG = SHORT signal

\- Mixed signals = NO DIRECTION (reject)



\### STEP 4 — OPTIONS ENGINE

\- Scan every 5 minutes (synchronized to market clock: 09:25:00, 09:30:00, 09:35:00, etc.)

\- Also scan immediately when SMC triggers (event-driven), using most recent 5-minute options data

\- Calculate:

&nbsp; - PCR (Put Call Ratio)

&nbsp; - OI Change per strike

&nbsp; - Long Buildup detection

&nbsp; - Short Buildup detection

&nbsp; - Long Unwinding detection

&nbsp; - Short Covering detection



\*\*PCR Interpretation:\*\*

\- PCR above 1.3 = Bullish

\- PCR below 0.7 = Bearish

\- PCR 0.7 to 1.3 = Neutral



\*\*Output:\*\* Options score 0-100



\### STEP 5 — RELATIVE STRENGTH ENGINE

\- Formula: Stock return minus NIFTY 50 return (same weighted timeframes)

\- Timeframe weights:

&nbsp; - 5m = 10%

&nbsp; - 15m = 20%

&nbsp; - 30m = 30%

&nbsp; - Daily = 40%

\- Output: Percentile rank across NIFTY 50 (0-100)



\*\*NIFTY Return Calculation:\*\*

\- Calculate NIFTY 50 return over the same weighted periods (5m/15m/30m/Daily)

\- Use percentage change from period open to current price



\### STEP 6 — RVOL ENGINE

\- Formula: Current volume divided by 20-day average volume (same timeframe)

\- RVOL scoring (linear interpolation between thresholds):

&nbsp; - RVOL ≥ 3.0 = score 100

&nbsp; - RVOL 2.0 to 3.0 = score 80 to 100 (linear)

&nbsp; - RVOL 1.5 to 2.0 = score 60 to 80 (linear)

&nbsp; - RVOL 1.0 to 1.5 = score 40 to 60 (linear)

&nbsp; - RVOL < 1.0 = score 0 to 40 (linear, capped at 40)

\- Output: RVOL score 0-100



\### STEP 7 — BREADTH ENGINE

\- Calculate from all 50 NIFTY stocks:

&nbsp; - Advance Decline Ratio

&nbsp; - Stocks above VWAP count

&nbsp; - Stocks above 20 EMA count

&nbsp; - New Highs count

&nbsp; - New Lows count

\- Output: Breadth score 0-100



\### STEP 8 — SECTOR STRENGTH ENGINE

\- Use pre-calculated sector ranking from 08:10 AM calculation

\- Map each stock to its sector

\- Assign sector score

\- Output: Sector score 0-100



\### STEP 9 — COMPOSITE SCORE



\*\*7 Input Engines \& Weightings:\*\*



| Engine | Weight | Description |

|--------|--------|-------------|

| Market Regime | 25% | From Regime Engine (Step 10) |

| Relative Strength | 20% | From Step 5 |

| Volume RVOL | 15% | From Step 6 |

| Market Breadth | 10% | From Step 7 |

| Options Flow | 10% | From Step 4 |

| Sector Strength | 10% | From Step 8 |

| SMC Signal Quality | 10% | From Step 3: based on number of SMC confirmations (1=weak, 2=medium, 3+=strong) |

| \*\*Total\*\* | \*\*100%\*\* | |



\*\*SMC Quality Score (0-100):\*\*

\- 1 SMC confirmation = 40

\- 2 SMC confirmations = 70

\- 3+ SMC confirmations = 100

\- 0 SMC confirmations = 0 (rejected at Gate 2 anyway)



\*\*THRESHOLD RULE:\*\*

\- Score must be STRICTLY GREATER than 85

\- Score 85 = REJECT immediately

\- Score 86 = proceed to gates

\- Score 85.5 = REJECT (must be ≥ 86.0)



\*\*ATR Standard:\*\* Period 14, Timeframe 15m  

\*\*RVOL Standard:\*\* 20-day average



\### STEP 10 — RISK GATES

Run all 8 gates. All must pass. Any single fail = reject immediately. All gates run BEFORE AI layers.



\#### GATE 1 — LIQUIDITY

\- Minimum ADTV ₹50 Crore

\- Maximum bid-ask spread 0.20%

\- Minimum session RVOL 1.0

\- \*\*Fail = reject\*\*



\#### GATE 2 — SMC VALIDATION

\- Must have cross-timeframe confirmation from Step 3 above

\- \*\*Fail = reject\*\*



\#### GATE 3 — CORRELATION

\- Maximum 2 alerts same sector per 30 min

\- Maximum 4 active alerts total

\- \*\*Fail = reject\*\*



\#### GATE 4 — EARNINGS

\- Company results within next 24 trading hours (Asia/Kolkata timezone) = block

\- No exceptions

\- \*\*Fail = reject\*\*



\#### GATE 5 — EVENT RISK

\- Block 15 minutes before major event

\- Block 15 minutes after major event

\- Major events: RBI, Fed, CPI, GDP, Budget, MPC

\- \*\*Fail = reject\*\*



\#### GATE 6 — CHOPPY FILTER

All 3 conditions must be true together:

\- ADX(14) less than 20

\- AND AD Ratio between 0.9 and 1.1

\- AND NIFTY inside 0.5 ATR range for 30 min

\- If all 3 true: \*\*block ALL signals\*\*



\#### GATE 7 — CIRCUIT BREAKER

\- NIFTY moves more than 1.5% in 15 min

\- Action: Pause 20 minutes → Recalculate regime → Resume if stable



\#### GATE 8 — VOLATILITY REGIME

\- \*\*India VIX above 20:\*\*

&nbsp; - Reduce position size by 50%

&nbsp; - Alert continues with warning

\- \*\*NIFTY ATR(14) above 1.5× 30-day average:\*\*

&nbsp; - Pause all intraday alerts

&nbsp; - Resume when ATR returns below 1.5× threshold



\### STEP 11 — HISTORICAL PATTERN ENGINE

\- Search last 90 days stored data

\- Find similar setups with:

&nbsp; - Same market regime

&nbsp; - Similar score within ±5 points

&nbsp; - Same direction (Long or Short) — mapped from SMC direction in Step 3

&nbsp; - Same sector

\- Output:

&nbsp; - Win Rate percentage

&nbsp; - Profit Factor

&nbsp; - Sample size count

&nbsp; - Average hold time

\- \*\*Minimum 10 similar setups required\*\*

\- Less than 10 = add LOW CONFIDENCE tag to alert



\### STEP 12 — GEIE VALIDATION

\- Use cached GEIE result from 08:05 AM

\- NO live API call here

\- Check impact direction for this stock

\- If NEGATIVE and LONG signal: Add warning note to alert

\- If POSITIVE and LONG signal: Add confirmation note to alert

\- If NEUTRAL: No additional note

\- If GEIE\_STATUS = UNAVAILABLE: Continue normally, add "GEIE UNAVAILABLE" note



\### STEP 13 — ALGORITHMIC CONFIDENCE FILTER

Rules based. No AI call. No API cost. Replaces live ARC completely.



\*\*HIGH confidence when:\*\*

\- Score above 92

\- AND GEIE direction POSITIVE

\- AND Historical win rate above 60%



\*\*MEDIUM confidence when:\*\*

\- Score 88 to 92

\- AND GEIE direction POSITIVE or NEUTRAL

\- AND Historical win rate 50% to 60%



\*\*LOW confidence when:\*\*

\- Score 86 to 88 (corrected: was 85-88, but 85 is rejected)

\- AND GEIE direction NEUTRAL

\- AND Historical win rate below 50%

\- Add CAUTION flag to alert



\### STEP 14 — RISK ENGINE

\- Check daily risk used is below 2%

\- Check consecutive losses below 3

\- Check sector exposure limits

\- Calculate position size with VIX adjustment



\*\*Position Size Formula:\*\*

```

Size = (Capital × 0.5%) ÷ max((Entry − Stop Loss), Entry × 0.001)

```



\*\*Guard against division by zero:\*\*

\- If (Entry − Stop Loss) < 0.1% of Entry price, use minimum stop distance = 0.1% of Entry price

\- If still zero or negative, reject signal



\*\*VIX Adjustment:\*\*

\- VIX below 15: Full size (100%)

\- VIX 15 to 20: 75% of size

\- VIX above 20: 50% of size



\*\*Maximum position cap:\*\* 10% of capital



\### STEP 15 — BIG MONEY CONFLUENCE CHECK

\*\*NEW in v4.6\*\*



Check 5 Big Money signals (see Section 10 for details):



| Signal | Points | Source |

|--------|--------|--------|

| FII Buying Trend (3+ consecutive days) | +20 | fii\_dii\_tracker table |

| Bulk Deal Same Direction (last 15 min) | +20 | bulk\_deal\_tracker table |

| Unusual Options Activity (3x OI change) | +20 | options\_intelligence table |

| Historical OB Zone Nearby (tested 3+ times) | +20 | order\_block\_memory table |

| RS Divergence Detected (>1.5% vs NIFTY) | +20 | Calculated live |

| \*\*Maximum\*\* | \*\*100\*\* | |



\*\*Rules:\*\*

\- Big Money Score is CONTEXT only

\- Weight in composite = 0%

\- Never blocks signal

\- Enhances Risk Grade only (see Section 15)



\### STEP 16 — GENERATE ALERT

If all 15 steps pass:

\- Generate alert with Big Money section

\- Apply Risk Grade upgrade if Big Money Score ≥ 80

\- Send via Telegram

\- Log to database

\- Update audit trail

\- Set valid\_until based on regime (see Section 16)



---



\## 6. MARKET REGIME ENGINE



This determines 25% of total composite score.



| Regime | Regime Score | Max Composite | Alerts Allowed | Notes |

|--------|-------------|---------------|----------------|-------|

| \*\*Trend Day\*\* | 100 | 100.0 | YES | ADX(14) on 15m > 25, NIFTY > EMA 20, AD Ratio > 1.5 |

| \*\*Expiry Day\*\* | 70 | 92.5 | YES | Weekly or Monthly expiry day |

| \*\*Reversal Day\*\* | 50 | 87.5 | YES (HIGH only) | Gap at open > 0.8%, opening direction fails within 30 min, breadth reverses |

| \*\*Transition Day\*\* | 30 | 82.5 | NO | Cannot mathematically reach 86 |

| \*\*Range Day\*\* | 20 | 80.0 | NO | ADX(14) on 15m < 20, NIFTY inside ATR range, AD Ratio 0.8-1.2 |



\*\*Composite Score Calculation Example (Trend Day):\*\*

\- Regime contribution: 100 × 25% = 25 points

\- If all other engines score 100: 25 + 20 + 15 + 10 + 10 + 10 + 10 = 100



---



\## 7. COMPOSITE SCORE \& WEIGHTINGS



\*\*Final Formula:\*\*

```

Composite = (RegimeScore × 0.25) + (RS\_Score × 0.20) + (RVOL\_Score × 0.15) + 

&nbsp;           (Breadth\_Score × 0.10) + (Options\_Score × 0.10) + (Sector\_Score × 0.10) + 

&nbsp;           (SMC\_Quality\_Score × 0.10)

```



\*\*Big Money Score is NOT included in composite.\*\*



---



\## 8. RISK GATES (Summary)



| Gate | Name | Fail Action |

|------|------|-------------|

| 1 | Liquidity | Reject signal |

| 2 | SMC Validation | Reject signal |

| 3 | Correlation | Reject signal |

| 4 | Earnings | Reject signal |

| 5 | Event Risk | Reject signal |

| 6 | Choppy Filter | Block ALL signals |

| 7 | Circuit Breaker | Pause 20 min |

| 8 | Volatility Regime | Reduce size or Pause |



---



\## 9. BIG MONEY DETECTION MODULE



\### MODULE 1 — FII/DII TRACKER



\*\*Purpose:\*\* Track institutional buying and selling to set daily market bias.



\*\*Data Source:\*\* NSE website daily data. Perplexity API 8 AM scan.



\*\*What to track:\*\*

\- Daily FII net activity: Net Buyer or Net Seller (Amount in crores)

\- Daily DII net activity: Net Buyer or Net Seller (Amount in crores)

\- 5 day trend: Count consecutive FII buy/sell days



\*\*Logic:\*\*

\- FII buyer 3+ consecutive days = BULLISH BIAS for long signals

\- FII seller 3+ consecutive days = BEARISH BIAS, suppress long signals

\- FII buyer + DII buyer same day = STRONG BULLISH — extra confidence

\- FII seller + DII seller same day = STRONG BEARISH — suppress longs



\*\*Database:\*\* `fii\_dii\_tracker` table



\### MODULE 2 — BLOCK AND BULK DEAL TRACKER



\*\*Purpose:\*\* Detect large institutional transactions.



\*\*Pre-Market Block Deals (8 AM):\*\* Already in Perplexity 8 AM scan. No change.



\*\*Intraday Bulk Deal Monitor:\*\*

\- URL: https://www.nseindia.com/market-data/bulk-deal

\- Scan: Every 15 minutes during live market

\- Detect: Any deal above ₹25 crore in NIFTY 50 stocks



\*\*Logic:\*\*

\- Bulk buy deal in stock X = Add INSTITUTIONAL BUY FLAG

\- Bulk sell deal in stock X = Add INSTITUTIONAL SELL FLAG



\*\*Database:\*\* `bulk\_deal\_tracker` table



\### MODULE 3 — OPTIONS BIG MONEY DETECTOR



\*\*1. Unusual Options Activity Detector:\*\*

\- Strikes where OI change is 3x or more than 20-day average

\- Unusual CALL buying = Big money expects price up

\- Unusual PUT buying = Big money expects price down

\- Unusual PUT writing = Big money defending support



\*\*2. Max Pain Tracker:\*\*

\- Calculate max pain daily (price where max options expire worthless)

\- Show in Telegram alert on expiry day



\*\*3. OI Concentration Zones:\*\*

\- Highest PUT OI = Strong support level

\- Highest CALL OI = Strong resistance level



\*\*Database:\*\* `options\_intelligence` table



\### MODULE 4 — SMART MONEY ORDER BLOCK DATABASE



\*\*Purpose:\*\* Build permanent database of key Order Block zones.



\*\*Store every valid OB detected:\*\*

\- Symbol, timeframe, type (bullish/bearish)

\- High, low, midpoint

\- First detected, last tested

\- Test count, held count

\- Broken status



\*\*Logic:\*\*

\- Price returns to stored OB and bounces: test\_count + 1, held\_count + 1

\- Price breaks through: broken = TRUE

\- Tested 3+ times and held each time = MAJOR INSTITUTIONAL ZONE

\- Price near major OB = Extra confidence, boost signal score by 2-3 points



\*\*Database:\*\* `order\_block\_memory` table



\### MODULE 5 — RELATIVE STRENGTH DIVERGENCE



\*\*Purpose:\*\* Detect when stock moves significantly different from market.



\*\*Hidden Accumulation:\*\*

\- NIFTY flat or slightly down (-0.3% to +0.3%)

\- Stock holding strong or moving up (>1.5% divergence)

\- = Institutions accumulating secretly = BULLISH



\*\*Hidden Distribution:\*\*

\- NIFTY flat or slightly up (-0.3% to +0.3%)

\- Stock falling or underperforming badly (<-1.5% divergence)

\- = Institutions distributing quietly = BEARISH



\*\*Threshold:\*\* NIFTY move between -0.3% and +0.3%, Stock divergence >1.5%



---



\## 10. BIG MONEY CONFLUENCE SCORE



\*\*Combine all Big Money signals into one score:\*\*



| Signal | Points |

|--------|--------|

| FII buying trend (3+ days) | +20 |

| Bulk deal same direction | +20 |

| Unusual options activity | +20 |

| Historical OB zone nearby | +20 |

| RS divergence detected | +20 |

| \*\*Maximum\*\* | \*\*100\*\* |



\*\*Integration Rules:\*\*

1\. Big Money Score is CONTEXT only

2\. Weight in composite = 0%

3\. Never blocks signal

4\. Enhances Risk Grade only



\*\*Risk Grade Upgrade Rules:\*\*



| Base Grade | Big Money Score | Final Grade |

|------------|----------------|-------------|

| B (86) | 80+ | \*\*B+\*\* |

| B+ (87-89) | 80+ | \*\*A\*\* |

| A (90-94) | 80+ | \*\*A+\*\* |

| A+ (95+) | Any | \*\*A+\*\* (no change) |



---



\## 11. ARC ENGINE — CLAUDE API



\*\*Role:\*\* Pre-market and post-market ONLY. Never used in live 60-second scan.  

\*\*Weight:\*\* 0% — does not affect score.  

\*\*Role:\*\* Veto power only.



\### Pre-Market at 08:20 AM:

\- Reviews watchlist as batch

\- For each stock returns: APPROVE or CAUTION or REJECT

\- \*\*REJECT = Stock removed from watchlist, no alerts for that stock today\*\*

\- \*\*CAUTION = Stock stays on watchlist but all alerts tagged with ARC: CAUTION\*\*

\- \*\*APPROVE = Stock on watchlist, normal processing\*\*



\*\*Updated Prompt (v4.6):\*\*

Include Big Money context:

\- FII Trend: \[X days buying or selling]

\- Bulk Deals Today: \[any or NONE]

\- Big Money Score: \[XX out of 100]

\- OB Zone: \[near or not near]

\- RS Divergence: \[detected or not]



\### Post-Market at 04:00 PM:

\- Reviews flagged signals

\- Input for next day watchlist



\### ARC Failure Policy:

\- If Claude API times out: Skip ARC review

\- Mark stocks as UNREVIEWED

\- Publish watchlist anyway

\- Human manually checks

\- All UNREVIEWED stocks get "ARC: UNREVIEWED" tag on alerts



---



\## 12. GEIE ENGINE — GEMINI API



\*\*Model:\*\* Gemini Flash  

\*\*Runs:\*\* Pre-market 08:05 AM only  

\*\*Cached:\*\* In Redis, valid all day  

\*\*Live scan:\*\* Uses cache only, no API call



\*\*Purpose:\*\* Map global and India news to NIFTY 50 stock level impact.



\*\*Updated Prompt (v4.6):\*\*

Also analyze:

\- FII trend for last 5 days

\- Any major block deals yesterday

\- Options OI concentration levels

\- Where are the major support zones



\*\*Output JSON format (mandatory):\*\*

```json

{

&nbsp; "event\_id": "GEIE-YYYY-MM-DD-001",

&nbsp; "timestamp": "IST timestamp",

&nbsp; "market\_sentiment": "RISK\_ON",

&nbsp; "stock\_impacts": {

&nbsp;   "TATASTEEL": {

&nbsp;     "direction": "POSITIVE",

&nbsp;     "magnitude": 2,

&nbsp;     "reasons": \["China production cuts"],

&nbsp;     "confidence": "HIGH",

&nbsp;     "urgency": "INTRADAY"

&nbsp;   }

&nbsp; },

&nbsp; "fii\_5day\_trend": "BUYING or SELLING or MIXED",

&nbsp; "institutional\_bias": "BULLISH or BEARISH or NEUTRAL",

&nbsp; "key\_support\_from\_options": "price level",

&nbsp; "key\_resistance\_from\_options": "price level",

&nbsp; "top\_beneficiaries": \["TATASTEEL", "JSWSTEEL"],

&nbsp; "top\_losers": \["MARUTI", "TATAMOTORS"],

&nbsp; "geie\_status": "ACTIVE"

}

```



\*\*Note:\*\* `magnitude` field (1-3 scale) is for human reference only. Only `direction` is used by the system. Weight in composite score = 0%.



\### GEIE Failure Policy:

\- If Gemini API times out or errors: Mark GEIE\_STATUS as UNAVAILABLE

\- Log to audit

\- System continues normally

\- NEVER block any alert

\- Use last valid snapshot from Redis

\- Snapshot valid for 60 minutes

\- After 60 min with no valid snapshot: All stocks default to NEUTRAL



---



\## 13. GEIE MASTER MAP — ALL 50 STOCKS



\[Same as v4.5 — no changes to content]



\### Metals

\*\*TATASTEEL:\*\*

\- positive: steel\_price\_up, china\_production\_cuts, infra\_spending\_up, govt\_stimulus

\- negative: china\_dumping, coal\_cost\_up, domestic\_demand\_down



\*\*JSWSTEEL:\*\*

\- positive: steel\_price\_up, china\_production\_cuts, infra\_spending\_up

\- negative: china\_dumping, coal\_cost\_up, iron\_ore\_cost\_up



\*\*HINDALCO:\*\*

\- positive: aluminum\_price\_up, global\_demand\_up, auto\_demand

\- negative: aluminum\_price\_down, coal\_cost\_up, china\_dumping



\### Banking

\*\*HDFCBANK:\*\*

\- positive: gdp\_growth, credit\_growth, rate\_cut, fii\_inflow

\- negative: rate\_hike, npa\_rise, regulatory\_tightening



\*\*ICICIBANK:\*\*

\- positive: gdp\_growth, credit\_growth, rate\_cut, fii\_inflow

\- negative: rate\_hike, npa\_rise, regulatory\_tightening



\*\*SBIN:\*\*

\- positive: govt\_spending, rate\_cut, psu\_revival, infra\_projects

\- negative: rate\_hike, npa\_rise, privatization\_fear



\*\*KOTAKBANK:\*\*

\- positive: gdp\_growth, credit\_growth, rate\_cut, fii\_inflow

\- negative: rate\_hike, npa\_rise



\*\*AXISBANK:\*\*

\- positive: gdp\_growth, credit\_growth, rate\_cut, fii\_inflow

\- negative: rate\_hike, npa\_rise



\*\*INDUSINDBK:\*\*

\- positive: gdp\_growth, credit\_growth, rate\_cut, fii\_inflow

\- negative: rate\_hike, npa\_rise, regulatory\_tightening



\*\*BAJFINANCE:\*\*

\- positive: credit\_growth, consumer\_demand, rate\_cut, fintech\_growth

\- negative: rate\_hike, npa\_rise, regulatory\_tightening



\*\*BAJAJFINSV:\*\*

\- positive: insurance\_growth, rate\_cut

\- negative: rate\_hike, claims\_spike



\### IT

\*\*INFY:\*\*

\- positive: usd\_strong, us\_it\_spend\_up, digital\_transformation, ai\_adoption

\- negative: usd\_weak, us\_recession, immigration\_restrictions



\*\*TCS:\*\*

\- positive: usd\_strong, us\_it\_spend\_up, digital\_transformation

\- negative: usd\_weak, us\_recession, immigration\_restrictions



\*\*HCLTECH:\*\*

\- positive: usd\_strong, us\_it\_spend\_up, digital\_transformation

\- negative: usd\_weak, us\_recession



\*\*WIPRO:\*\*

\- positive: usd\_strong, us\_it\_spend\_up

\- negative: usd\_weak, us\_recession, margin\_pressure



\*\*TECHM:\*\*

\- positive: usd\_strong, us\_it\_spend\_up, auto\_tech

\- negative: usd\_weak, us\_recession



\### Energy

\*\*RELIANCE:\*\*

\- positive: refining\_margins\_up, energy\_demand\_growth, jio\_growth

\- negative: windfall\_tax, oil\_price\_crash, regulatory\_restrictions



\*\*ONGC:\*\*

\- positive: oil\_price\_up, govt\_support

\- negative: oil\_price\_crash, windfall\_tax, subsidy\_burden



\*\*BPCL:\*\*

\- positive: crude\_price\_down, marketing\_margin\_up

\- negative: crude\_price\_up, subsidy\_burden



\*\*NTPC:\*\*

\- positive: power\_demand\_up, renewable\_push, govt\_spending

\- negative: coal\_shortage, regulatory\_delay



\*\*POWERGRID:\*\*

\- positive: power\_demand\_up, transmission\_expansion

\- negative: regulatory\_delay, land\_acquisition\_issues



\*\*COALINDIA:\*\*

\- positive: power\_demand\_up, coal\_price\_up

\- negative: renewable\_push, environmental\_restrictions



\### Auto

\*\*MARUTI:\*\*

\- positive: rate\_cut, rural\_demand\_up, commodity\_cost\_down

\- negative: steel\_cost\_up, fuel\_price\_up, rate\_hike



\*\*TATAMOTORS:\*\*

\- positive: ev\_adoption, jlr\_recovery, commodity\_cost\_down

\- negative: steel\_cost\_up, chip\_shortage, uk\_recession



\*\*M\&M:\*\*

\- positive: tractor\_demand\_up, rural\_growth, suv\_demand, rate\_cut

\- negative: steel\_cost\_up, fuel\_price\_up, rate\_hike



\*\*BAJAJ-AUTO:\*\*

\- positive: two\_wheeler\_demand, export\_growth, rate\_cut

\- negative: fuel\_price\_up, rate\_hike, electric\_competition



\*\*HEROMOTOCO:\*\*

\- positive: two\_wheeler\_demand, rural\_growth, rate\_cut

\- negative: fuel\_price\_up, rate\_hike, electric\_competition



\*\*EICHERMOT:\*\*

\- positive: premium\_bike\_demand, export\_growth, rate\_cut

\- negative: fuel\_price\_up, rate\_hike, electric\_competition



\### Pharma

\*\*SUNPHARMA:\*\*

\- positive: fda\_approval, patent\_wins, generic\_boom, us\_demand\_up

\- negative: fda\_warning, patent\_loss, pricing\_pressure



\*\*DRREDDY:\*\*

\- positive: fda\_approval, patent\_wins, generic\_boom

\- negative: fda\_warning, patent\_loss, pricing\_pressure



\*\*CIPLA:\*\*

\- positive: fda\_approval, generic\_boom, api\_demand

\- negative: fda\_warning, pricing\_pressure



\*\*DIVISLAB:\*\*

\- positive: api\_demand, china\_alternative, fda\_approval

\- negative: china\_competition, fda\_warning



\### FMCG

\*\*HINDUNILVR:\*\*

\- positive: rural\_demand\_up, monsoon\_good, premiumization

\- negative: inflation\_up, rural\_distress



\*\*ITC:\*\*

\- positive: cigarette\_volume\_up, hotel\_recovery, fmcg\_growth

\- negative: tax\_hike\_cigarette, esg\_pressure



\*\*NESTLEIND:\*\*

\- positive: urban\_demand\_up, premiumization

\- negative: inflation\_up, input\_cost\_up



\*\*BRITANNIA:\*\*

\- positive: rural\_demand\_up, monsoon\_good, inflation\_down

\- negative: inflation\_up, input\_cost\_up



\*\*TATACONSUM:\*\*

\- positive: beverage\_demand, premiumization

\- negative: inflation\_up, input\_cost\_up



\### Infrastructure

\*\*LT:\*\*

\- positive: infra\_spending, govt\_capex, order\_book\_up

\- negative: interest\_rate\_up, execution\_delay



\*\*ULTRACEMCO:\*\*

\- positive: infra\_spending, housing\_demand

\- negative: fuel\_cost\_up, competition



\*\*GRASIM:\*\*

\- positive: cement\_demand, textile\_recovery

\- negative: fuel\_cost\_up, cotton\_price\_up



\*\*ADANIENT:\*\*

\- positive: infra\_spending, cement\_demand, energy\_transition

\- negative: regulatory\_scrutiny, debt\_concerns



\*\*ADANIPORTS:\*\*

\- positive: trade\_growth, port\_expansion, logistics\_boom

\- negative: trade\_war, regulatory\_scrutiny



\### Others

\*\*BHARTIARTL:\*\*

\- positive: tariff\_hike, 5g\_rollout, data\_consumption\_up

\- negative: tariff\_war, regulatory\_fine



\*\*ASIANPAINT:\*\*

\- positive: housing\_demand, monsoon\_good, premiumization

\- negative: input\_cost\_up, competition



\*\*TITAN:\*\*

\- positive: gold\_price\_up, wedding\_season, premiumization

\- negative: gold\_price\_crash, competition



\*\*APOLLOHOSP:\*\*

\- positive: healthcare\_spending, insurance\_penetration

\- negative: regulatory\_price\_cap, input\_cost\_up



\*\*SBILIFE:\*\*

\- positive: insurance\_penetration, rate\_cut, vnb\_margin\_up

\- negative: rate\_hike, claims\_spike



\*\*HDFCLIFE:\*\*

\- positive: insurance\_penetration, rate\_cut, vnb\_margin\_up

\- negative: rate\_hike, claims\_spike



\*\*UPL:\*\*

\- positive: monsoon\_good, global\_agri\_demand

\- negative: monsoon\_bad, generic\_competition



---



\## 14. TELEGRAM ALERT FORMAT



Every alert must look exactly like this:



```

🚨 IIIS SIGNAL ALERT



Signal ID: IIIS-YYYY-MM-DD-NNN

Time: HH:MM AM IST

Valid Until: HH:MM AM IST (calculated from regime rules, Section 16)



Stock: SYMBOL

Direction: LONG or SHORT

Score: XX out of 100

Confidence: HIGH or MEDIUM or LOW

Risk Grade: A+ or A or B+ or B or C



Market Context:

Regime: \[Trend Day / Expiry Day / Reversal Day / Transition Day / Range Day]

Sector Rank: \[number]

RS Percentile: \[number]

Volume: \[N]x average

VIX: \[number]



Trade Levels:

Entry Zone: XXX to XXX

Stop Loss: XXX

Target 1: XXX (1.5R)

Target 2: XXX (2.5R)

Quantity: NNN shares

Risk: ₹XXX (0.5%)



Intelligence:

GEIE Direction: POSITIVE or NEGATIVE or NEUTRAL or UNAVAILABLE

GEIE Reason: \[one line here]

Historical Win Rate: XX% (N setups found)

ARC Pre-Market: APPROVE or CAUTION or REJECT or UNREVIEWED



SMC Structure: \[5m signal] + \[15m signal]

Options: \[build-up type here]



💰 BIG MONEY SIGNALS

FII Trend: \[BUYER/SELLER] \[N] days \[✅/❌]

Bulk Deal: \[Rs XXCr BUY/SELL at HH:MM] \[✅/❌]

Options: \[PUT/CALL writing heavy at strike] \[✅/❌]

OB Zone: \[level] (tested \[N]x, held \[N]x) \[✅/❌]

RS Diverge: \[+/-X.X%] vs NIFTY \[+/-X.X%] \[✅/❌]

Big Money Score: \[XX]/100

Conclusion: \[Institutions accumulating/distributing/neutral]



⚠️ This is an intelligence alert only.

Human decision required.

System never executes trades.

Alert expires: HH:MM AM IST

```



---



\## 15. RISK GRADE DEFINITIONS



| Grade | Score Range | GEIE | Historical WR | Confidence | Big Money | Notes |

|-------|-------------|------|---------------|------------|-----------|-------|

| \*\*A+\*\* | > 95 | HIGH confidence | > 65% | HIGH | Any | Best quality |

| \*\*A\*\* | 90-94 | HIGH or MEDIUM | > 55% | HIGH | 80+ upgrades B+→A | |

| \*\*B+\*\* | 87-89 | MEDIUM | > 50% | MEDIUM | 80+ upgrades B→B+ | |

| \*\*B\*\* | 86 | LOW or NEUTRAL | > 45% | MEDIUM | Any | Minimum passing score |

| \*\*C\*\* | Any | Any | Any | Any | Any | CAUTION flag present |



\*\*Upgrade Rules:\*\*

\- Base B (86) + Big Money ≥80 = Final B+

\- Base B+ (87-89) + Big Money ≥80 = Final A

\- Base A (90-94) + Big Money ≥80 = Final A+

\- Base A+ (95+) = No upgrade needed



\*\*Note:\*\* Score 85 is REJECTED. Grade B starts at 86.



---



\## 16. ALERT VALIDITY \& COOLDOWN RULES



\### Alert Validity by Regime



| Regime | Validity Period |

|--------|-----------------|

| Trend Day | 15 minutes |

| Expiry Day | 5 minutes |

| Reversal Day | 10 minutes |

| Transition Day | 10 minutes (alerts blocked anyway) |

| Range Day | 10 minutes (alerts blocked anyway) |



\- Auto expiry always enabled

\- Valid until = Alert time + validity period

\- After expiry, signal status changes to EXPIRED



\### Alert Cooldown



\*\*Standard Cooldown:\*\*

\- Same stock, same direction = 30 minute wait from last alert expiry



\*\*Cooldown Exception (allows immediate re-alert):\*\*

\- Score improves by 10 or more points AND

\- New market regime detected (different from previous alert's regime)



\*\*Exception does NOT apply if:\*\*

\- Same regime, even with +10 score improvement

\- Different direction (treated as new signal, no cooldown)



---



\## 17. RISK MANAGEMENT



| Parameter | Value |

|-----------|-------|

| Risk per trade | 0.5% of capital |

| Maximum daily risk | 2% of capital |

| Hard stop | 3 consecutive losses |

| After hard stop | No alerts until next day (03:30 PM reset) |



\### Position Size Formula

```

Size = (Capital × 0.5%) ÷ max((Entry − Stop Loss), Entry × 0.001)

```



\### VIX Position Adjustment

| VIX Level | Position Size |

|-----------|---------------|

| Below 15 | 100% (full size) |

| 15 to 20 | 75% of calculated size |

| Above 20 | 50% of calculated size |



\- Maximum single position: 10% of capital

\- Daily reset at 03:30 PM: Risk counters reset to zero, consecutive loss counter resets



---



\## 18. DATABASE SCHEMA — 16 TABLES



\### TABLE 1: market\_data (TimescaleDB)

```sql

CREATE TABLE market\_data (

&nbsp;   time TIMESTAMPTZ NOT NULL,

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   open DECIMAL(12,4),

&nbsp;   high DECIMAL(12,4),

&nbsp;   low DECIMAL(12,4),

&nbsp;   close DECIMAL(12,4),

&nbsp;   volume BIGINT,

&nbsp;   vwap DECIMAL(12,4),

&nbsp;   timeframe VARCHAR(10) NOT NULL

);

SELECT create\_hypertable('market\_data', 'time', chunk\_time\_interval => INTERVAL '1 day');

```



\### TABLE 2: signals

```sql

CREATE TABLE signals (

&nbsp;   signal\_id VARCHAR(30) PRIMARY KEY,

&nbsp;   timestamp TIMESTAMPTZ NOT NULL,

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),

&nbsp;   score DECIMAL(5,2) NOT NULL CHECK (score > 85.0),

&nbsp;   confidence VARCHAR(10) NOT NULL CHECK (confidence IN ('HIGH', 'MEDIUM', 'LOW')),

&nbsp;   regime VARCHAR(20) NOT NULL,

&nbsp;   entry\_low DECIMAL(12,4) NOT NULL,

&nbsp;   entry\_high DECIMAL(12,4) NOT NULL,

&nbsp;   stop\_loss DECIMAL(12,4) NOT NULL,

&nbsp;   target\_1 DECIMAL(12,4) NOT NULL,

&nbsp;   target\_2 DECIMAL(12,4) NOT NULL,

&nbsp;   quantity INTEGER NOT NULL,

&nbsp;   risk\_amount DECIMAL(12,2) NOT NULL,

&nbsp;   geie\_direction VARCHAR(20),

&nbsp;   geie\_confidence VARCHAR(10),

&nbsp;   arc\_decision VARCHAR(20),

&nbsp;   historical\_wr DECIMAL(5,2),

&nbsp;   historical\_sample INTEGER,

&nbsp;   risk\_grade VARCHAR(5) NOT NULL,

&nbsp;   status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'HIT\_SL', 'HIT\_T1', 'HIT\_T2', 'CANCELLED')),

&nbsp;   valid\_until TIMESTAMPTZ NOT NULL,

&nbsp;   created\_at TIMESTAMPTZ DEFAULT NOW()

);

```



\### TABLE 3: active\_alerts

```sql

CREATE TABLE active\_alerts (

&nbsp;   alert\_id SERIAL PRIMARY KEY,

&nbsp;   signal\_id VARCHAR(30) REFERENCES signals(signal\_id),

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   direction VARCHAR(10) NOT NULL,

&nbsp;   sector VARCHAR(50) NOT NULL,

&nbsp;   triggered\_at TIMESTAMPTZ NOT NULL,

&nbsp;   expires\_at TIMESTAMPTZ NOT NULL

);

```



\### TABLE 4: risk\_state

```sql

CREATE TABLE risk\_state (

&nbsp;   session\_date DATE UNIQUE NOT NULL,

&nbsp;   daily\_risk\_used DECIMAL(5,2) DEFAULT 0,

&nbsp;   consecutive\_losses INTEGER DEFAULT 0,

&nbsp;   hard\_stop\_active BOOLEAN DEFAULT FALSE,

&nbsp;   total\_signals INTEGER DEFAULT 0,

&nbsp;   signals\_hit\_sl INTEGER DEFAULT 0,

&nbsp;   signals\_hit\_t1 INTEGER DEFAULT 0,

&nbsp;   signals\_hit\_t2 INTEGER DEFAULT 0,

&nbsp;   updated\_at TIMESTAMPTZ DEFAULT NOW()

);

```



\### TABLE 5: regime\_history

```sql

CREATE TABLE regime\_history (

&nbsp;   id SERIAL PRIMARY KEY,

&nbsp;   timestamp TIMESTAMPTZ NOT NULL,

&nbsp;   regime VARCHAR(20) NOT NULL,

&nbsp;   regime\_score DECIMAL(5,2) NOT NULL,

&nbsp;   adx DECIMAL(8,4),

&nbsp;   nifty\_price DECIMAL(12,4),

&nbsp;   ad\_ratio DECIMAL(5,2),

&nbsp;   notes TEXT

);

```



\### TABLE 6: audit\_log

```sql

CREATE TABLE audit\_log (

&nbsp;   id BIGSERIAL PRIMARY KEY,

&nbsp;   timestamp TIMESTAMPTZ DEFAULT NOW(),

&nbsp;   component VARCHAR(50) NOT NULL,

&nbsp;   action VARCHAR(100) NOT NULL,

&nbsp;   result VARCHAR(50) NOT NULL,

&nbsp;   reason TEXT,

&nbsp;   metadata JSONB

);

CREATE INDEX idx\_audit\_timestamp ON audit\_log(timestamp);

-- RULE: Never delete. Never update. Append only forever.

```



\### TABLE 7: system\_health

```sql

CREATE TABLE system\_health (

&nbsp;   id SERIAL PRIMARY KEY,

&nbsp;   checked\_at TIMESTAMPTZ NOT NULL,

&nbsp;   component VARCHAR(50) NOT NULL,

&nbsp;   status VARCHAR(20) NOT NULL,

&nbsp;   response\_time\_ms INTEGER,

&nbsp;   ghost\_mode\_active BOOLEAN DEFAULT FALSE,

&nbsp;   last\_error TEXT

);

```



\### TABLE 8: geie\_events

```sql

CREATE TABLE geie\_events (

&nbsp;   event\_id VARCHAR(50) PRIMARY KEY,

&nbsp;   timestamp TIMESTAMPTZ NOT NULL,

&nbsp;   event\_name VARCHAR(100),

&nbsp;   impact\_direction VARCHAR(20),

&nbsp;   confidence VARCHAR(10),

&nbsp;   urgency VARCHAR(20),

&nbsp;   beneficiaries JSONB,

&nbsp;   losers JSONB,

&nbsp;   neutral JSONB,

&nbsp;   raw\_output JSONB

);

```



\### TABLE 9: geie\_master\_map

```sql

CREATE TABLE geie\_master\_map (

&nbsp;   symbol VARCHAR(20) PRIMARY KEY,

&nbsp;   positive\_triggers TEXT\[],

&nbsp;   negative\_triggers TEXT\[],

&nbsp;   neutral\_triggers TEXT\[],

&nbsp;   last\_updated TIMESTAMPTZ DEFAULT NOW()

);

```



\### TABLE 10: options\_data

```sql

CREATE TABLE options\_data (

&nbsp;   time TIMESTAMPTZ NOT NULL,

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   strike DECIMAL(12,4) NOT NULL,

&nbsp;   expiry DATE NOT NULL,

&nbsp;   option\_type VARCHAR(5) NOT NULL CHECK (option\_type IN ('CE', 'PE')),

&nbsp;   oi BIGINT,

&nbsp;   oi\_change BIGINT,

&nbsp;   volume BIGINT,

&nbsp;   iv DECIMAL(8,4),

&nbsp;   ltp DECIMAL(12,4),

&nbsp;   PRIMARY KEY (time, symbol, strike, expiry, option\_type)

);

```



\### TABLE 11: earnings\_calendar

```sql

CREATE TABLE earnings\_calendar (

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   earnings\_date DATE NOT NULL,

&nbsp;   earnings\_time TIME,

&nbsp;   PRIMARY KEY (symbol, earnings\_date)

);

```



\### TABLE 12: event\_calendar

```sql

CREATE TABLE event\_calendar (

&nbsp;   event\_name VARCHAR(100) NOT NULL,

&nbsp;   event\_date DATE NOT NULL,

&nbsp;   event\_time TIME,

&nbsp;   impact\_level VARCHAR(20) NOT NULL,

&nbsp;   description TEXT,

&nbsp;   PRIMARY KEY (event\_name, event\_date)

);

```



\### TABLE 13: fii\_dii\_tracker (NEW v4.6)

```sql

CREATE TABLE fii\_dii\_tracker (

&nbsp;   date DATE PRIMARY KEY,

&nbsp;   fii\_action VARCHAR(10) NOT NULL CHECK (fii\_action IN ('BUYER', 'SELLER')),

&nbsp;   fii\_amount\_crores DECIMAL(12,2),

&nbsp;   dii\_action VARCHAR(10) NOT NULL CHECK (dii\_action IN ('BUYER', 'SELLER')),

&nbsp;   dii\_amount\_crores DECIMAL(12,2),

&nbsp;   combined\_bias VARCHAR(20) NOT NULL CHECK (combined\_bias IN ('BULLISH', 'BEARISH', 'NEUTRAL')),

&nbsp;   consecutive\_fii\_buy\_days INTEGER DEFAULT 0,

&nbsp;   consecutive\_fii\_sell\_days INTEGER DEFAULT 0,

&nbsp;   created\_at TIMESTAMPTZ DEFAULT NOW()

);

```



\### TABLE 14: bulk\_deal\_tracker (NEW v4.6)

```sql

CREATE TABLE bulk\_deal\_tracker (

&nbsp;   id SERIAL PRIMARY KEY,

&nbsp;   timestamp TIMESTAMPTZ NOT NULL,

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   deal\_type VARCHAR(10) NOT NULL CHECK (deal\_type IN ('BUY', 'SELL')),

&nbsp;   quantity BIGINT,

&nbsp;   price DECIMAL(12,4),

&nbsp;   value\_crores DECIMAL(12,2),

&nbsp;   client\_name VARCHAR(200),

&nbsp;   deal\_category VARCHAR(10) NOT NULL CHECK (deal\_category IN ('BULK', 'BLOCK')),

&nbsp;   created\_at TIMESTAMPTZ DEFAULT NOW()

);

CREATE INDEX idx\_bulk\_symbol ON bulk\_deal\_tracker(symbol);

CREATE INDEX idx\_bulk\_timestamp ON bulk\_deal\_tracker(timestamp);

```



\### TABLE 15: options\_intelligence (NEW v4.6)

```sql

CREATE TABLE options\_intelligence (

&nbsp;   date DATE NOT NULL,

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   max\_pain\_level DECIMAL(12,4),

&nbsp;   highest\_put\_oi\_strike DECIMAL(12,4),

&nbsp;   highest\_call\_oi\_strike DECIMAL(12,4),

&nbsp;   unusual\_activity\_detected BOOLEAN DEFAULT FALSE,

&nbsp;   unusual\_strike DECIMAL(12,4),

&nbsp;   unusual\_type VARCHAR(10) CHECK (unusual\_type IN ('CALL', 'PUT')),

&nbsp;   unusual\_oi\_change BIGINT,

&nbsp;   created\_at TIMESTAMPTZ DEFAULT NOW(),

&nbsp;   PRIMARY KEY (date, symbol)

);

```



\### TABLE 16: order\_block\_memory (NEW v4.6)

```sql

CREATE TABLE order\_block\_memory (

&nbsp;   id SERIAL PRIMARY KEY,

&nbsp;   symbol VARCHAR(20) NOT NULL,

&nbsp;   timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('5m', '15m', 'Daily')),

&nbsp;   ob\_type VARCHAR(10) NOT NULL CHECK (ob\_type IN ('BULLISH', 'BEARISH')),

&nbsp;   ob\_high DECIMAL(12,4) NOT NULL,

&nbsp;   ob\_low DECIMAL(12,4) NOT NULL,

&nbsp;   ob\_midpoint DECIMAL(12,4) NOT NULL,

&nbsp;   first\_detected TIMESTAMPTZ NOT NULL,

&nbsp;   last\_tested TIMESTAMPTZ,

&nbsp;   test\_count INTEGER DEFAULT 0,

&nbsp;   held\_count INTEGER DEFAULT 0,

&nbsp;   broken BOOLEAN DEFAULT FALSE,

&nbsp;   broken\_at TIMESTAMPTZ,

&nbsp;   created\_at TIMESTAMPTZ DEFAULT NOW()

);

CREATE INDEX idx\_ob\_symbol ON order\_block\_memory(symbol);

CREATE INDEX idx\_ob\_broken ON order\_block\_memory(broken) WHERE broken = FALSE;

```



---



\## 19. GHOST MODE



\### Triggers that Activate Ghost Mode

\- Upstox WebSocket feed fails

\- Database connection lost

\- Any single API fails 3 times in a row

\- Market data gap more than 2 minutes

\- 4 consecutive health check failures (120 seconds, aligned with 2-minute data gap threshold)



\### Actions when Ghost Mode Activates

\- Stop ALL new alerts immediately

\- Purge any pending alert queue

\- Continue monitoring and logging

\- Send Telegram message to admin

\- NEVER resume automatically

\- Wait for manual human approval



\### Ghost Mode Admin Message Format

```

🚨 GHOST MODE ACTIVATED



Reason: \[state reason here]

Time: \[timestamp here]



All alerts stopped.

Data integrity may be compromised.



Send /resume command to restart.

Manual verification required before resume.

```



---



\## 20. MONITORING



\- Health check runs every 30 seconds

\- Check all 7 components:

&nbsp; 1. Upstox WebSocket connection

&nbsp; 2. Perplexity API response

&nbsp; 3. Gemini API response

&nbsp; 4. Claude API response

&nbsp; 5. Telegram Bot status

&nbsp; 6. PostgreSQL connection

&nbsp; 7. Redis connection

\- Log every check to system\_health table

\- Alert admin if any component is DOWN

\- 4 consecutive failures = trigger Ghost Mode



---



\## 21. SESSION END PROTOCOL



| Time | Action |

|------|--------|

| 03:14:30 PM | Lock queue, no new alerts |

| 03:15:00 PM | Stop all alert generation |

| 03:20:00 PM | Close all monitoring loops |

| 03:30:00 PM | Freeze session and reset counters |

| 04:00:00 PM | Run ARC post-market batch |

| 04:30:00 PM | Generate and send EOD report |



\### EOD Report Must Include

\- Total stocks scanned today

\- Total signals generated

\- Total alerts sent

\- Total alerts rejected and why (per gate)

\- Daily risk percentage used

\- Consecutive loss count

\- Regime accuracy assessment

\- GEIE direction accuracy

\- Historical pattern accuracy

\- Big Money signals detected today

\- System uptime and health summary

\- Next day watchlist draft



---



\## 22. DEVELOPMENT PHASES IN ORDER



\### Phase 1 — Infrastructure (Week 1-2)

\- Set up VPS primary and backup

\- Install PostgreSQL with TimescaleDB

\- Install Redis

\- Create Docker setup

\- Create all 16 database tables

\- Set up environment variables

\- Build health monitoring system

\- Build Ghost Mode system

\- Build audit logging system

\- Test all connections

\- \*\*Do not proceed until all tests pass\*\*



\### Phase 2 — Market Data (Week 3)

\- Integrate Upstox API V3

\- Build WebSocket connection with auto-reconnect

\- Build REST fallback for WebSocket failure

\- Build OHLC candle constructor from tick data

\- Build 1m, 5m, 15m, 30m, Daily candle builder

\- Build instrument master loader for NIFTY 50

\- Test live data flow for all 50 stocks

\- Verify latency under 100ms



\### Phase 3 — Multi Timeframe Engine (Week 4)

\- Build trend calculator for each timeframe

\- Build alignment scorer across timeframes

\- Minimum 3 of 4 alignment rule (same direction)



\### Phase 4 — SMC Engine (Week 5)

\- Build BOS detector for 5m and 15m

\- Build CHOCH detector for 5m and 15m

\- Build Order Block detector for 5m and 15m

\- Build FVG detector for 5m and 15m

\- Build cross-timeframe validator

\- Enforce 5m + 15m mandatory rule

\- Build direction mapping logic



\### Phase 5 — Options Engine (Week 6)

\- Build option chain fetcher from Upstox

\- Build PCR calculator

\- Build OI change tracker

\- Build buildup classifier

\- Build 5-minute scheduler (synchronized to market clock)

\- Build event-driven trigger on SMC



\### Phase 6 — Scoring Engine (Week 7)

\- Build all 7 individual engines (Regime, RS, RVOL, Breadth, Options, Sector, SMC Quality)

\- Build composite score calculator

\- Build regime detector

\- Build sector mapper

\- Enforce score threshold strictly > 85



\### Phase 7 — Risk Gates (Week 8)

\- Build all 8 gates in order

\- Build earnings calendar loader (24-hour Asia/Kolkata window)

\- Build event calendar loader (RBI, Fed, CPI, GDP, Budget, MPC)

\- Build VIX adjustment logic

\- Build ATR-based pause logic

\- Ensure gates run before AI layers



\### Phase 8 — Backtesting Engine (Week 9-10)

\- Build historical data downloader

\- Build signal replay engine

\- Build performance metrics calculator

\- Run 90 days of backtest

\- Validate: Profit Factor above 1.5, Drawdown below 15%, Win Rate above 45%

\- Fix any issues before proceeding



\### Phase 9 — GEIE Engine (Week 11)

\- Build Perplexity integration

\- Build Gemini integration

\- Build master correlation map loader with all 50 stocks

\- Build Redis caching for GEIE output (60-min fallback)

\- Build failure handling (NEVER block alerts)

\- Test end-to-end



\### Phase 10 — Historical Pattern Engine (Week 12)

\- Build similar setup searcher (90-day lookback)

\- Build win rate calculator

\- Build confidence scorer

\- Enforce minimum 10 setup rule

\- Build direction mapping from SMC



\### Phase 11 — ARC Engine (Week 13)

\- Build Claude API integration

\- Build pre-market batch processor (08:20 AM)

\- Build post-market reviewer (04:00 PM)

\- Build failure handling (UNREVIEWED fallback)

\- Build veto logic (REJECT removes from watchlist)



\### Phase 12 — Telegram System (Week 14)

\- Build Telegram bot

\- Build alert formatter with exact format (including Big Money section)

\- Build alert validity timer (regime-based)

\- Build auto expiry system

\- Build cooldown tracker (30-min standard, +10 score + regime change exception)

\- Build admin alert system

\- Build Ghost Mode messaging



\### Phase 13 — Big Money Module (Week 15-16) \[NEW v4.6]

\- Build FII/DII tracker (NSE data fetch)

\- Build bulk deal monitor (15-min scan)

\- Build options big money detector (unusual activity, max pain, OI zones)

\- Build order block memory database

\- Build RS divergence detector

\- Build Big Money confluence score calculator

\- Integrate into live scan (Step 15)

\- Update Telegram format with Big Money section

\- Update Risk Grade with upgrade logic



\### Phase 14 — Paper Trading (Week 17-20)

\- Run live paper trading for 30 days

\- Track all metrics including Big Money accuracy

\- Fix any bugs found

\- Validate system performance



\### Phase 15 — Live Production (Week 21 onward)

\- Start with ₹50,000 capital

\- Run for 30 days. Review results.

\- If profitable: increase to ₹2,00,000

\- Run for 30 days. Review results.

\- If profitable: increase to ₹10,00,000

\- Then full deployment



---



\## 23. NON-NEGOTIABLE RULES



NEVER violate these under any condition:



1\. Human always makes final trade decision.

2\. System NEVER executes any trade.

3\. Score threshold is strictly above 85 (≥ 86.0).

4\. Risk per trade is always 0.5%.

5\. Maximum daily risk is always 2%.

6\. Hard stop at 3 consecutive losses.

7\. All 8 gates always run before AI.

8\. ATR period always 14 on 15m chart.

9\. RVOL always uses 20-day average.

10\. Ghost Mode always requires manual resume.

11\. GEIE failure never blocks any alert.

12\. ARC never runs in live 60-second scan.

13\. Maximum 4 active alerts at any time.

14\. Maximum 2 same sector per 30 minutes.

15\. Alert cooldown 30 min same stock same direction.

16\. GEIE weight in scoring is 0%.

17\. ARC weight in scoring is 0%.

18\. All API keys in environment variables.

19\. Audit log is never deleted.

20\. No hardcoded credentials anywhere.

21\. \*\*Big Money Score weight = 0%. Context only.\*\*

22\. \*\*Big Money affects Risk Grade only. Not numerical score.\*\*

23\. \*\*Big Money Score 0 = signal proceeds normally. Enhancement only.\*\*

24\. \*\*Bulk deal monitor never blocks alert. Information only.\*\*

25\. \*\*FII data from NSE official only. No third party estimates.\*\*



---



\## 24. ERRATA: v4.4 → v4.6 CHANGES



\### Critical Fixes (from v4.5)



| # | Issue | v4.4 Problem | v4.5/v4.6 Fix |

|---|-------|-------------|---------------|

| 1 | Score Threshold / Risk Grade | Grade B covered "85-86" but 85 rejected | Grade B = Score 86 only. LOW starts at 86. |

| 2 | Undefined "Signal Quality" | 10% weight but never defined | Renamed to "SMC Signal Quality" with explicit scoring |

| 3 | SMC Direction Mapping | Structure detected but no Long/Short mapping | Added explicit direction mapping rules |

| 4 | Gate 8 Volatility Confusion | Mixed VIX/ATR under same header | Split: VIX = position reduction, ATR = pause |

| 5 | Position Size Division by Zero | Could divide by zero | Guard: min stop = 0.1% of entry |



\### Moderate Fixes (from v4.5)



| # | Issue | Fix |

|---|-------|-----|

| 6 | Options Engine Timing | Specified: 5-min market-clock sync + event-driven priority |

| 7 | GEIE Score Field | Renamed to "magnitude" (human ref only) |

| 8 | ARC Veto Power | Explicit: REJECT = remove from watchlist |

| 9 | Cooldown Exception | Requires BOTH +10 score AND new regime |

| 10 | RVOL Score | Linear interpolation between thresholds |

| 11 | NIFTY Return | Explicit calculation over same weighted periods |

| 12 | Multi Timeframe | Must align in SAME DIRECTION |



\### v4.6 Big Money Additions



| # | Addition | Description |

|---|----------|-------------|

| 13 | 16-Step Live Scan | Added Step 15: Big Money Confluence Check |

| 14 | 4 New Database Tables | fii\_dii\_tracker, bulk\_deal\_tracker, options\_intelligence, order\_block\_memory |

| 15 | FII/DII Tracker | Daily NSE data, 5-day trend, combined bias |

| 16 | Bulk Deal Monitor | 15-min scan, ₹25Cr+ threshold, intraday flag |

| 17 | Options Big Money | Unusual activity (3x OI), max pain, OI concentration zones |

| 18 | Order Block Memory | Permanent OB database, test tracking, strength scoring |

| 19 | RS Divergence | Hidden accumulation/distribution detection |

| 20 | Big Money Confluence | 5-signal score (0-100), Risk Grade upgrade logic |

| 21 | Updated Telegram Format | Added 💰 Big Money Signals section |

| 22 | Updated Risk Grades | Big Money ≥80 upgrades: B→B+, B+→A, A→A+ |

| 23 | Updated GEIE Prompt | Added FII trend, block deals, OI levels |

| 24 | Updated ARC Prompt | Added Big Money context for decisions |

| 25 | New Phase 13 | Big Money Module (Week 15-16) |

| 26 | 25 Non-Negotiable Rules | Added Rules 21-25 for Big Money |



---



\*\*VERSION:\*\* IIIS v4.6 PRODUCTION  

\*\*STATUS:\*\* FROZEN — READY FOR PHASE 1  

\*\*NEXT STEP:\*\* BEGIN PHASE 1 (Infrastructure)



---



\## INSTRUCTION TO AI AGENT



You have read the complete corrected specification.

Now tell me:

1\. Confirm you understood everything.

2\. Ask me: Ready to start Phase 1?

3\. Wait for my go ahead.

4\. Build one phase at a time.

5\. Test before moving to next phase.

6\. Ask for my approval after each phase.

7\. Never skip any step.

8\. Never add features not in this spec.

9\. Never remove features from this spec.

10\. Follow non-negotiable rules always.



