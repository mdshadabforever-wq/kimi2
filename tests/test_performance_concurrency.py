import asyncio
import datetime
import pytest
import database
from market_data.tick_processor import TickProcessor
from market_data.candle_builder import CandleBuilder
from market_data.instrument_loader import InstrumentLoader
from bootstrap import register_services

@pytest.mark.asyncio
async def test_multi_symbol_concurrency():
    """Verify that multiple symbol tick streams can be processed concurrently without race conditions."""
    register_services()
    builder = CandleBuilder()
    builder.clear_cache()
    
    processor = TickProcessor(candle_builder_callback=builder.process_tick)
    
    symbols = ["TATASTEEL", "INFY", "TCS", "HDFCBANK", "ICICIBANK"]
    
    # Clean DB
    database.execute_query("DELETE FROM raw_ticks WHERE symbol IN %s;", (tuple(symbols),))
    database.execute_query("DELETE FROM market_data WHERE symbol IN %s;", (tuple(symbols),))
    
    async def simulate_stream(symbol):
        # Process 5 sequential ticks for a symbol
        for i in range(5):
            tick = {
                "symbol": symbol,
                "price": 100.0 + i,
                "volume": 10,
                "time": datetime.datetime(2026, 6, 15, 10, 15, i)
            }
            processor.process_tick(tick)
            await asyncio.sleep(0.01) # Yield control
            
    # Run streams concurrently
    await asyncio.gather(*(simulate_stream(sym) for sym in symbols))
    
    # Verify DB records
    for sym in symbols:
        res = database.execute_query(
            "SELECT count(*) FROM raw_ticks WHERE symbol = %s;", (sym,), fetch=True
        )
        assert res[0][0] == 5
        
        res_candle = database.execute_query(
            "SELECT volume FROM market_data WHERE symbol = %s AND timeframe = '1m';", (sym,), fetch=True
        )
        assert len(res_candle) > 0

def test_50_symbol_load_simulation():
    """Simulates a peak load of 50 concurrent symbol ticks to verify latency and database throughput."""
    register_services()
    loader = InstrumentLoader()
    builder = CandleBuilder()
    builder.clear_cache()
    
    processor = TickProcessor(candle_builder_callback=builder.process_tick)
    
    # Fetch all 50 symbols
    symbols = loader.symbols
    assert len(symbols) == 50
    
    # Clean DB
    database.execute_query("DELETE FROM raw_ticks WHERE symbol IN %s;", (tuple(symbols),))
    database.execute_query("DELETE FROM market_data WHERE symbol IN %s;", (tuple(symbols),))
    
    # Start load test
    import time
    start_time = time.perf_counter()
    
    # Process 1 tick for each of the 50 symbols
    for sym in symbols:
        tick = {
            "symbol": sym,
            "price": 250.0,
            "volume": 100,
            "time": datetime.datetime(2026, 6, 15, 10, 30, 0)
        }
        res = processor.process_tick(tick)
        assert res is True
        
    duration_ms = (time.perf_counter() - start_time) * 1000
    avg_duration_ms = duration_ms / 50
    
    print(f"\n[LOAD TEST] Processed 50 symbols in {duration_ms:.1f}ms (Avg: {avg_duration_ms:.2f}ms/tick)")
    
    # Assert average processing time is strictly < 100ms
    assert avg_duration_ms < 100.0
