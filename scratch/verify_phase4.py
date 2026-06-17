import datetime
import asyncio
import time
from decimal import Decimal
import database
from market_structure.smc_engine import SMCEngine
from market_structure.structure_persistence import StructurePersistence
from market_structure.recovery_manager import RecoveryManager
from market_data.instrument_loader import InstrumentLoader

def setup_clean_db():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM smc_structures;")
    database.execute_query("DELETE FROM order_block_memory;")
    database.execute_query("DELETE FROM market_data;")
    database.execute_query("DELETE FROM latency_metrics;")

def run_verification():
    print("=== Phase 4 SMC Engine Verification ===")
    setup_clean_db()
    
    engine = SMCEngine()
    symbol = "SBIN"
    tf = "5m"
    
    # 1. Warm up symbol
    engine.warmup_symbol(symbol)
    
    # 2. Insert 14 flat candles to establish ATR = 1.0 and recent prices
    base_time = datetime.datetime(2026, 6, 15, 9, 30, 0)
    for i in range(14):
        candle = {
            "time": base_time + datetime.timedelta(minutes=5 * i),
            "open": Decimal("100.0"),
            "high": Decimal("100.5"),
            "low": Decimal("99.5"),
            "close": Decimal("100.0")
        }
        engine.process_candle(symbol, tf, candle)
        # Also save to market_data for process_tick recovery tests
        database.execute_query(
            "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
            (candle["time"], symbol, candle["open"], candle["high"], candle["low"], candle["close"], 100, candle["close"], tf)
        )
        
    # 3. Establish Swing High at 105.0 and Swing Low at 95.0
    # Pattern: 100, 102, 105 (Swing High), 101, 98, 95 (Swing Low), 97, 100
    swings = [100.0, 102.0, 105.0, 101.0, 98.0, 95.0, 97.0, 100.0]
    for idx, price in enumerate(swings):
        t = base_time + datetime.timedelta(minutes=5 * (14 + idx))
        candle = {
            "time": t,
            "open": Decimal("100.0"),
            "high": Decimal(str(price + 0.2)),
            "low": Decimal(str(price - 0.2)),
            "close": Decimal(str(price))
        }
        engine.process_candle(symbol, tf, candle)
        database.execute_query(
            "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
            (t, symbol, candle["open"], candle["high"], candle["low"], candle["close"], 100, candle["close"], tf)
        )
        
    print(f"Latest Swing High: {engine.states[symbol][tf]['latest_swing_high']}")
    print(f"Latest Swing Low: {engine.states[symbol][tf]['latest_swing_low']}")
    
    # 4. Trigger Bullish BOS by closing above Swing High (105.0)
    bos_time = base_time + datetime.timedelta(minutes=5 * (14 + len(swings)))
    bos_candle = {
        "time": bos_time,
        "open": Decimal("104.0"),
        "high": Decimal("107.0"),
        "low": Decimal("103.0"),
        "close": Decimal("106.5") # > 105.0
    }
    engine.process_candle(symbol, tf, bos_candle)
    database.execute_query(
        "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
        (bos_time, symbol, bos_candle["open"], bos_candle["high"], bos_candle["low"], bos_candle["close"], 100, bos_candle["close"], tf)
    )
    
    # 5. Trigger Bearish CHOCH by closing below Swing Low (95.0)
    # Trend flips to BEARISH
    choch_time = base_time + datetime.timedelta(minutes=5 * (14 + len(swings) + 1))
    choch_candle = {
        "time": choch_time,
        "open": Decimal("106.0"),
        "high": Decimal("106.0"),
        "low": Decimal("93.0"),
        "close": Decimal("94.0") # < 95.0
    }
    engine.process_candle(symbol, tf, choch_candle)
    database.execute_query(
        "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
        (choch_time, symbol, choch_candle["open"], choch_candle["high"], choch_candle["low"], choch_candle["close"], 100, choch_candle["close"], tf)
    )
    
    print(f"Current trend after break: {engine.states[symbol][tf]['current_trend']}")
    
    # 6. Trigger FVG (Bullish)
    # Candle 1: High=100.0, Candle 2: Bullish impulse, Candle 3: Low=101.5
    fvg_time = base_time + datetime.timedelta(minutes=50)
    c1 = {"time": fvg_time, "open": 98.0, "high": 100.0, "low": 97.0, "close": 99.0}
    c2 = {"time": fvg_time + datetime.timedelta(minutes=5), "open": 99.0, "high": 105.0, "low": 99.0, "close": 104.0}
    c3 = {"time": fvg_time + datetime.timedelta(minutes=10), "open": 104.0, "high": 106.0, "low": 101.5, "close": 105.0}
    engine.process_candle(symbol, tf, c1)
    engine.process_candle(symbol, tf, c2)
    engine.process_candle(symbol, tf, c3)
    
    # 7. Print DB Verification results
    print("\n--- Persistence Evidence ---")
    structs = StructurePersistence.load_structures(symbol, tf)
    for s in structs:
        print(f"Structure: {s['structure_type']} | Direction: {s['direction']} | Mitigated: {s['mitigated']} | Time: {s['time']}")
        
    obs = StructurePersistence.load_order_blocks(symbol, tf)
    for ob in obs:
        print(f"Order Block: {ob['ob_type']} | High: {ob['ob_high']} | Low: {ob['ob_low']} | Midpoint: {ob['ob_midpoint']} | Time: {ob['first_detected']}")

    # 8. Test Restart Recovery
    print("\n--- Restart Recovery Evidence ---")
    # Fetch candles from database to simulate reload
    db_candles = engine._load_historical_candles(symbol, tf)
    recovered_state = RecoveryManager.recover_state(symbol, tf, db_candles)
    print(f"Recovered Trend: {recovered_state['current_trend']}")
    print(f"Recovered Swing High: {recovered_state['latest_swing_high']}")
    print(f"Recovered Swing Low: {recovered_state['latest_swing_low']}")
    print(f"Recovered Active FVGs Count: {len(recovered_state['active_fvgs'])}")
    print(f"Recovered Active OBs Count: {len(recovered_state['active_obs'])}")

async def run_perf_verification():
    print("\n--- Performance and Concurrent Execution Evidence ---")
    loader = InstrumentLoader()
    symbols = loader.symbols
    
    engine = SMCEngine()
    # Warmup all 50 symbols
    for s in symbols:
        engine.warmup_symbol(s)
        
    async def process_stock(s):
        tick = {
            "symbol": s,
            "price": 100.0,
            "volume": 20,
            "time": datetime.datetime.now()
        }
        # Force tick processing
        engine.process_tick(tick)
        
    # Run processing concurrently
    start_time = time.perf_counter()
    await asyncio.gather(*(process_stock(s) for s in symbols))
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    avg_latency = elapsed_ms / len(symbols)
    
    print(f"Processed all {len(symbols)} NIFTY symbols concurrently.")
    print(f"Total Concurrent Execution Time: {elapsed_ms:.2f}ms")
    print(f"Average Processing Latency: {avg_latency:.2f}ms per stock")
    
    # Telemetry metrics row count
    res = database.execute_query("SELECT count(*) FROM latency_metrics;", fetch=True)
    print(f"Telemetry metrics recorded in DB: {res[0][0]} rows")

if __name__ == "__main__":
    run_verification()
    asyncio.run(run_perf_verification())
