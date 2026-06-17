import datetime
import pytest
from decimal import Decimal
import database
from config import Config
from market_data.candle_builder import CandleBuilder, get_candle_boundary, is_market_session_active

def test_nse_session_boundaries():
    """Verify market session filters (Monday-Friday, 09:15-15:30, no holidays)."""
    _orig = Config.MOCK_MODE
    Config.MOCK_MODE = False
    try:
        # 1. Valid weekday session time
        dt_valid = datetime.datetime(2026, 6, 15, 10, 30, 0) # Monday
        assert is_market_session_active(dt_valid) is True
        
        # 2. Weekend
        dt_weekend = datetime.datetime(2026, 6, 14, 10, 30, 0) # Sunday
        assert is_market_session_active(dt_weekend) is False
        
        # 3. Off hours (09:00 AM)
        dt_early = datetime.datetime(2026, 6, 15, 9, 0, 0)
        assert is_market_session_active(dt_early) is False
        
        # 4. National Holiday (Republic Day)
        dt_holiday = datetime.datetime(2026, 1, 26, 11, 0, 0)
        assert is_market_session_active(dt_holiday) is False
    finally:
        Config.MOCK_MODE = _orig

def test_deterministic_candle_math():
    """Verify candle math matches spec example:
    Ticks:
      - 09:15:01 -> 100 (Vol: 100)
      - 09:15:10 -> 101 (Vol: 100)
      - 09:15:20 -> 99  (Vol: 100)
      - 09:15:50 -> 102 (Vol: 100)
    Expected 1m candle (O:100, H:102, L:99, C:102).
    """
    builder = CandleBuilder()
    builder.clear_cache()
    
    # Clean up DB for this test timestamp to run clean
    test_time = datetime.datetime(2026, 6, 15, 9, 15, 0) # Monday
    database.execute_query("DELETE FROM market_data WHERE symbol = 'TATASTEEL' AND time = %s;", (test_time,))
    
    ticks = [
        {"symbol": "TATASTEEL", "price": 100.0, "volume": 100, "time": datetime.datetime(2026, 6, 15, 9, 15, 1)},
        {"symbol": "TATASTEEL", "price": 101.0, "volume": 100, "time": datetime.datetime(2026, 6, 15, 9, 15, 10)},
        {"symbol": "TATASTEEL", "price": 99.0,  "volume": 100, "time": datetime.datetime(2026, 6, 15, 9, 15, 20)},
        {"symbol": "TATASTEEL", "price": 102.0, "volume": 100, "time": datetime.datetime(2026, 6, 15, 9, 15, 50)}
    ]
    
    for t in ticks:
        builder.process_tick(t)
        
    # Query database to check generated 1m candle
    res = database.execute_query(
        "SELECT open, high, low, close, volume FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;",
        (test_time,), fetch=True
    )
    assert res is not None
    assert len(res) == 1
    
    o, h, l, c, v = res[0]
    assert o == Decimal("100.0000")
    assert h == Decimal("102.0000")
    assert l == Decimal("99.0000")
    assert c == Decimal("102.0000")
    assert v == 400

def test_duplicate_tick_filtering():
    """Verify that duplicate ticks are ignored and do not double aggregate volume."""
    builder = CandleBuilder()
    builder.clear_cache()
    
    test_time = datetime.datetime(2026, 6, 15, 9, 20, 0)
    database.execute_query("DELETE FROM market_data WHERE symbol = 'TATASTEEL' AND time = %s;", (test_time,))
    
    tick = {"symbol": "TATASTEEL", "price": 150.0, "volume": 10, "time": datetime.datetime(2026, 6, 15, 9, 20, 5)}
    
    # Send twice
    builder.process_tick(tick)
    builder.process_tick(tick)
    
    res = database.execute_query(
        "SELECT volume FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;",
        (test_time,), fetch=True
    )
    # Volume should only be 10 (second duplicate tick was discarded)
    assert res[0][0] == 10

def test_out_of_order_tick_processing():
    """Verify out-of-order ticks update the correct candle retroactively."""
    builder = CandleBuilder()
    builder.clear_cache()
    
    t1 = datetime.datetime(2026, 6, 15, 9, 30, 0)
    t2 = datetime.datetime(2026, 6, 15, 9, 31, 0)
    
    database.execute_query("DELETE FROM market_data WHERE symbol = 'TATASTEEL' AND time IN (%s, %s);", (t1, t2))
    
    # 1. Process tick for 09:31:00
    builder.process_tick({"symbol": "TATASTEEL", "price": 120.0, "volume": 5, "time": datetime.datetime(2026, 6, 15, 9, 31, 10)})
    
    # 2. Process delayed/out-of-order tick for 09:30:00 (which belongs to a previous candle boundary)
    builder.process_tick({"symbol": "TATASTEEL", "price": 115.0, "volume": 8, "time": datetime.datetime(2026, 6, 15, 9, 30, 20)})
    
    # Verify both candles exist in database
    res1 = database.execute_query("SELECT volume, close FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;", (t1,), fetch=True)
    res2 = database.execute_query("SELECT volume, close FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;", (t2,), fetch=True)
    
    assert res1[0][0] == 8
    assert res1[0][1] == Decimal("115.0000")
    assert res2[0][0] == 5
    assert res2[0][1] == Decimal("120.0000")

def test_process_restart_recovery():
    """Verify candle state recovery: reload existing database candle and continue aggregation."""
    builder = CandleBuilder()
    builder.clear_cache()
    
    test_time = datetime.datetime(2026, 6, 15, 9, 45, 0)
    database.execute_query("DELETE FROM market_data WHERE symbol = 'TATASTEEL' AND time = %s;", (test_time,))
    
    # 1. Simulate process 1: aggregate first tick
    builder.process_tick({"symbol": "TATASTEEL", "price": 100.0, "volume": 10, "time": datetime.datetime(2026, 6, 15, 9, 45, 5)})
    
    # 2. Simulate process crash/restart by clearing active builder memory
    builder.clear_cache()
    
    # 3. Simulate process 2: receive next tick in same candle boundary.
    # It must reload previous candle values from DB and update correctly.
    builder.process_tick({"symbol": "TATASTEEL", "price": 105.0, "volume": 15, "time": datetime.datetime(2026, 6, 15, 9, 45, 15)})
    
    res = database.execute_query(
        "SELECT open, high, low, close, volume FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;",
        (test_time,), fetch=True
    )
    o, h, l, c, v = res[0]
    assert o == Decimal("100.0000") # Kept from first run
    assert h == Decimal("105.0000") # Updated High
    assert l == Decimal("100.0000") # Kept Low
    assert c == Decimal("105.0000") # Updated Close
    assert v == 25                  # Aggregated Volume (10 + 15)

def test_rebuild_candles_from_ticks():
    """Verify that candles can be rebuilt completely from raw_ticks database table."""
    builder = CandleBuilder()
    
    # Setup test boundary
    symbol = "INFY"
    t1 = datetime.datetime(2026, 6, 15, 10, 0, 0)
    
    # Clean DB
    database.execute_query("DELETE FROM raw_ticks WHERE symbol = %s;", (symbol,))
    database.execute_query("DELETE FROM market_data WHERE symbol = %s;", (symbol,))
    
    # Insert raw ticks
    database.execute_query(
        "INSERT INTO raw_ticks (time, symbol, price, volume) VALUES (%s, %s, %s, %s), (%s, %s, %s, %s);",
        (
            datetime.datetime(2026, 6, 15, 10, 0, 5), symbol, 500.0, 5,
            datetime.datetime(2026, 6, 15, 10, 0, 25), symbol, 505.0, 10
        )
    )
    
    # Run rebuild
    builder.rebuild_candles_from_raw_ticks(
        symbol=symbol,
        timeframe="1m",
        start_time=datetime.datetime(2026, 6, 15, 9, 59, 0),
        end_time=datetime.datetime(2026, 6, 15, 10, 2, 0)
    )
    
    # Verify rebuilt candle
    res = database.execute_query(
        "SELECT open, high, low, close, volume FROM market_data WHERE symbol=%s AND timeframe='1m' AND time=%s;",
        (symbol, t1), fetch=True
    )
    assert res is not None
    assert len(res) == 1
    o, h, l, c, v = res[0]
    assert o == Decimal("500.0000")
    assert h == Decimal("505.0000")
    assert l == Decimal("500.0000")
    assert c == Decimal("505.0000")
    assert v == 15

def test_candle_boundary_transitions():
    """Verify that ticks transitioning across boundaries correctly close the old candle and start a new one."""
    builder = CandleBuilder()
    builder.clear_cache()
    
    t1 = datetime.datetime(2026, 6, 15, 9, 20, 0)
    t2 = datetime.datetime(2026, 6, 15, 9, 21, 0)
    database.execute_query("DELETE FROM market_data WHERE symbol = 'TATASTEEL' AND time IN (%s, %s);", (t1, t2))
    
    # Tick inside first 1m boundary (09:20:00 - 09:20:59)
    builder.process_tick({"symbol": "TATASTEEL", "price": 100.0, "volume": 10, "time": datetime.datetime(2026, 6, 15, 9, 20, 30)})
    
    # Tick on the boundary transition (09:21:00) which should belong to the next candle
    builder.process_tick({"symbol": "TATASTEEL", "price": 105.0, "volume": 15, "time": datetime.datetime(2026, 6, 15, 9, 21, 0)})
    
    # Verify first candle
    res1 = database.execute_query("SELECT volume, close FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;", (t1,), fetch=True)
    assert res1 is not None and len(res1) == 1
    assert res1[0][0] == 10
    assert res1[0][1] == Decimal("100.0000")
    
    # Verify transitioned candle
    res2 = database.execute_query("SELECT volume, close FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;", (t2,), fetch=True)
    assert res2 is not None and len(res2) == 1
    assert res2[0][0] == 15
    assert res2[0][1] == Decimal("105.0000")

def test_market_open_candle_creation():
    """Verify that ticks exactly at market open are ingested, but ticks before are ignored."""
    _orig = Config.MOCK_MODE
    Config.MOCK_MODE = False
    try:
        builder = CandleBuilder()
        builder.clear_cache()
        
        t_open = datetime.datetime(2026, 6, 15, 9, 15, 0)
        database.execute_query("DELETE FROM market_data WHERE symbol = 'TATASTEEL' AND time = %s;", (t_open,))
        
        # Tick 1 second before market open (should be ignored)
        builder.process_tick({"symbol": "TATASTEEL", "price": 99.0, "volume": 5, "time": datetime.datetime(2026, 6, 15, 9, 14, 59)})
        
        # Tick exactly at market open (should be processed)
        builder.process_tick({"symbol": "TATASTEEL", "price": 100.0, "volume": 10, "time": datetime.datetime(2026, 6, 15, 9, 15, 0)})
        
        # Verify open candle exists and has correct volume from the open tick only
        res = database.execute_query("SELECT volume, open FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;", (t_open,), fetch=True)
        assert res is not None and len(res) == 1
        assert res[0][0] == 10
        assert res[0][1] == Decimal("100.0000")
    finally:
        Config.MOCK_MODE = _orig

def test_market_close_candle_creation():
    """Verify that ticks exactly at market close are ingested, but ticks after are ignored."""
    _orig = Config.MOCK_MODE
    Config.MOCK_MODE = False
    try:
        builder = CandleBuilder()
        builder.clear_cache()
        
        t_close_boundary = datetime.datetime(2026, 6, 15, 15, 30, 0)
        database.execute_query("DELETE FROM market_data WHERE symbol = 'TATASTEEL' AND time = %s;", (t_close_boundary,))
        
        # Tick exactly at market close (should be processed)
        builder.process_tick({"symbol": "TATASTEEL", "price": 100.0, "volume": 10, "time": datetime.datetime(2026, 6, 15, 15, 30, 0)})
        
        # Tick 1 second after market close (should be ignored)
        builder.process_tick({"symbol": "TATASTEEL", "price": 101.0, "volume": 20, "time": datetime.datetime(2026, 6, 15, 15, 30, 1)})
        
        # Verify close candle exists and has volume only from the close tick
        res = database.execute_query("SELECT volume, close FROM market_data WHERE symbol='TATASTEEL' AND timeframe='1m' AND time=%s;", (t_close_boundary,), fetch=True)
        assert res is not None and len(res) == 1
        assert res[0][0] == 10
        assert res[0][1] == Decimal("100.0000")
    finally:
        Config.MOCK_MODE = _orig
