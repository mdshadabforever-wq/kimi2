# IIIS — Intelligent Institutional Investing System (v4.6)

IIIS (v4.6) is an agent-centric, institutional-grade passive trading intelligence observer dashboard and signal analysis engine. It runs live scan pipelines, calculates composite scores based on multi-timeframe trends, smart money concepts (SMC), and option flow indicators, and validates entries through sequential risk assessment gates.

## Current Project Status
* **Core Trading Signal Engine:** 100% complete and fully verified.
* **Founder OS Passive Observer Interface:** Completed. Includes live operating center (Today), Day Replay, Trade Stories, Notion-style memory intelligence archives, PDF report generator, AI Analyst diagnostic agent, and operations dashboard.
* **Testing Coverage:** 132 tests fully passing (zero regressions).
* **API Integrations:** Standard operations are currently simulated using stateful mock adapters to support development, testing, and UI validation without broker costs.

---

## Clean Codebase & Module Structure

* `/market_analysis` — Trend Engine, EMA calculation caches, multi-timeframe alignment engine.
* `/market_structure` — Smart Money Concepts (SMC) engine, order blocks, FVG, BOS, and CHOCH validators.
* `/options_engine` — PCR metrics, max pain calculations, and volume buildup analyzers.
* `/scoring_engine` — Composite score calculator aggregating 7 sub-scores (Regime, RS, RVOL, Breadth, Sector, SMC Quality, Options).
* `/risk_gates` — Sequential validation check (Liquidity, Correlation, Circuit breakers, choppiness filters, and consecutive loss limits).
* `/arc_engine` — Claude-driven pre-market watchlist reviewer and post-market signal auditor.
* `/geie_engine` — Gemini & Perplexity powered global/India macro-sentiment parser.
* `/dashboard` — CSS/HTML views for Today operating center, memory indexes, and daily intelligence reports.
* `/services` — MemoryEngine trade story logs, graveyard behavior compilers, and FPDF2-based EOD PDF compilers.
* `/mocks` — Stateful mock interfaces simulating Upstox WebSocket, Perplexity news queries, Gemini sentiment feeds, and Claude watchlists.

---

## Simulated Integrations In Use (MOCK_MODE=True)

To facilitate sandbox testing and offline verification, the following modules operate on stateful mocks:
1. **Upstox API V3 Mock:** Generates stateful price drifts, feeds simulated WebSocket ticks, and constructs dynamic option chains around the spot price.
2. **Perplexity API Mock:** Simulates premarket global/India macroeconomic news search strings.
3. **Gemini API Mock:** Simulates premarket news sentiment evaluations and sector rotation weights.
4. **Claude API Mock:** Simulates premarket watchlists reviews and daily post-market signal audits.
5. **NSE Mock:** Simulates daily FII/DII transaction flows and institutional block/bulk deals.

---

## Future Real API Integrations Required

To deploy IIIS v4.6 into live paper trading or production environments, mock classes must be replaced by active adapters implementing the corresponding interfaces:

1. **Upstox Live Adapter:**
   * Implement real connection to `wss://api-v2.upstox.com/feed/market-data-feed` using Protobuf decoding.
   * Call GET `https://api.upstox.com/v2/option/chain` to populate options tables for candidates.
   * Call GET `https://api.upstox.com/v2/historical-candle` to fetch the initial 150-candle warmup history.
2. **Perplexity Live API:**
   * Call POST `https://api.perplexity.ai/chat/completions` with Google Search grounding.
3. **Gemini Live API:**
   * Call Google Generative AI Python SDK (`gemini-1.5-pro` or `gemini-1.5-flash`) for news parsing and MemoryEngine EOD classifications.
4. **Claude Live API:**
   * Call Anthropic SDK (`claude-3-5-sonnet`) to review premarket watchlists and post-market signals.
5. **NSE Scrapers/Feeders:**
   * Automate parsing of NSE daily reports for FII/DII flows and bulk/block deal sheets post-market.
6. **Yahoo Finance (`yfinance`):**
   * Integrate EOD historical data syncing for constituent stocks as a backup verification source.
