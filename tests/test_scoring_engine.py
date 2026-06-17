import datetime
import pytest
import asyncio
from decimal import Decimal
import database
from scoring_engine.market_regime import MarketRegimeScorer
from scoring_engine.relative_strength import RelativeStrengthScorer
from scoring_engine.relative_volume import RelativeVolumeScorer
from scoring_engine.breadth_engine import MarketBreadthScorer
from scoring_engine.sector_strength import SectorStrengthScorer
from scoring_engine.score_calculator import CompositeScoreCalculator
from scoring_engine.score_audit import ScoreAuditor
from scoring_engine.persistence import ScoringPersistence
from scoring_engine.recovery_manager import ScoringRecoveryManager
from scoring_engine.telemetry import ScoringTelemetry
from market_data.instrument_loader import InstrumentLoader

@pytest.fixture(scope="module", autouse=True)
def setup_database_schema():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM score_audits;")
    database.execute_query("DELETE FROM regime_history;")
    database.execute_query("DELETE FROM trend_states;")
    database.execute_query("DELETE FROM market_data;")
    database.execute_query("DELETE FROM latency_metrics;")

def test_market_regime_scoring():
    """1. Test Market Regime scoring."""
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # 1. Clean DB and check fallback
    database.execute_query("DELETE FROM regime_history;")
    assert MarketRegimeScorer.calculate_score("SBIN", t) == Decimal("50.0")
    
    # 2. Insert Bullish trending
    database.execute_query(
        "INSERT INTO regime_history (timestamp, regime, regime_score) VALUES (%s, %s, %s);",
        (t, "BULLISH_TRENDING", 90.0)
    )
    assert MarketRegimeScorer.calculate_score("SBIN", t) == Decimal("100.0")
    
    # 3. Insert Volatile/Bearish
    database.execute_query(
        "INSERT INTO regime_history (timestamp, regime, regime_score) VALUES (%s, %s, %s);",
        (t + datetime.timedelta(minutes=5), "BEARISH_VOLATILE", 10.0)
    )
    assert MarketRegimeScorer.calculate_score("SBIN", t + datetime.timedelta(minutes=5)) == Decimal("0.0")

def test_relative_strength_scoring():
    """2. Test Relative Strength scoring."""
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    symbol = "TCS"
    
    database.execute_query("DELETE FROM market_data WHERE symbol IN (%s, 'NIFTY 50');", (symbol,))
    
    # Insert 2 candles for stock (return = +10%)
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, %s, %s, '15m');", (t - datetime.timedelta(minutes=15), symbol, 100.0))
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, %s, %s, '15m');", (t, symbol, 110.0))
    
    # Insert 2 candles for index (return = +5%)
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, %s, %s, '15m');", (t - datetime.timedelta(minutes=15), "NIFTY 50", 10000.0))
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, %s, %s, '15m');", (t, "NIFTY 50", 10500.0))
    
    # Stock return (10%) > Index return (5%) -> 100.0
    assert RelativeStrengthScorer.calculate_score(symbol, t, "15m") == Decimal("100.0")
    
    # Update stock close to 102.0 (return = +2% < index return 5%) -> 0.0
    database.execute_query("UPDATE market_data SET close = 102.0 WHERE symbol = %s AND time = %s;", (symbol, t))
    assert RelativeStrengthScorer.calculate_score(symbol, t, "15m") == Decimal("0.0")

def test_relative_volume_scoring():
    """3. Test Relative Volume scoring."""
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    symbol = "SBIN"
    
    database.execute_query("DELETE FROM market_data WHERE symbol = %s;", (symbol,))
    
    # Insert 20 candles with volume 1000
    for i in range(19):
        database.execute_query("INSERT INTO market_data (time, symbol, volume, timeframe) VALUES (%s, %s, %s, '15m');", (t - datetime.timedelta(minutes=15 * (i + 1)), symbol, 1000))
        
    # Case A: Latest volume = 1600 (RVOL = 1600 / 1030 = ~1.55 >= 1.5) -> 100
    database.execute_query("INSERT INTO market_data (time, symbol, volume, timeframe) VALUES (%s, %s, %s, '15m');", (t, symbol, 1600))
    assert RelativeVolumeScorer.calculate_score(symbol, t, "15m") == Decimal("100.0")
    
    # Case B: Latest volume = 1100 (1.0 <= RVOL < 1.5) -> 70
    database.execute_query("UPDATE market_data SET volume = 1100 WHERE symbol = %s AND time = %s;", (symbol, t))
    assert RelativeVolumeScorer.calculate_score(symbol, t, "15m") == Decimal("70.0")

def test_market_breadth_scoring():
    """4. Test Market Breadth scoring."""
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    database.execute_query("DELETE FROM trend_states;")
    
    # Insert 3 BULLISH and 1 BEARISH
    database.execute_query("INSERT INTO trend_states (time, symbol, trend, timeframe) VALUES (%s, 'SBIN', 'BULLISH', '15m');", (t, ))
    database.execute_query("INSERT INTO trend_states (time, symbol, trend, timeframe) VALUES (%s, 'TCS', 'BULLISH', '15m');", (t, ))
    database.execute_query("INSERT INTO trend_states (time, symbol, trend, timeframe) VALUES (%s, 'RELIANCE', 'BULLISH', '15m');", (t, ))
    database.execute_query("INSERT INTO trend_states (time, symbol, trend, timeframe) VALUES (%s, 'INFY', 'BEARISH', '15m');", (t, ))
    
    # Breadth = 3 / 4 = 75%
    assert MarketBreadthScorer.calculate_score(t, "15m") == Decimal("75.0")

def test_sector_strength_scoring():
    """5. Test Sector Strength scoring."""
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    symbol = "TCS" # Sector IT (other: INFY)
    
    database.execute_query("DELETE FROM market_data WHERE symbol IN ('TCS', 'INFY', 'NIFTY 50');", ())
    
    # IT sector returns (TCS return = +10%, INFY return = +10% => Avg = 10%)
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, 'TCS', 100, '15m');", (t - datetime.timedelta(minutes=15),))
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, 'TCS', 110, '15m');", (t,))
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, 'INFY', 100, '15m');", (t - datetime.timedelta(minutes=15),))
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, 'INFY', 110, '15m');", (t,))
    
    # NIFTY 50 return (+5%)
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, 'NIFTY 50', 10000, '15m');", (t - datetime.timedelta(minutes=15),))
    database.execute_query("INSERT INTO market_data (time, symbol, close, timeframe) VALUES (%s, 'NIFTY 50', 10500, '15m');", (t,))
    
    assert SectorStrengthScorer.calculate_score(symbol, t, "15m") == Decimal("100.0")

def test_composite_score_calculation():
    """6, 7, 8, 9. Verify composite score components and formula weighting."""
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    symbol = "TCS"
    
    # We pass explicit sub-scores for: trend, smc, options
    # The scoring engine calculates the rest: regime, rs, rvol, breadth, sector
    # Let's seed DB so they return:
    #  regime = 100 (Bullish Trending seeded in test_market_regime_scoring)
    #  rs = 100 (TCS return > Index return seeded in test_sector_strength_scoring)
    #  rvol = 40 (fallback when insufficient candles)
    #  breadth = 75 (seeded in test_market_breadth_scoring)
    #  sector = 100 (IT return > Index return seeded in test_sector_strength_scoring)
    # Let's calculate expected score if we pass: trend = 100, smc = 70, options = 100
    # Expected weighted score under new weights:
    #  Regime (100 * 0.25) + RS (100 * 0.20) + RVOL (40 * 0.15) + Breadth (75 * 0.10) + Sector (100 * 0.10) + SMC (70 * 0.10) + Options (100 * 0.10)
    #  = 25 + 20 + 6 + 7.5 + 10 + 7 + 10 = 85.50
    
    res = CompositeScoreCalculator.calculate_composite_score(
        symbol=symbol,
        as_of_time=t,
        trend_score=Decimal("100.0"),
        smc_score=Decimal("70.0"),
        options_score=Decimal("100.0"),
        timeframe="15m"
    )
    
    assert res["final_composite_score"] == Decimal("85.5")
    assert res["is_accepted"] is False

def test_score_threshold_rules():
    """10, 11, 12. Verify validation thresholds (FAIL <= 85.5, PASS >= 86.0)."""
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    symbol = "SBIN"
    
    from unittest.mock import patch
    with patch("scoring_engine.market_regime.MarketRegimeScorer.calculate_score", return_value=Decimal("100.0")), \
         patch("scoring_engine.relative_strength.RelativeStrengthScorer.calculate_score", return_value=Decimal("100.0")), \
         patch("scoring_engine.relative_volume.RelativeVolumeScorer.calculate_score", return_value=Decimal("100.0")), \
         patch("scoring_engine.breadth_engine.MarketBreadthScorer.calculate_score", return_value=Decimal("100.0")), \
         patch("scoring_engine.sector_strength.SectorStrengthScorer.calculate_score", return_value=Decimal("100.0")):
         
         # 1. Total score = 84.0 (<= 85.5) -> FAIL
         res_82 = CompositeScoreCalculator.calculate_composite_score(symbol, t, 20, 20, 20)
         assert res_82["final_composite_score"] <= Decimal("85.5")
         assert res_82["is_accepted"] is False
         
         # 2. Total score = 94.0 (>= 86.0) -> PASS
         res_86 = CompositeScoreCalculator.calculate_composite_score(symbol, t, 70, 70, 70)
         assert res_86["final_composite_score"] >= Decimal("86.0")
         assert res_86["is_accepted"] is True

def test_audit_reconstruction():
    """13. Test score audit reconstruction."""
    t = datetime.datetime(2026, 6, 15, 15, 0, 0)
    symbol = "AUDIT_SYM"
    
    ScoringPersistence.save_audit(
        time=t,
        symbol=symbol,
        regime=Decimal("100.0"),
        rs=Decimal("100.0"),
        rvol=Decimal("70.0"),
        breadth=Decimal("60.0"),
        sector=Decimal("100.0"),
        trend=Decimal("100.0"),
        smc=Decimal("70.0"),
        options=Decimal("100.0"),
        final_score=Decimal("88.5")
    )
    
    rebuilt = ScoreAuditor.rebuild_score(symbol, t)
    assert rebuilt is not None
    assert rebuilt["reverified"] is True
    assert rebuilt["audit_record"]["final_composite_score"] == Decimal("88.5")
    assert rebuilt["status"] == "PASS"

def test_restart_recovery():
    """14 & 15. Test scoring restart recovery."""
    t = datetime.datetime(2026, 6, 15, 16, 0, 0)
    symbol = "RECOVER_SYM"
    
    ScoringPersistence.save_audit(
        time=t,
        symbol=symbol,
        regime=Decimal("100.0"),
        rs=Decimal("100.0"),
        rvol=Decimal("100.0"),
        breadth=Decimal("100.0"),
        sector=Decimal("100.0"),
        trend=Decimal("100.0"),
        smc=Decimal("100.0"),
        options=Decimal("100.0"),
        final_score=Decimal("100.0")
    )
    
    recovered = ScoringRecoveryManager.recover_latest_score(symbol)
    assert recovered["status"] == "RECOVERED"
    assert recovered["final_composite_score"] == Decimal("100.0")

def test_multi_symbol_processing():
    """15. Test symbol isolation in scoring."""
    t = datetime.datetime(2026, 6, 15, 16, 0, 0)
    # Verify we can calculate scores for separate symbols without overlap
    res1 = CompositeScoreCalculator.calculate_composite_score("RELIANCE", t, 100, 100, 100)
    res2 = CompositeScoreCalculator.calculate_composite_score("TCS", t, 0, 0, 0)
    
    assert res1["symbol"] == "RELIANCE"
    assert res2["symbol"] == "TCS"
    assert res1["final_composite_score"] > res2["final_composite_score"]

def test_nifty_50_constituents():
    """16. Test instrument master NIFTY 50 loader."""
    loader = InstrumentLoader()
    symbols = loader.symbols
    assert len(symbols) == 50
    assert "RELIANCE" in symbols

@pytest.mark.asyncio
async def test_concurrent_execution_and_telemetry():
    """17 & 18. Test concurrent calculations and latency telemetry."""
    database.execute_query("DELETE FROM latency_metrics;")
    
    symbols = ["RELIANCE", "TCS", "INFY", "SBIN", "ICICIBANK"]
    t = datetime.datetime(2026, 6, 15, 17, 0, 0)
    
    async def run_scoring(s):
        return CompositeScoreCalculator.calculate_composite_score(s, t, 100, 100, 100)
        
    results = await asyncio.gather(*(run_scoring(s) for s in symbols))
    
    assert len(results) == len(symbols)
    # Check database telemetry logs
    metrics_count = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'COMPOSITE_SCORING';", fetch=True)
    assert metrics_count[0][0] == len(symbols)
