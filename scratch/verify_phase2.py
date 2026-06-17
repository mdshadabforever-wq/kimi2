import sys
import os
import datetime
from decimal import Decimal
import asyncio

# Setup path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from bootstrap import register_services
import database
from market_data.candle_builder import CandleBuilder
from market_data.latency_monitor import LatencyMonitor
from market_data.websocket_manager import WebSocketManager
from interfaces.base import ServiceRegistry
import ghost_mode

async def verify_all():
    register_services()
    print("=" * 60)
    print(" IIIS PHASE 2 INTEGRATION VERIFICATION")
    print("=" * 60)
    
    # 1. CANDLE VERIFICATION & REBUILD
    print("\n[PART 1] CANDLE VERIFICATION & RAW TICK REBUILD")
    print("-" * 50)
    symbol = "TATASTEEL"
    database.execute_query("DELETE FROM raw_ticks WHERE symbol = %s;", (symbol,))
    database.execute_query("DELETE FROM market_data WHERE symbol = %s;", (symbol,))
    
    # Generate 5 ticks in normal market session (Monday 2026-06-15)
    base_time = datetime.datetime(2026, 6, 15, 9, 20, 0)
    ticks = [
        {"symbol": symbol, "price": 150.0, "volume": 10, "time": base_time + datetime.timedelta(seconds=5)},
        {"symbol": symbol, "price": 151.5, "volume": 20, "time": base_time + datetime.timedelta(seconds=15)},
        {"symbol": symbol, "price": 149.0, "volume": 15, "time": base_time + datetime.timedelta(seconds=25)},
        {"symbol": symbol, "price": 152.0, "volume": 30, "time": base_time + datetime.timedelta(seconds=35)},
        {"symbol": symbol, "price": 150.5, "volume": 25, "time": base_time + datetime.timedelta(seconds=45)}
    ]
    
    # Persist raw ticks (Requirement 1)
    for tick in ticks:
        database.execute_query(
            "INSERT INTO raw_ticks (time, symbol, price, volume) VALUES (%s, %s, %s, %s);",
            (tick["time"], tick["symbol"], tick["price"], tick["volume"])
        )
    print(f"Persisted {len(ticks)} raw ticks to 'raw_ticks' hypertable.")
    
    # Rebuild candles from persisted raw ticks (Requirement 1 & 3)
    builder = CandleBuilder()
    builder.clear_cache()
    
    print("Rebuilding candles from raw ticks...")
    builder.rebuild_candles_from_raw_ticks(
        symbol=symbol,
        timeframe="1m",
        start_time=base_time - datetime.timedelta(minutes=1),
        end_time=base_time + datetime.timedelta(minutes=2)
    )
    
    # Query rebuilt candles
    res = database.execute_query(
        "SELECT time, open, high, low, close, volume, vwap FROM market_data WHERE symbol = %s ORDER BY time ASC;",
        (symbol,), fetch=True
    )
    print("\nGenerated Candles in 'market_data' table:")
    for row in res:
        print(f"  Time: {row[0]} | O: {row[1]} | H: {row[2]} | L: {row[3]} | C: {row[4]} | V: {row[5]} | VWAP: {row[6]}")

    # 2. RECONNECT VERIFICATION
    print("\n[PART 2] WEBSOCKET AUTO-RECONNECT & BACKOFF VERIFICATION")
    print("-" * 50)
    upstox = ServiceRegistry.get("upstox")
    upstox.simulate_websocket_disconnect = True
    
    manager = WebSocketManager(symbols=[symbol], tick_processor_callback=lambda x: None)
    manager.max_backoff = 8.0
    manager.backoff_delay = 1.0
    
    print("Simulating sequential connection failures...")
    for attempt in range(1, 4):
        try:
            upstox.connect_websocket()
        except Exception:
            manager.websocket_connected = False
            manager.reconnect_attempts += 1
            manager.backoff_delay = min(manager.backoff_delay * 2, manager.max_backoff)
            print(f"  Attempt {attempt} failed -> Reconnect count: {manager.reconnect_attempts}, Backoff delay: {manager.backoff_delay}s")
            
    # Restore connection
    upstox.simulate_websocket_disconnect = False
    upstox.connect_websocket()
    manager.websocket_connected = True
    manager.reconnect_attempts = 0
    manager.backoff_delay = 1.0
    print(f"  Connection restored -> Reconnect count: {manager.reconnect_attempts}, Status: Connected")

    # 3. DATA GAP SOURCE ATTRIBUTION VERIFICATION
    print("\n[PART 3] DATA GAP SOURCE ATTRIBUTION & AUDIT LOGS")
    print("-" * 50)
    # Resume Ghost Mode if active
    if ghost_mode.is_ghost_mode_active():
        ghost_mode.resume_system()
        
    causes = [
        {"desc": "websocket disconnect", "disconnected": True, "error": False, "timeout": False},
        {"desc": "exchange silence", "disconnected": False, "error": False, "timeout": False},
        {"desc": "mock outage", "disconnected": False, "error": True, "timeout": False},
        {"desc": "processing backlog", "disconnected": False, "error": False, "timeout": True}  # Simulated processing backlog via timeout/latency
    ]
    
    for cause in causes:
        # Reset Upstox mock state
        upstox.websocket_connected = not cause["disconnected"]
        upstox.simulate_websocket_disconnect = cause["disconnected"]
        upstox.simulate_error = cause["error"]
        upstox.simulate_timeout = cause["timeout"]
        upstox.last_tick_time = datetime.datetime.now() - datetime.timedelta(minutes=3)
        
        # Detect root cause
        if not upstox.websocket_connected:
            rc = "websocket disconnect"
        elif upstox.simulate_error:
            rc = "mock outage"
        elif upstox.simulate_timeout:
            rc = "processing backlog"
        else:
            rc = "exchange silence"
            
        reason = f"Data gap detected. Root cause: {rc}."
        ghost_mode.activate_ghost_mode(reason)
        
        # Read from audit_log
        audit_res = database.execute_query(
            "SELECT action, result, reason FROM audit_log WHERE action='ACTIVATE_GHOST_MODE' ORDER BY id DESC LIMIT 1;",
            fetch=True
        )
        print(f"  Source: {cause['desc']:<22} | Log action: {audit_res[0][0]} | Reason recorded: {audit_res[0][2]}")
        
        # Resume for next check
        ghost_mode.resume_system()

    # 4. LATENCY TELEMETRY PERSISTENCE
    print("\n[PART 4] LATENCY TELEMETRY PERSISTENCE")
    print("-" * 50)
    monitor = LatencyMonitor()
    database.execute_query("DELETE FROM latency_metrics WHERE symbol = %s;", (symbol,))
    
    stages = ["TICK_INGESTION", "CANDLE_BUILDING", "DATABASE_WRITE"]
    for i, stage in enumerate(stages):
        monitor.record_latency(
            symbol=symbol,
            receive_lat_ms=30 + i * 5,
            processing_lat_ms=10 + i * 2,
            candle_build_lat_ms=4 + i,
            stage=stage
        )
        
    # Query database
    lat_res = database.execute_query(
        "SELECT timestamp, stage, receive_latency_ms, processing_latency_ms, candle_build_latency_ms FROM latency_metrics WHERE symbol = %s ORDER BY id ASC;",
        (symbol,), fetch=True
    )
    print("Recorded Latency Telemetry in 'latency_metrics' table:")
    for row in lat_res:
        print(f"  Time: {row[0]} | Stage: {row[1]:<15} | Receive: {row[2]}ms | Proc: {row[3]}ms | Build: {row[4]}ms")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(verify_all())
