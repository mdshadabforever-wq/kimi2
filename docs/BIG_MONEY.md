# Big Money Detection Module

This document defines the Big Money Detection Module and Confluence Score logic introduced in IIIS v4.6 to detect and trace institutional market activities.

---

## 1. Core Principles & Integration Rules

1. **Context Only:** The Big Money Confluence Score is for contextual reference only.
2. **Scoring Weight:** Weight in the composite scoring engine is strictly **0%**.
3. **No Blocking:** Big Money signals/scores do **never** block any signal from proceeding.
4. **Zero Impact Baseline:** If Big Money Score = 0, the signal proceeds normally.
5. **Risk Grading Impact:** Big Money affects the final **Risk Grade only**.

---

## 2. Big Money Detection Modules

The system tracks institutional activity across 5 distinct modules:

### MODULE 1 — FII/DII Tracker
* **Purpose:** Monitor daily institutional net buying and net selling to establish a daily bias.
* **Data Source:** Daily data from the NSE website via a Perplexity API scan at 8:00 AM.
* **Calculations:**
  * Daily net activity in crores for FII and DII.
  * Count of consecutive net buying/selling days for FII.
* **Logical Rules:**
  * **Bullish Bias:** Net FII buyer for $\ge 3$ consecutive days (supports long setups).
  * **Bearish Bias:** Net FII seller for $\ge 3$ consecutive days (suppresses long setups).
  * **Strong Bullish:** FII net buyer + DII net buyer on the same day.
  * **Strong Bearish:** FII net seller + DII net seller on the same day (suppresses long setups).
* **Database:** `fii_dii_tracker` table.

### MODULE 2 — Block and Bulk Deal Tracker
* **Purpose:** Detect large-value institutional transactions.
* **Pre-Market Block Deals:** Captured in the Perplexity 8:00 AM scan.
* **Intraday Bulk Deal Monitor:**
  * **Endpoint:** `https://www.nseindia.com/market-data/bulk-deal`
  * **Scan Frequency:** Every 15 minutes during live market hours.
  * **Filter Threshold:** Any block/bulk deal of **$\ge$ ₹25 crore** in value for Nifty 50 stocks.
  * **Flags:**
    * Bulk buy deal in Stock X $\rightarrow$ Add `INSTITUTIONAL BUY FLAG`.
    * Bulk sell deal in Stock X $\rightarrow$ Add `INSTITUTIONAL SELL FLAG`.
* **Database:** `bulk_deal_tracker` table.

### MODULE 3 — Options Big Money Detector
* **Purpose:** Monitor options volume, open interest shifts, and thresholds.
* **Unusual Options Activity:** Strikes where the intraday change in Open Interest (OI) is **$\ge 3$ times** the 20-day average.
  * Unusual Call Buying $\rightarrow$ Expects price to rise.
  * Unusual Put Buying $\rightarrow$ Expects price to fall.
  * Unusual Put Writing $\rightarrow$ Defending support zone.
* **Max Pain Tracker:** Daily calculation of the options Max Pain price point (displayed in Telegram on expiry days).
* **OI Concentration Zones:**
  * Highest Put OI strike $\rightarrow$ Represents strong support level.
  * Highest Call OI strike $\rightarrow$ Represents strong resistance level.
* **Database:** `options_intelligence` table.

### MODULE 4 — Smart Money Order Block Database
* **Purpose:** Build a persistent database of validated Order Blocks (OB).
* **Calculations:** Store symbol, timeframe, type (bullish/bearish), high, low, midpoint, first detected timestamp, last tested timestamp, test count, held count, and broken status.
* **Logical Rules:**
  * **Price Test:** When price returns to an active OB and bounces: `test_count = test_count + 1` and `held_count = held_count + 1`.
  * **Price Violation:** If price breaks completely through the OB range: `broken = TRUE` and `broken_at = timestamp`.
  * **Major Institutional Zone:** Any OB that has been tested $\ge 3$ times and held successfully.
  * **Confluence Boost:** If price is near a major OB, the signal score can be boosted by +2 to +3 points.
* **Database:** `order_block_memory` table.

### MODULE 5 — Relative Strength Divergence
* **Purpose:** Detect instances where a stock moves independently of the broader index.
* **Hidden Accumulation (Bullish):**
  * Nifty is flat/consolidating (moves between -0.3% and +0.3%).
  * Stock holds strong or rallies (Stock vs Nifty divergence **> 1.5%**).
* **Hidden Distribution (Bearish):**
  * Nifty is flat/consolidating (moves between -0.3% and +0.3%).
  * Stock drops or lags significantly (Stock vs Nifty divergence **< -1.5%**).
* **Divergence Threshold:** Nifty daily return within [-0.3%, +0.3%] and Stock divergence relative to Nifty index > 1.5%.

---

## 3. Big Money Confluence Score (0–100)

The Big Money Confluence Score aggregates all 5 signals to calculate institutional support:

| Signal Component | Points |
|---|---|
| FII net buying trend ($\ge 3$ days) | +20 |
| Bulk deal in the same direction | +20 |
| Unusual options activity | +20 |
| Historical Order Block zone nearby | +20 |
| RS Divergence detected | +20 |
| **Maximum Score** | **100** |

---

## 4. Risk Grade Upgrade Rules

A Big Money Confluence Score of **$\ge 80$** triggers an upgrade to the final Risk Grade by **+1 notch**:

| Base Risk Grade | Big Money Confluence Score | Final Upgraded Risk Grade |
|---|---|---|
| B (86) | $\ge 80$ | **B+** |
| B+ (87-89) | $\ge 80$ | **A** |
| A (90-94) | $\ge 80$ | **A+** |
| A+ ($\ge 95$) | Any | **A+** (no change) |
| C (any with Caution flag) | Any | **C** (no upgrade) |
