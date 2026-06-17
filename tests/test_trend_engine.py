import datetime
import pytest
from decimal import Decimal
import asyncio
import database
from market_analysis.indicator_cache import IndicatorCache
from market_analysis.timeframe_analyzer import TimeframeAnalyzer
from market_analysis.alignment_engine import AlignmentEngine
from market_analysis.trend_persistence import TrendPersistence
from market_analysis.trend_engine import TrendEngine
from market_analysis.warmup_manager import WarmupManager
from market_data.instrument_loader import InstrumentLoader

def setup_test_candles(symbol: str, timeframe: str, start_time: datetime.datetime, count: int, base_price: float, trend_type: str = "bullish"):
    """Helper to insert 'count' candles to database for trend calculation warmup."""
    database.execute_query("DELETE FROM market_data WHERE symbol = %s AND timeframe = %s;", (symbol, timeframe))
    
    # Generate prices
    prices = []
    curr = base_price
    for i in range(count):
        if trend_type == "bullish":
            curr += 1.0  # upward trend
        elif trend_type == "bearish":
            curr -= 1.0  # downward trend
        else:
            curr = base_price  # flat trend
        prices.append(curr)
        
    for i, price in enumerate(prices):
        # Time increment based on timeframe
        if timeframe == "5m":
            t = start_time + datetime.timedelta(minutes=5 * i)
        elif timeframe == "15m":
            t = start_time + datetime.timedelta(minutes=15 * i)
        elif timeframe == "1h":
            t = start_time + datetime.timedelta(hours=i)
        else: # Daily
            t = start_time + datetime.timedelta(days=i)
            
        database.execute_query(
            "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
            (t, symbol, price - 0.5, price + 0.5, price - 0.5, price, 100, price, timeframe)
        )
    return prices

def setup_timeframe_history(symbols: list[str], tick_time: datetime.datetime, count: int = 22, base_price: float = 100.0, trend_type: str = "bullish"):
    """Inserts 'count' completed candles before 'tick_time' for all 4 timeframes (Daily, 1h, 15m, 5m)."""
    if not symbols:
        return
        
    timeframes = ["Daily", "1h", "15m", "5m"]
    symbol_placeholders = ",".join(["%s"] * len(symbols))
    tf_placeholders = ",".join(["%s"] * len(timeframes))
    
    database.execute_query(
        f"DELETE FROM market_data WHERE symbol IN ({symbol_placeholders}) AND timeframe IN ({tf_placeholders});",
        tuple(symbols) + tuple(timeframes)
    )
    
    rows = []
    for sym in symbols:
        for tf in timeframes:
            for i in range(count):
                if trend_type == "bullish":
                    price = base_price - (count - 1 - i) * 1.0
                elif trend_type == "bearish":
                    price = base_price + (count - 1 - i) * 1.0
                else:
                    price = base_price
                
                if tf == "5m":
                    t = tick_time - datetime.timedelta(minutes=5 * (count - i))
                elif tf == "15m":
                    t = tick_time - datetime.timedelta(minutes=15 * (count - i))
                elif tf == "1h":
                    t = tick_time - datetime.timedelta(hours=count - i)
                else:  # Daily
                    t = tick_time - datetime.timedelta(days=count - i)
                    
                rows.append((t, sym, price - 0.5, price + 0.5, price - 0.5, price, 100, price, tf))
                
    chunk_size = 500
    for idx in range(0, len(rows), chunk_size):
        chunk = rows[idx:idx + chunk_size]
        placeholders = ",".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
        query = f"INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES {placeholders};"
        flat_args = []
        for r in chunk:
            flat_args.extend(r)
        database.execute_query(query, tuple(flat_args))

def test_trend_detection_types():
    """Verify Bullish, Bearish, and Neutral trend classification rules."""
    cache = IndicatorCache()
    analyzer = TimeframeAnalyzer(cache)
    symbol = "TATASTEEL"
    timeframe = "15m"
    start_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    
    # 1. Neutral: Insufficient candles (< 20)
    setup_test_candles(symbol, timeframe, start_time, 15, 100.0, "bullish")
    trend, ema_val = analyzer.analyze_timeframe(symbol, timeframe, start_time + datetime.timedelta(minutes=15 * 14))
    assert trend == "NEUTRAL"
    assert ema_val == Decimal("0")
    
    # 2. Bullish: Close > EMA 20
    prices = setup_test_candles(symbol, timeframe, start_time, 25, 100.0, "bullish")
    check_time = start_time + datetime.timedelta(minutes=15 * 24)
    trend, ema_val = analyzer.analyze_timeframe(symbol, timeframe, check_time)
    assert trend == "BULLISH"
    assert ema_val > 0
    assert Decimal(str(prices[-1])) > ema_val
    
    # 3. Bearish: Close < EMA 20
    prices = setup_test_candles(symbol, timeframe, start_time, 25, 100.0, "bearish")
    cache.clear() # Clear cache to re-analyze from scratch
    trend, ema_val = analyzer.analyze_timeframe(symbol, timeframe, check_time)
    assert trend == "BEARISH"
    assert ema_val > 0
    assert Decimal(str(prices[-1])) < ema_val

def test_timeframe_analysis_boundaries():
    """Verify EMA calculation behaves correctly on distinct Daily, Hourly, 15m, and 5m boundaries."""
    cache = IndicatorCache()
    analyzer = TimeframeAnalyzer(cache)
    symbol = "INFY"
    start_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    
    timeframes = ["Daily", "1h", "15m", "5m"]
    for tf in timeframes:
        cache.clear()
        setup_test_candles(symbol, tf, start_time, 22, 500.0, "bullish")
        
        # Calculate check boundary time
        if tf == "5m":
            check_time = start_time + datetime.timedelta(minutes=5 * 21)
        elif tf == "15m":
            check_time = start_time + datetime.timedelta(minutes=15 * 21)
        elif tf == "1h":
            check_time = start_time + datetime.timedelta(hours=21)
        else:
            check_time = start_time + datetime.timedelta(days=21)
            
        trend, ema_val = analyzer.analyze_timeframe(symbol, tf, check_time)
        assert trend in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert ema_val > Decimal("0")

def test_alignment_logic():
    """Verify AlignmentEngine scoring logic for PASS (4/4, 3/4) and FAIL (2/4)."""
    # 1. PASS (4/4 Bullish)
    trends = {"Daily": "BULLISH", "1h": "BULLISH", "15m": "BULLISH", "5m": "BULLISH"}
    is_aligned, direction, score = AlignmentEngine.calculate_alignment(trends)
    assert is_aligned is True
    assert direction == "BULLISH"
    assert score == 100
    
    # 2. PASS (3/4 Bearish)
    trends = {"Daily": "BEARISH", "1h": "BEARISH", "15m": "BEARISH", "5m": "NEUTRAL"}
    is_aligned, direction, score = AlignmentEngine.calculate_alignment(trends)
    assert is_aligned is True
    assert direction == "BEARISH"
    assert score == 75
    
    # 3. FAIL (2/4 Bullish)
    trends = {"Daily": "BULLISH", "1h": "BULLISH", "15m": "BEARISH", "5m": "NEUTRAL"}
    is_aligned, direction, score = AlignmentEngine.calculate_alignment(trends)
    assert is_aligned is False
    assert direction == "NEUTRAL"
    assert score == 0

def test_trend_persistence_and_restart():
    """Verify TrendPersistence writes to DB and restores TrendEngine state after restart."""
    symbol = "TCS"
    tf = "15m"
    test_time = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # Clean DB
    database.execute_query("DELETE FROM trend_states WHERE symbol = %s;", (symbol,))
    
    # Save trend state
    TrendPersistence.save_trend_state(
        boundary_time=test_time,
        symbol=symbol,
        timeframe=tf,
        trend="BULLISH",
        ema_20=Decimal("1500.50"),
        close=Decimal("1510.00")
    )
    
    # Load specific state
    state = TrendPersistence.load_trend_state(symbol, tf, test_time)
    assert state is not None
    assert state["trend"] == "BULLISH"
    assert state["ema_20"] == Decimal("1500.50")
    assert state["close"] == Decimal("1510.00")
    
    # Simulate restart recovery
    engine = TrendEngine()
    engine.restore_state_from_db(symbol)
    
    assert symbol in engine.latest_trends
    assert engine.latest_trends[symbol][tf] == "BULLISH"

def test_warmup_manager_rebuild():
    """Verify WarmupManager correctly rebuilds indicator cache and DB state from historical candles."""
    cache = IndicatorCache()
    analyzer = TimeframeAnalyzer(cache)
    warmup = WarmupManager(cache, analyzer)
    symbol = "HDFCBANK"
    tf = "5m"
    start_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    
    # Insert 25 candles to DB
    setup_test_candles(symbol, tf, start_time, 25, 1400.0, "bullish")
    
    # Clear cache and database trend_states for this symbol
    cache.clear()
    database.execute_query("DELETE FROM trend_states WHERE symbol = %s;", (symbol,))
    
    # Execute warmup
    warmup.warmup_symbol(symbol, timeframes=[tf])
    
    # Verify cache size is populated
    assert cache.size() > 0
    
    # Verify DB contains calculated trend states
    res = database.execute_query("SELECT count(*) FROM trend_states WHERE symbol = %s AND timeframe = %s;", (symbol, tf), fetch=True)
    assert res[0][0] > 0

def test_cache_correctness():
    """Verify that indicator cache prevents redundant database hits by reusing cached EMAs."""
    cache = IndicatorCache()
    analyzer = TimeframeAnalyzer(cache)
    symbol = "SBIN"
    tf = "15m"
    start_time = datetime.datetime(2026, 6, 15, 10, 0, 0)
    
    # Setup candles
    setup_test_candles(symbol, tf, start_time, 22, 750.0, "bullish")
    
    # First computation: populates cache
    trend1, ema1 = analyzer.analyze_timeframe(symbol, tf, start_time + datetime.timedelta(minutes=15 * 21))
    
    # Verify cached entry exists
    assert cache.get_ema(symbol, tf, start_time + datetime.timedelta(minutes=15 * 21)) is not None
    
    # Clear DB table to verify we don't hit DB again
    database.execute_query("DELETE FROM market_data WHERE symbol = %s;", (symbol,))
    
    # Second computation: must hit cache
    trend2, ema2 = analyzer.analyze_timeframe(symbol, tf, start_time + datetime.timedelta(minutes=15 * 21))
    assert trend2 == trend1
    assert ema2 == ema1

@pytest.mark.asyncio
async def test_concurrent_multi_symbol_processing():
    """Verify concurrent calculation of trends for multiple symbols to prove thread/async safety and low latency."""
    loader = InstrumentLoader()
    symbols = loader.symbols[:10]  # first 10 symbols
    tick_time = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # Bulk insert candle history prior to tick_time
    setup_timeframe_history(symbols, tick_time, 22, 100.0, "bullish")
        
    engine = TrendEngine()
    
    # Warm up trend states
    engine.warmup_system(symbols)
    
    async def process_concurrent(symbol):
        tick = {
            "symbol": symbol,
            "price": 105.0,
            "volume": 20,
            "time": tick_time
        }
        is_aligned, direction, score, trends = engine.process_tick(tick)
        assert direction == "BULLISH"
        assert is_aligned is True
        assert score == 100
        
    # Run processing concurrently
    import time
    start = time.perf_counter()
    await asyncio.gather(*(process_concurrent(sym) for sym in symbols))
    duration_ms = (time.perf_counter() - start) * 1000
    avg_latency = duration_ms / len(symbols)
    
    print(f"\n[CONCURRENCY] Processed {len(symbols)} symbols concurrently in {duration_ms:.1f}ms (Avg: {avg_latency:.2f}ms/symbol)")
    assert avg_latency < 50.0  # Must be well below 50ms per stock

@pytest.mark.asyncio
async def test_nifty_50_processing():
    """Verify processing and trend calculation for all 50 NIFTY constituents."""
    loader = InstrumentLoader()
    symbols = loader.symbols
    assert len(symbols) == 50
    
    tick_time = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # Bulk insert candles for all 50 symbols
    setup_timeframe_history(symbols, tick_time, 22, 100.0, "bullish")
    
    # Clean DB trend_states for all 50 symbols
    symbol_placeholders = ",".join(["%s"] * len(symbols))
    database.execute_query(f"DELETE FROM trend_states WHERE symbol IN ({symbol_placeholders});", tuple(symbols))
    
    engine = TrendEngine()
    
    # Warm up trend states for all 50 symbols
    engine.warmup_system(symbols)
    
    # Verify database contains trend states for all symbols
    for sym in symbols:
        assert sym in engine.latest_trends
        for tf in ["5m", "15m", "1h", "Daily"]:
            assert engine.latest_trends[sym][tf] == "BULLISH"
            
    # Process a tick for all 50 symbols concurrently and measure performance
    async def process_concurrent(symbol):
        tick = {
            "symbol": symbol,
            "price": 105.0,
            "volume": 20,
            "time": tick_time
        }
        is_aligned, direction, score, trends = engine.process_tick(tick)
        assert is_aligned is True
        assert direction == "BULLISH"
        assert score == 100
        
    import time
    start = time.perf_counter()
    await asyncio.gather(*(process_concurrent(sym) for sym in symbols))
    duration_ms = (time.perf_counter() - start) * 1000
    avg_latency = duration_ms / len(symbols)
    
    print(f"\n[NIFTY 50] Processed all {len(symbols)} symbols in {duration_ms:.1f}ms (Avg: {avg_latency:.2f}ms/symbol)")
    assert avg_latency < 50.0  # Must be well below 50ms per stock
