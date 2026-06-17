import sys
import os
import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bootstrap import register_services
from orchestrator import Orchestrator
from market_data.instrument_loader import InstrumentLoader
from interfaces.base import ServiceRegistry
from seeder import seed_mock_data_for_demo

def run_diagnostic():
    register_services()
    orchestrator = Orchestrator()
    loader = InstrumentLoader()
    
    symbol = "TATASTEEL"
    timestamp = datetime.datetime.now()
    
    print(f"--- DIAGNOSTIC FOR {symbol} AT {timestamp} ---")
    
    # Seed
    seed_mock_data_for_demo(loader.symbols)
    
    # Warm up
    orchestrator.warmup_engines(loader.symbols)
    
    # Simulate live tick processing
    upstox = ServiceRegistry.get("upstox")
    upstox.connect_websocket()
    tick = upstox.get_live_data(symbol)
    tick["time"] = timestamp
    
    print(f"Processing tick: {tick}")
    orchestrator.process_tick(tick)
    
    # Check 1: trend_engine trends
    trends = orchestrator.trend_engine.latest_trends.get(symbol)
    print(f"1. TrendEngine latest trends after tick: {trends}")
    if not trends:
        print("-> FAILED: No trends found")
        return
        
    # Check 2: alignment
    from market_analysis.alignment_engine import AlignmentEngine
    is_aligned, trend_direction, trend_score = AlignmentEngine.calculate_alignment(trends)
    print(f"2. Alignment: is_aligned={is_aligned}, trend_direction={trend_direction}, trend_score={trend_score}")
    if not is_aligned or trend_direction == "NEUTRAL":
        print("-> FAILED: Trend not aligned or NEUTRAL")
        return
        
    # Check 3: SMC Setup
    mapped_trend_dir = "LONG" if trend_direction == "BULLISH" else "SHORT" if trend_direction == "BEARISH" else "NO_DIRECTION"
    smc_setup = orchestrator.smc_engine.generate_setup(symbol)
    print(f"3. SMC Setup: direction={smc_setup.get('direction')}, mapped_trend_dir={mapped_trend_dir}")
    if smc_setup["direction"] == "NO_DIRECTION" or smc_setup["direction"] != mapped_trend_dir:
        print("-> FAILED: SMC Setup direction doesn't match or is NO_DIRECTION")
        return
        
    # Check 4: Options buildup
    expiry_date = timestamp.date() + datetime.timedelta(days=7)
    options_result = orchestrator.options_engine.process_option_update(symbol, expiry_date, timestamp)
    print(f"4. Options result: bias={options_result.get('bias')}")
    
    # Check 5: Composite scoring
    from decimal import Decimal
    from scoring_engine.score_calculator import CompositeScoreCalculator
    mapped_options_bias = "LONG" if options_result["bias"] == "BULLISH" else "SHORT" if options_result["bias"] == "BEARISH" else "NEUTRAL"
    options_score = Decimal("100.0") if mapped_options_bias == smc_setup["direction"] else Decimal("50.0") if mapped_options_bias == "NEUTRAL" else Decimal("0.0")
    score_res = CompositeScoreCalculator.calculate_composite_score(
        symbol=symbol,
        as_of_time=timestamp,
        trend_score=Decimal(str(trend_score)),
        smc_score=Decimal(str(smc_setup["score"])),
        options_score=options_score,
        timeframe="15m"
    )
    print(f"5. Composite Score result: is_accepted={score_res.get('is_accepted')}, score={score_res.get('final_composite_score')}")
    print(f"   Sub-scores: regime={score_res.get('regime_score')}, rs={score_res.get('rs_score')}, rvol={score_res.get('rvol_score')}, breadth={score_res.get('breadth_score')}, sector={score_res.get('sector_score')}, trend={score_res.get('trend_score')}, smc={score_res.get('smc_score')}, options={score_res.get('options_score')}")
    if not score_res["is_accepted"]:
        print("-> FAILED: Composite score not accepted")
        return
        
    # Check 6: ARC decision
    arc_dec = orchestrator.watchlist_decisions.get(symbol, "APPROVE")
    print(f"6. ARC Premarket Decision: {arc_dec}")
    if arc_dec == "REJECT":
        print("-> FAILED: ARC Decision is REJECT")
        return
        
    # Check 7: Risk Gates
    print("-> ALL CHECKS PASSED up to Risk Gates!")

if __name__ == "__main__":
    run_diagnostic()
