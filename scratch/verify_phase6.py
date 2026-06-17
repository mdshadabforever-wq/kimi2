import datetime
import asyncio
import time
from decimal import Decimal
import database
from scoring_engine.score_calculator import CompositeScoreCalculator
from scoring_engine.score_audit import ScoreAuditor
from scoring_engine.persistence import ScoringPersistence
from scoring_engine.recovery_manager import ScoringRecoveryManager
from market_data.instrument_loader import InstrumentLoader
from unittest.mock import patch

def setup_clean_db():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM score_audits;")
    database.execute_query("DELETE FROM regime_history;")
    database.execute_query("DELETE FROM trend_states;")
    database.execute_query("DELETE FROM market_data;")
    database.execute_query("DELETE FROM latency_metrics;")

def run_scoring_verification():
    print("=== Phase 6 Composite Scoring Engine Verification ===")
    setup_clean_db()
    
    symbol = "TATASTEEL"
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # 1. Seed other scorers mock values
    # regime=100, rs=100, rvol=100, breadth=80, sector=100
    with patch("scoring_engine.market_regime.MarketRegimeScorer.calculate_score", return_value=Decimal("100.0")), \
         patch("scoring_engine.relative_strength.RelativeStrengthScorer.calculate_score", return_value=Decimal("100.0")), \
         patch("scoring_engine.relative_volume.RelativeVolumeScorer.calculate_score", return_value=Decimal("100.0")), \
         patch("scoring_engine.breadth_engine.MarketBreadthScorer.calculate_score", return_value=Decimal("80.0")), \
         patch("scoring_engine.sector_strength.SectorStrengthScorer.calculate_score", return_value=Decimal("100.0")):
         
         # 2. Composite Score Breakdown Example (Targeting Score = 91.0)
         # Components:
         #  regime = 100 * 0.15 = 15.0
         #  rs = 100 * 0.10 = 10.0
         #  rvol = 100 * 0.10 = 10.0
         #  breadth = 80 * 0.10 = 8.0
         #  sector = 100 * 0.10 = 10.0
         #  Sum (regime+rs+rvol+breadth+sector) = 53.0
         #  Need 38.0 from trend + smc + options
         #  Let trend = 100 (15.0), smc = 70 (10.5), options = 100 (15.0) => 40.5 => Total = 93.5
         #  Let trend = 100 (15.0), smc = 70 (10.5), options = 50 (7.5) => 33.0 => Total = 86.0
         #  Let trend = 100 (15.0), smc = 100 (15.0), options = 50 (7.5) => 37.5 => Total = 90.5
         #  To get exactly 91.0:
         #  Let trend = 100 (15.0), smc = 70 (10.5), options = 83.33 (12.5) => 38.0 => Total = 91.0
         trend_val = Decimal("100.0")
         smc_val = Decimal("70.0")
         options_val = Decimal("83.33")
         
         res = CompositeScoreCalculator.calculate_composite_score(symbol, t, trend_val, smc_val, options_val)
         
         print("\nA. Composite Score Breakdown Example")
         print("------------------------------------")
         print(f"Symbol: {res['symbol']}")
         print(f"Timestamp: {res['time']}")
         print(f"Market Regime     = {res['regime_score']}")
         print(f"RS                = {res['rs_score']}")
         print(f"RVOL              = {res['rvol_score']}")
         print(f"Breadth           = {res['breadth_score']}")
         print(f"Sector            = {res['sector_score']}")
         print(f"Trend Alignment   = {res['trend_score']}")
         print(f"SMC Quality       = {res['smc_score']}")
         print(f"Options           = {res['options_score']}")
         print(f"Final Composite Score = {res['final_composite_score']} (Accepted: {res['is_accepted']})")

         print("\nB. Threshold Verification")
         print("------------------------")
         
         # 1. Score 84.50 -> FAIL (trend=100, smc=40, options=70 => sum = 53 + 15 + 6 + 10.5 = 84.50)
         r_845 = CompositeScoreCalculator.calculate_composite_score(symbol, t, 100, 40, 70)
         print(f"Score {r_845['final_composite_score']} -> {'PASS' if r_845['is_accepted'] else 'FAIL'}")
         
         # 2. Score 85.00 -> FAIL (trend=100, smc=70, options=43.33 => sum = 53 + 15 + 10.5 + 6.5 = 85.00)
         r_85 = CompositeScoreCalculator.calculate_composite_score(symbol, t, 100, 70, Decimal("43.33"))
         print(f"Score {r_85['final_composite_score']} -> {'PASS' if r_85['is_accepted'] else 'FAIL'}")
         
         # 3. Score 85.50 -> FAIL (trend=100, smc=70, options=46.66 => sum = 53 + 15 + 10.5 + 7.0 = 85.50)
         r_855 = CompositeScoreCalculator.calculate_composite_score(symbol, t, 100, 70, Decimal("46.66"))
         print(f"Score {r_855['final_composite_score']} -> {'PASS' if r_855['is_accepted'] else 'FAIL'}")
         
         # 4. Score 86.00 -> PASS (trend=100, smc=70, options=50 => sum = 53 + 15 + 10.5 + 7.5 = 86.00)
         r_86 = CompositeScoreCalculator.calculate_composite_score(symbol, t, 100, 70, 50)
         print(f"Score {r_86['final_composite_score']} -> {'PASS' if r_86['is_accepted'] else 'FAIL'}")

         print("\nC. Audit Reconstruction Example")
         print("------------------------------")
         # Rebuild score historically
         rebuilt = ScoreAuditor.rebuild_score(symbol, t)
         print(f"Input:")
         print(f"  symbol = {symbol}")
         print(f"  timestamp = {t}")
         print(f"Output:")
         print(f"  All component scores: ")
         rec = rebuilt["audit_record"]
         print(f"    Regime={rec['regime_score']}, RS={rec['rs_score']}, RVOL={rec['rvol_score']}, Breadth={rec['breadth_score']}, Sector={rec['sector_score']}")
         print(f"    Trend={rec['trend_score']}, SMC={rec['smc_score']}, Options={rec['options_score']}")
         print(f"  Final score = {rec['final_composite_score']}")
         print(f"  Verification result = {rebuilt['status']}")

         print("\n--- Restart Recovery Evidence ---")
         recovered = ScoringRecoveryManager.recover_latest_score(symbol)
         print(f"Recovery Status: {recovered['status']}")
         print(f"Recovered Score: {recovered['final_composite_score']} (Time: {recovered['time']})")

async def run_perf_verification():
    print("\nD. Multi-Symbol Verification & Concurrency")
    print("------------------------------------------")
    loader = InstrumentLoader()
    symbols = loader.symbols
    t = datetime.datetime.now()

    # Process all 50 symbols concurrently
    async def process_stock(s):
        return CompositeScoreCalculator.calculate_composite_score(s, t, 100, 100, 100)

    start_time = time.perf_counter()
    results = await asyncio.gather(*(process_stock(s) for s in symbols))
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    avg_latency = elapsed_ms / len(symbols)

    print(f"Processed all {len(symbols)} NIFTY symbols concurrently.")
    print(f"Total Concurrent Execution Time: {elapsed_ms:.2f}ms")
    print(f"Average Processing Latency: {avg_latency:.2f}ms per stock")
    
    print("\nE. Telemetry Output")
    print("-------------------")
    res = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'COMPOSITE_SCORING';", fetch=True)
    print(f"Telemetry metrics recorded in DB: {res[0][0]} rows")

if __name__ == "__main__":
    run_scoring_verification()
    asyncio.run(run_perf_verification())
