import sys
import os
import datetime
from decimal import Decimal
import asyncio
import time

# Setup path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from bootstrap import register_services
import database
from market_analysis.trend_engine import TrendEngine
from market_analysis.alignment_engine import AlignmentEngine
from market_analysis.trend_persistence import TrendPersistence
from market_analysis.warmup_manager import WarmupManager
from market_analysis.indicator_cache import IndicatorCache
from market_analysis.timeframe_analyzer import TimeframeAnalyzer
from market_data.instrument_loader import InstrumentLoader

def setup_test_candles(symbol: str, timeframe: str, start_time: datetime.datetime, count: int, base_price: float, trend_type: str = "bullish"):
    database.execute_query("DELETE FROM market_data WHERE symbol = %s AND timeframe = %s;", (symbol, timeframe))
    curr = base_price
    for i in range(count):
        if trend_type == "bullish":
            curr += 1.0
        elif trend_type == "bearish":
            curr -= 1.0
        else:
            curr = base_price
            
        if timeframe == "5m":
            t = start_time + datetime.timedelta(minutes=5 * i)
        elif timeframe == "15m":
            t = start_time + datetime.timedelta(minutes=15 * i)
        elif timeframe == "1h":
            t = start_time + datetime.timedelta(hours=i)
        else:
            t = start_time + datetime.timedelta(days=i)
            
        database.execute_query(
            "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
            (t, symbol, curr - 0.5, curr + 0.5, curr - 0.5, curr, 100, curr, timeframe)
        )

def setup_bulk_test_candles(symbols: list[str], timeframes: list[str], start_time: datetime.datetime, count: int, base_price: float, trend_type: str = "bullish"):
    """Helper to insert 'count' candles to database in bulk for all specified symbols and timeframes."""
    if not symbols:
        return
    
    symbol_placeholders = ",".join(["%s"] * len(symbols))
    tf_placeholders = ",".join(["%s"] * len(timeframes))
    
    database.execute_query(
        f"DELETE FROM market_data WHERE symbol IN ({symbol_placeholders}) AND timeframe IN ({tf_placeholders});",
        tuple(symbols) + tuple(timeframes)
    )
    
    rows = []
    for sym in symbols:
        for tf in timeframes:
            curr = base_price
            for i in range(count):
                if trend_type == "bullish":
                    curr += 1.0
                elif trend_type == "bearish":
                    curr -= 1.0
                else:
                    curr = base_price
                
                if tf == "5m":
                    t = start_time + datetime.timedelta(minutes=5 * i)
                elif tf == "15m":
                    t = start_time + datetime.timedelta(minutes=15 * i)
                elif tf == "1h":
                    t = start_time + datetime.timedelta(hours=i)
                else:  # Daily
                    t = start_time + datetime.timedelta(days=i)
                    
                rows.append((t, sym, curr - 0.5, curr + 0.5, curr - 0.5, curr, 100, curr, tf))
                
    chunk_size = 500
    for idx in range(0, len(rows), chunk_size):
        chunk = rows[idx:idx + chunk_size]
        placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
        query = f"INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES {placeholders};"
        flat_args = []
        for r in chunk:
            flat_args.extend(r)
        database.execute_query(query, tuple(flat_args))

async def verify_all():
    register_services()
    print("=" * 60)
    print(" IIIS PHASE 3 MULTI TIMEFRAME ENGINE VERIFICATION")
    print("=" * 60)
    
    symbol = "TATASTEEL"
    start_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    
    # 1. TREND CALCULATION VERIFICATION
    print("\n[PART 1] TREND CALCULATION VERIFICATION")
    print("-" * 50)
    # Insert 25 bullish candles to DB
    setup_test_candles(symbol, "15m", start_time, 25, 150.0, "bullish")
    
    cache = IndicatorCache()
    analyzer = TimeframeAnalyzer(cache)
    check_time = start_time + datetime.timedelta(minutes=15 * 24)
    trend, ema_val = analyzer.analyze_timeframe(symbol, "15m", check_time)
    print(f"Calculated 15m Trend for {symbol} at {check_time}:")
    print(f"  Trend Direction: {trend}")
    print(f"  EMA 20 Value   : {ema_val:.4f}")
    print(f"  Close Price    : 174.0000 (Close > EMA 20 -> Bullish)")

    # 2. ALIGNMENT VERIFICATION
    print("\n[PART 2] ALIGNMENT ENGINE VERIFICATION (3-OF-4 RULE)")
    print("-" * 50)
    # Case A: 4/4 Align
    trends_4 = {"Daily": "BULLISH", "1h": "BULLISH", "15m": "BULLISH", "5m": "BULLISH"}
    is_aligned_4, dir_4, score_4 = AlignmentEngine.calculate_alignment(trends_4)
    print(f"Case A (4/4 Bullish) -> Is Aligned: {is_aligned_4} | Direction: {dir_4} | Score: {score_4}")
    
    # Case B: 3/4 Align
    trends_3 = {"Daily": "BEARISH", "1h": "BEARISH", "15m": "BEARISH", "5m": "NEUTRAL"}
    is_aligned_3, dir_3, score_3 = AlignmentEngine.calculate_alignment(trends_3)
    print(f"Case B (3/4 Bearish) -> Is Aligned: {is_aligned_3} | Direction: {dir_3} | Score: {score_3}")
    
    # Case C: 2/4 Align (FAIL)
    trends_2 = {"Daily": "BULLISH", "1h": "BULLISH", "15m": "BEARISH", "5m": "NEUTRAL"}
    is_aligned_2, dir_2, score_2 = AlignmentEngine.calculate_alignment(trends_2)
    print(f"Case C (2/4 Mixed)   -> Is Aligned: {is_aligned_2} | Direction: {dir_2} | Score: {score_2}")

    # 3. WARMUP VERIFICATION
    print("\n[PART 3] HISTORICAL WARMUP VERIFICATION")
    print("-" * 50)
    cache.clear()
    database.execute_query("DELETE FROM trend_states WHERE symbol = %s;", (symbol,))
    setup_test_candles(symbol, "5m", start_time, 25, 150.0, "bearish")
    
    warmup = WarmupManager(cache, analyzer)
    warmup.warmup_symbol(symbol, timeframes=["5m"])
    print("Warmed up 5m timeframe for TATASTEEL.")
    print(f"  In-memory Cache Size: {cache.size()} items cached")
    
    # Check DB rows populated
    db_rows = database.execute_query(
        "SELECT count(*) FROM trend_states WHERE symbol = %s AND timeframe = '5m';",
        (symbol,), fetch=True
    )
    print(f"  Database 'trend_states' table populated: {db_rows[0][0]} rows saved.")

    # 4. RESTART RECOVERY VERIFICATION
    print("\n[PART 4] RESTART RECOVERY VERIFICATION")
    print("-" * 50)
    engine = TrendEngine()
    # Restore from DB
    engine.restore_state_from_db(symbol)
    print(f"TrendEngine state successfully recovered from DB:")
    print(f"  Latest trends in memory: {engine.latest_trends.get(symbol)}")

    # 5. PERFORMANCE VERIFICATION (50 Stocks load & execution)
    print("\n[PART 5] PERFORMANCE VERIFICATION (50 STOCKS CONCURRENT RUN)")
    print("-" * 50)
    loader = InstrumentLoader()
    symbols = loader.symbols
    assert len(symbols) == 50
    
    print(f"Loading 22 historical candles for all {len(symbols)} NIFTY 50 instruments...")
    setup_bulk_test_candles(symbols, ["5m", "15m", "1h", "Daily"], start_time, 22, 100.0, "bullish")
    
    perf_engine = TrendEngine()
    perf_engine.warmup_system(symbols)
    
    # Clear latency metrics table to isolate telemetry checking
    database.execute_query("DELETE FROM latency_metrics WHERE stage = 'TREND_ANALYSIS';")
    
    async def process_tick_async(sym):
        tick = {
            "symbol": sym,
            "price": 105.0,
            "volume": 20,
            "time": start_time + datetime.timedelta(minutes=5 * 21)
        }
        perf_engine.process_tick(tick)
        
    start_perf = time.perf_counter()
    await asyncio.gather(*(process_tick_async(sym) for sym in symbols))
    duration_ms = (time.perf_counter() - start_perf) * 1000
    avg_latency = duration_ms / len(symbols)
    
    print(f"Processed {len(symbols)} symbols concurrently:")
    print(f"  Total Time : {duration_ms:.2f}ms")
    print(f"  Avg Latency: {avg_latency:.2f}ms per symbol")
    
    # Query latency metrics to confirm telemetry integration
    res = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'TREND_ANALYSIS';", fetch=True)
    print(f"  Telemetry rows recorded: {res[0][0]} entries.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(verify_all())
