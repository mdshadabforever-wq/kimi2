-- IIIS Database Schema Creation Script
-- Non-Negotiable: PostgreSQL + TimescaleDB

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- TABLE 1: market_data (TimescaleDB)
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    vwap DECIMAL(12,4),
    timeframe VARCHAR(10) NOT NULL
);
SELECT create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_data_lookup ON market_data(time, symbol, timeframe);

-- TABLE 2: signals
CREATE TABLE IF NOT EXISTS signals (
    signal_id VARCHAR(30) PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    score DECIMAL(5,2) NOT NULL CHECK (score > 85.0),
    confidence VARCHAR(10) NOT NULL CHECK (confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    regime VARCHAR(20) NOT NULL,
    entry_low DECIMAL(12,4) NOT NULL,
    entry_high DECIMAL(12,4) NOT NULL,
    stop_loss DECIMAL(12,4) NOT NULL,
    target_1 DECIMAL(12,4) NOT NULL,
    target_2 DECIMAL(12,4) NOT NULL,
    quantity INTEGER NOT NULL,
    risk_amount DECIMAL(12,2) NOT NULL,
    geie_direction VARCHAR(20),
    geie_confidence VARCHAR(10),
    arc_decision VARCHAR(20),
    historical_wr DECIMAL(5,2),
    historical_sample INTEGER,
    risk_grade VARCHAR(5) NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'HIT_SL', 'HIT_T1', 'HIT_T2', 'CANCELLED')),
    valid_until TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 3: active_alerts
CREATE TABLE IF NOT EXISTS active_alerts (
    alert_id SERIAL PRIMARY KEY,
    signal_id VARCHAR(30) REFERENCES signals(signal_id),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    sector VARCHAR(50) NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

-- TABLE 4: risk_state
CREATE TABLE IF NOT EXISTS risk_state (
    session_date DATE UNIQUE NOT NULL,
    daily_risk_used DECIMAL(5,2) DEFAULT 0,
    consecutive_losses INTEGER DEFAULT 0,
    hard_stop_active BOOLEAN DEFAULT FALSE,
    total_signals INTEGER DEFAULT 0,
    signals_hit_sl INTEGER DEFAULT 0,
    signals_hit_t1 INTEGER DEFAULT 0,
    signals_hit_t2 INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 5: regime_history
CREATE TABLE IF NOT EXISTS regime_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    regime VARCHAR(20) NOT NULL,
    regime_score DECIMAL(5,2) NOT NULL,
    adx DECIMAL(8,4),
    nifty_price DECIMAL(12,4),
    ad_ratio DECIMAL(5,2),
    notes TEXT
);

-- TABLE 6: audit_log (Append-only)
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    component VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    result VARCHAR(50) NOT NULL,
    reason TEXT,
    metadata JSONB
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- Prevent UPDATE and DELETE on audit_log at database level
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Updates and deletes are strictly prohibited on the audit_log table. This is a non-negotiable security policy.';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_prevent_audit_log_update
BEFORE UPDATE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();

CREATE OR REPLACE TRIGGER trg_prevent_audit_log_delete
BEFORE DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();

-- TABLE 7: system_health
CREATE TABLE IF NOT EXISTS system_health (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL,
    component VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    response_time_ms INTEGER,
    ghost_mode_active BOOLEAN DEFAULT FALSE,
    last_error TEXT
);

-- TABLE 8: geie_events
CREATE TABLE IF NOT EXISTS geie_events (
    event_id VARCHAR(50) PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    event_name VARCHAR(100),
    impact_direction VARCHAR(20),
    confidence VARCHAR(10),
    urgency VARCHAR(20),
    beneficiaries JSONB,
    losers JSONB,
    neutral JSONB,
    raw_output JSONB
);

-- TABLE 9: geie_master_map
CREATE TABLE IF NOT EXISTS geie_master_map (
    symbol VARCHAR(20) PRIMARY KEY,
    positive_triggers TEXT[],
    negative_triggers TEXT[],
    neutral_triggers TEXT[],
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 10: options_data
CREATE TABLE IF NOT EXISTS options_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    strike DECIMAL(12,4) NOT NULL,
    expiry DATE NOT NULL,
    option_type VARCHAR(5) NOT NULL CHECK (option_type IN ('CE', 'PE')),
    oi BIGINT,
    oi_change BIGINT,
    volume BIGINT,
    iv DECIMAL(8,4),
    ltp DECIMAL(12,4),
    PRIMARY KEY (time, symbol, strike, expiry, option_type)
);

-- TABLE 11: earnings_calendar
CREATE TABLE IF NOT EXISTS earnings_calendar (
    symbol VARCHAR(20) NOT NULL,
    earnings_date DATE NOT NULL,
    earnings_time TIME,
    PRIMARY KEY (symbol, earnings_date)
);

-- TABLE 12: event_calendar
CREATE TABLE IF NOT EXISTS event_calendar (
    event_name VARCHAR(100) NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME,
    impact_level VARCHAR(20) NOT NULL,
    description TEXT,
    PRIMARY KEY (event_name, event_date)
);

-- TABLE 13: fii_dii_tracker
CREATE TABLE IF NOT EXISTS fii_dii_tracker (
    date DATE PRIMARY KEY,
    fii_action VARCHAR(10) NOT NULL CHECK (fii_action IN ('BUYER', 'SELLER')),
    fii_amount_crores DECIMAL(12,2),
    dii_action VARCHAR(10) NOT NULL CHECK (dii_action IN ('BUYER', 'SELLER')),
    dii_amount_crores DECIMAL(12,2),
    combined_bias VARCHAR(20) NOT NULL CHECK (combined_bias IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    consecutive_fii_buy_days INTEGER DEFAULT 0,
    consecutive_fii_sell_days INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 14: bulk_deal_tracker
CREATE TABLE IF NOT EXISTS bulk_deal_tracker (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    deal_type VARCHAR(10) NOT NULL CHECK (deal_type IN ('BUY', 'SELL')),
    quantity BIGINT,
    price DECIMAL(12,4),
    value_crores DECIMAL(12,2),
    client_name VARCHAR(200),
    deal_category VARCHAR(10) NOT NULL CHECK (deal_category IN ('BULK', 'BLOCK')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bulk_symbol ON bulk_deal_tracker(symbol);
CREATE INDEX IF NOT EXISTS idx_bulk_timestamp ON bulk_deal_tracker(timestamp);

-- TABLE 15: options_intelligence
CREATE TABLE IF NOT EXISTS options_intelligence (
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    max_pain_level DECIMAL(12,4),
    highest_put_oi_strike DECIMAL(12,4),
    highest_call_oi_strike DECIMAL(12,4),
    unusual_activity_detected BOOLEAN DEFAULT FALSE,
    unusual_strike DECIMAL(12,4),
    unusual_type VARCHAR(10) CHECK (unusual_type IN ('CALL', 'PUT')),
    unusual_oi_change BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date, symbol)
);

-- TABLE 16: order_block_memory
CREATE TABLE IF NOT EXISTS order_block_memory (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('5m', '15m', 'Daily')),
    ob_type VARCHAR(10) NOT NULL CHECK (ob_type IN ('BULLISH', 'BEARISH')),
    ob_high DECIMAL(12,4) NOT NULL,
    ob_low DECIMAL(12,4) NOT NULL,
    ob_midpoint DECIMAL(12,4) NOT NULL,
    first_detected TIMESTAMPTZ NOT NULL,
    last_tested TIMESTAMPTZ,
    test_count INTEGER DEFAULT 0,
    held_count INTEGER DEFAULT 0,
    broken BOOLEAN DEFAULT FALSE,
    broken_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ob_symbol ON order_block_memory(symbol);
CREATE INDEX IF NOT EXISTS idx_ob_broken ON order_block_memory(broken) WHERE broken = FALSE;

-- NEW TABLE 17: raw_ticks (TimescaleDB)
CREATE TABLE IF NOT EXISTS raw_ticks (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(12,4) NOT NULL,
    volume BIGINT NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('raw_ticks', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_raw_ticks_lookup ON raw_ticks(symbol, time DESC);

-- NEW TABLE 18: latency_metrics
CREATE TABLE IF NOT EXISTS latency_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    receive_latency_ms INTEGER NOT NULL,
    processing_latency_ms INTEGER NOT NULL,
    candle_build_latency_ms INTEGER NOT NULL,
    stage VARCHAR(20) NOT NULL
);

-- NEW TABLE 19: trend_states (TimescaleDB)
CREATE TABLE IF NOT EXISTS trend_states (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    trend VARCHAR(10) NOT NULL CHECK (trend IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    ema_20 DECIMAL(12,4),
    close DECIMAL(12,4)
);
SELECT create_hypertable('trend_states', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS idx_trend_states_lookup ON trend_states(time, symbol, timeframe);

-- NEW TABLE 20: smc_structures (TimescaleDB)
CREATE TABLE IF NOT EXISTS smc_structures (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    structure_type VARCHAR(10) NOT NULL CHECK (structure_type IN ('BOS', 'CHOCH', 'FVG')),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('BULLISH', 'BEARISH')),
    top_price DECIMAL(12,4) NOT NULL,
    bottom_price DECIMAL(12,4) NOT NULL,
    mitigated BOOLEAN DEFAULT FALSE,
    mitigated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('smc_structures', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS idx_smc_structures_lookup ON smc_structures (time, symbol, timeframe, structure_type, direction);
CREATE INDEX IF NOT EXISTS idx_smc_structures_unmitigated ON smc_structures (symbol, timeframe, structure_type, mitigated);

-- NEW TABLE 21: score_audits (TimescaleDB)
CREATE TABLE IF NOT EXISTS score_audits (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    regime_score DECIMAL(5,2) NOT NULL,
    rs_score DECIMAL(5,2) NOT NULL,
    rvol_score DECIMAL(5,2) NOT NULL,
    breadth_score DECIMAL(5,2) NOT NULL,
    sector_score DECIMAL(5,2) NOT NULL,
    trend_score DECIMAL(5,2) NOT NULL,
    smc_score DECIMAL(5,2) NOT NULL,
    options_score DECIMAL(5,2) NOT NULL,
    final_composite_score DECIMAL(5,2) NOT NULL,
    PRIMARY KEY (time, symbol)
);
SELECT create_hypertable('score_audits', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_score_audits_lookup ON score_audits(symbol, time DESC);


-- ==========================================
-- TRADE INTELLIGENCE MODULE TABLES
-- ==========================================

-- TABLE 22: paper_trades
CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id SERIAL PRIMARY KEY,
    signal_id VARCHAR(30) UNIQUE NOT NULL,
    strategy_version VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACTIVE', 'HIT_SL', 'HIT_T1', 'HIT_T2', 'EXPIRED')),
    outcome_classification VARCHAR(20) CHECK (outcome_classification IN ('WIN', 'LOSS', 'BREAKEVEN', 'PARTIAL_WIN', 'TIME_EXIT')),
    entry_low DECIMAL(12,4) NOT NULL,
    entry_high DECIMAL(12,4) NOT NULL,
    stop_loss DECIMAL(12,4) NOT NULL,
    target_1 DECIMAL(12,4) NOT NULL,
    target_2 DECIMAL(12,4) NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    entry_price DECIMAL(12,4),
    entry_time TIMESTAMPTZ,
    entry_volume BIGINT,
    exit_price DECIMAL(12,4),
    exit_time TIMESTAMPTZ,
    holding_minutes INTEGER,
    final_r_multiple DECIMAL(5,2),
    mfe DECIMAL(12,4),
    mae DECIMAL(12,4),
    max_profit_pct DECIMAL(5,2) DEFAULT 0.0,
    max_drawdown_pct DECIMAL(5,2) DEFAULT 0.0,
    founder_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 23: trade_events
CREATE TABLE IF NOT EXISTS trade_events (
    event_id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    metadata JSONB
);

-- TABLE 24: trade_news
CREATE TABLE IF NOT EXISTS trade_news (
    news_id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    headline TEXT NOT NULL,
    sentiment VARCHAR(20),
    impact VARCHAR(20)
);

-- TABLE 25: trade_snapshots
CREATE TABLE IF NOT EXISTS trade_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    snapshot_type VARCHAR(50) NOT NULL CHECK (snapshot_type IN ('Signal Creation', 'Entry', 'Exit')),
    geie JSONB,
    arc JSONB,
    big_money JSONB,
    regime JSONB,
    risk_state JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 26: trade_score_breakdown
CREATE TABLE IF NOT EXISTS trade_score_breakdown (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    regime_score DECIMAL(5,2),
    rs_score DECIMAL(5,2),
    rvol_score DECIMAL(5,2),
    breadth_score DECIMAL(5,2),
    sector_score DECIMAL(5,2),
    trend_score DECIMAL(5,2),
    smc_score DECIMAL(5,2),
    options_score DECIMAL(5,2),
    composite_score DECIMAL(5,2)
);

-- TABLE 27: trade_analysis
CREATE TABLE IF NOT EXISTS trade_analysis (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    markdown_report TEXT NOT NULL,
    json_report JSONB NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 28: trade_story_sections
CREATE TABLE IF NOT EXISTS trade_story_sections (
    section_id SERIAL PRIMARY KEY,
    trade_id INTEGER REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    section_name VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB
);

-- TABLE 29: trade_postmortem
CREATE TABLE IF NOT EXISTS trade_postmortem (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    why_worked TEXT,
    what_supported TEXT,
    risks_existed TEXT,
    lessons_learned TEXT,
    markdown_report TEXT NOT NULL,
    json_report JSONB NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 30: trade_market_context
CREATE TABLE IF NOT EXISTS trade_market_context (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    regime_name VARCHAR(50),
    regime_score DECIMAL(5,2),
    nifty_price DECIMAL(12,2),
    geie_sentiment VARCHAR(50),
    arc_decision VARCHAR(50),
    big_money_trend VARCHAR(50),
    options_bias VARCHAR(50),
    sector_strength_score DECIMAL(5,2),
    relative_strength_score DECIMAL(5,2)
);

-- TABLE 31: trade_candle_statistics
CREATE TABLE IF NOT EXISTS trade_candle_statistics (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    total_candles INTEGER,
    green_candles INTEGER,
    red_candles INTEGER,
    largest_favorable DECIMAL(12,4),
    largest_adverse DECIMAL(12,4),
    average_range DECIMAL(12,4),
    highest_volume BIGINT,
    lowest_volume BIGINT
);

-- TABLE 32: trade_decision_memory
CREATE TABLE IF NOT EXISTS trade_decision_memory (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    composite_score DECIMAL(5,2),
    regime_score DECIMAL(5,2),
    rs_score DECIMAL(5,2),
    rvol_score DECIMAL(5,2),
    breadth_score DECIMAL(5,2),
    sector_score DECIMAL(5,2),
    trend_score DECIMAL(5,2),
    smc_score DECIMAL(5,2),
    options_score DECIMAL(5,2),
    decision_reason TEXT
);

-- TABLE 33: founder_notes
CREATE TABLE IF NOT EXISTS founder_notes (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 34: trade_replays
CREATE TABLE IF NOT EXISTS trade_replays (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    replay_steps JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 35: trade_pattern_library
CREATE TABLE IF NOT EXISTS trade_pattern_library (
    pattern_id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(150) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL, -- 'SECTOR', 'SETUP', 'FOUNDER_BEHAVIOR'
    sample_count INTEGER NOT NULL,
    win_rate DECIMAL(5,2) NOT NULL,
    avg_r_multiple DECIMAL(5,2) NOT NULL,
    description TEXT NOT NULL,
    metadata JSONB,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 36: trade_graveyard
CREATE TABLE IF NOT EXISTS trade_graveyard (
    trade_id INTEGER PRIMARY KEY REFERENCES paper_trades(trade_id) ON DELETE CASCADE,
    why_failed TEXT,
    warning_signs TEXT,
    could_loss_be_avoided BOOLEAN DEFAULT FALSE,
    failure_category VARCHAR(50) NOT NULL, -- 'WEAK_VOLUME', 'NEWS_REVERSAL', 'COUNTER_TREND', etc.
    metadata JSONB,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 37: tomorrow_intelligence
CREATE TABLE IF NOT EXISTS tomorrow_intelligence (
    date DATE PRIMARY KEY,
    watchlist JSONB NOT NULL,
    important_news JSONB,
    risk_areas JSONB,
    confidence_levels JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 38: memory_insights
CREATE TABLE IF NOT EXISTS memory_insights (
    insight_id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL, -- 'WHAT_WORKS', 'WHAT_FAILS', 'WHAT_REPEATS', 'WHAT_CHANGED', 'ATTENTION'
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TABLE 39: daily_reports
CREATE TABLE IF NOT EXISTS daily_reports (
    report_date DATE PRIMARY KEY,
    summary_text TEXT NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

