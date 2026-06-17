# IIIS v4.6 Development Phases and Non-Negotiable Rules

This document outlines the ordered development phases and the core non-negotiable rules for the IIIS v4.6 system as defined in the frozen specification.

---

## 1. Development Phases In Order

### Phase 1 — Infrastructure (Week 1-2)
* Set up VPS primary and backup.
* Install PostgreSQL with TimescaleDB extension.
* Install Redis cache.
* Create Docker configuration setup.
* Create all 16 core database tables.
* Set up environment variables configuration.
* Build the system health monitoring module.
* Build the Ghost Mode framework.
* Build the trigger-protected audit logging system.
* Test all connections and verify. **Do not proceed until all tests pass.**

### Phase 2 — Market Data (Week 3)
* Integrate Upstox API V3.
* Build the WebSocket connection manager with auto-reconnect logic.
* Build REST fallback for WebSocket connection failures.
* Build OHLC candle constructor from tick stream data.
* Build 1m, 5m, 15m, 30m, and Daily candle builders.
* Build the instrument master loader for Nifty 50 constituents.
* Test live data flow for all 50 constituent stocks.
* Verify processing latency remains strictly under 100ms.

### Phase 3 — Multi-Timeframe Engine (Week 4)
* Build the trend calculator module for each required timeframe.
* Build the alignment scorer across timeframes.
* Enforce the minimum 3 of 4 timeframe alignment rule in the same direction.

### Phase 4 — SMC Engine (Week 5)
* Build Break of Structure (BOS) detector for 5m and 15m timeframes.
* Build Change of Character (CHOCH) detector for 5m and 15m timeframes.
* Build Order Block (OB) detector for 5m and 15m timeframes.
* Build Fair Value Gap (FVG) detector for 5m and 15m timeframes.
* Build the cross-timeframe validator.
* Enforce the mandatory 5m + 15m confirmation rule.
* Build structure-to-direction mapping logic.

### Phase 5 — Options Engine (Week 6)
* Build the option chain data fetcher from Upstox.
* Build Put-Call Ratio (PCR) calculator.
* Build Option Open Interest (OI) change tracker.
* Build options build-up classifier.
* Build the 5-minute scheduler synchronized to the market clock.
* Build event-driven trigger integration with SMC.

### Phase 6 — Scoring Engine (Week 7)
* Build all 7 individual scoring sub-engines (Regime, RS, RVOL, Breadth, Options, Sector, SMC Quality).
* Build the composite score calculator.
* Build the market regime detector.
* Build the sector strength mapper.
* Enforce the composite score threshold strictly above 85 (i.e. $\ge 86.0$).

### Phase 7 — Risk Gates (Week 8)
* Build all 8 risk validation gates in execution order.
* Build the earnings calendar loader (with a 24-hour Asia/Kolkata timezone buffer).
* Build the event calendar loader (covering RBI, Fed, CPI, GDP, Budget, MPC).
* Build VIX adjustment logic for position sizing.
* Build ATR-based validation pause logic.
* Ensure all 8 risk gates execute before AI layers are invoked.

### Phase 8 — Backtesting Engine (Week 9-10)
* Build the historical market data downloader.
* Build the signal replay engine.
* Build the performance metrics calculator.
* Run a full 90-day backtest simulation.
* Validate performance requirements: Profit Factor above 1.5, Drawdown below 15%, and Win Rate above 45%.
* Fix any detected anomalies before proceeding.

### Phase 9 — GEIE Engine (Week 11)
* Build Perplexity API integration.
* Build Gemini API integration.
* Build the master correlation map loader for all 50 constituent stocks.
* Build Redis caching for GEIE output (with a 60-minute fallback duration).
* Build failure handling (GEIE outage must **never** block alerts).
* Perform end-to-end integration testing.

### Phase 10 — Historical Pattern Engine (Week 12)
* Build similar setup searcher (90-day lookback window).
* Build historical win rate calculator.
* Build the algorithmic confidence scorer (Step 13).
* Enforce the minimum 10 historical setup requirement rule.
* Build direction mapping logic from SMC.

### Phase 11 — ARC Engine (Week 13)
* Build Claude API integration.
* Build the pre-market batch processor (triggered at 08:20 AM IST).
* Build the post-market reviewer (triggered at 04:00 PM IST).
* Build failure fallback handling (marking symbols as UNREVIEWED or defaulting to CAUTION).
* Build veto logic (REJECT removes a symbol from the active watchlist).

### Phase 12 — Telegram System (Week 14)
* Build the Telegram bot client.
* Build the alert formatter (matching the exact layout, including the Big Money section).
* Build the alert validity timer (regime-based).
* Build the auto-expiration handler.
* Build the cooldown tracker (enforcing a 30-minute standard cooldown, with regime change exceptions).
* Build the admin alerting system.
* Build the Ghost Mode notification formatting handler.

### Phase 13 — Big Money Module (Week 15-16) [v4.6 Additions]
* Build FII/DII tracker (fetching NSE daily activity).
* Build the bulk deal monitor (scanning every 15 minutes).
* Build options big money detector (unusual activity, max pain, OI zones).
* Build the permanent Order Block memory database.
* Build the Relative Strength (RS) divergence detector.
* Build the Big Money confluence score calculator.
* Integrate into the 16-step live scan flow (Step 15).
* Update the Telegram alert formatter with the `💰 BIG MONEY SIGNALS` section.
* Update the Risk Grade module with the grade upgrade logic.

### Phase 14 — Paper Trading (Week 17-20)
* Execute live paper trading simulation for 30 days.
* Track all trading metrics (including Big Money signal accuracy).
* Fix any runtime bugs and exceptions.
* Validate overall system performance.

### Phase 15 — Live Production (Week 21 onward)
* Initialize live trading with ₹50,000 capital.
* Run for 30 days and review trading logs.
* If profitable: scale capital to ₹2,00,000.
* Run for 30 days and review trading logs.
* If profitable: scale capital to ₹10,00,000.
* Proceed to full deployment.

---

## 2. Non-Negotiable Rules

The following rules must never be violated under any condition:

1. **Final Decision:** A human operator always makes the final trade decision.
2. **No Auto-Execution:** The system **NEVER** executes any trade automatically.
3. **Score Threshold:** The composite score threshold is strictly above 85 (i.e. $\ge 86.0$).
4. **Risk Per Trade:** Risk per trade is always strictly 0.5% of total capital.
5. **Max Daily Risk:** Maximum cumulative daily risk is always strictly capped at 2.0%.
6. **Hard Stop:** The system activates a hard stop upon 3 consecutive losses.
7. **Risk Gates Precedence:** All 8 risk validation gates must run before any AI reviews or alert transmissions occur.
8. **ATR Period:** The ATR period must always be 14 on a 15-minute chart.
9. **RVOL Reference:** RVOL calculations must always use a 20-day historical average.
10. **Ghost Mode Manual Action:** Ghost Mode always requires manual `/resume` human commands; it never auto-resumes.
11. **GEIE Fail-Safe:** GEIE API failures must **never** block any alert.
12. **No Live ARC:** The ARC Engine never runs in the live 60-second scan (pre-market and post-market ONLY).
13. **Active Alerts Cap:** Maximum of 4 active alerts allowed at any time.
14. **Sector Concentration:** Maximum of 2 alerts from the same sector in any 30-minute window.
15. **Alert Cooldown:** Standard cooldown of 30 minutes for the same stock in the same direction.
16. **GEIE Scoring Weight:** GEIE weight in composite scoring is strictly 0%.
17. **ARC Scoring Weight:** ARC weight in composite scoring is strictly 0%.
18. **Secret Management:** All API keys and credentials must reside in environment variables.
19. **Log Immutability:** The `audit_log` is append-only and must never be deleted or updated.
20. **No Hardcoding:** No credentials, tokens, or private endpoints hardcoded anywhere in the codebase.
21. **Big Money Weight:** Big Money Confluence Score weight is strictly 0% (used as context only).
22. **Big Money Scoring Impact:** Big Money affects the final **Risk Grade only** (does not alter composite numerical score).
23. **Zero Confluence Signal:** A Big Money Confluence Score of 0 has no negative effect; the signal proceeds normally.
24. **Bulk Deal Fail-Safe:** The bulk deal monitor must **never** block an alert (information-only).
25. **FII Source Integrity:** FII daily data must be fetched from the official NSE website only (no third-party estimates).
