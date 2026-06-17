# IIIS — Intelligent Institutional Investing System (v4.6)

IIIS (v4.6) is an agent-centric, institutional-grade passive trading intelligence observer dashboard and signal analysis engine. It runs live scan pipelines, calculates composite scores based on multi-timeframe trends, smart money concepts (SMC), and option flow indicators, and validates entries through sequential risk assessment gates.

## Current Project Status
* **Core Trading Signal Engine:** 100% complete and fully verified.
* **Production API Adapters (New in v4.6):** Fully coded and integrated under the `/production` folder. Ready to connect to live services upon credential configuration.
* **Founder OS Passive Observer Interface:** Completed. Includes live operating center (Today), Day Replay, Trade Stories, Notion-style memory intelligence archives, PDF report generator, AI Analyst diagnostic agent, and operations dashboard.
* **Testing Coverage:** 136 tests fully passing (zero regressions).
* **API Ingestion & Veto Wiring**: Dynamic 300-day historical Win Rate calculation and dynamic pre-market watchlist reviews are fully wired.

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
* `/production` — Production-ready API adapters (Upstox, Perplexity, Gemini, Claude, NSE, Yahoo Finance) that activate via env configurations.
* `/mocks` — Stateful mock interfaces simulating Upstox WebSocket, Perplexity news queries, Gemini sentiment feeds, and Claude watchlists.

---

## Integrations & Mode Selection

The system supports two execution environments configured in the `.env` file via `IIIS_TESTING`:

1. **Test/Mock Mode (`IIIS_TESTING=True` or `MOCK_MODE=True`)**:
   - Uses stateful mock adapters in `/mocks` to simulate price feeds, WebSocket ticks, option chains, news queries, and sentiment feeds without incurring API costs.
2. **Production Mode (`IIIS_TESTING=False`)**:
   - Activates production adapters under `/production` to establish real connections:
     - **Upstox**: Protobuf WebSocket market feed (`wss://api-v2.upstox.com/feed/market-data-feed`), Option Chain API, and Historical Candle warmups.
     - **Perplexity**: Live completions (`https://api.perplexity.ai/chat/completions`) using the `sonar` model with Google search grounding.
     - **Gemini**: Live completions (`gemini-2.5-flash` or `gemini-1.5-pro`) for GEIE impact mapping and MemoryEngine postmortems.
     - **Claude**: Live tool-based structured completions (`claude-sonnet-4-6` or `claude-3-5-sonnet-latest`) for watchlist audits and Live Signal veto gates.
     - **NSE & YFinance**: Live post-market Bhavcopy scraping, bulk/block deals, and backup data reconciliation.

