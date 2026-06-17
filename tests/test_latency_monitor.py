import pytest
import database
from market_data.latency_monitor import LatencyMonitor

def test_latency_telemetry_persistence():
    """Verify that LatencyMonitor correctly saves latency values to the database."""
    monitor = LatencyMonitor()
    
    symbol = "TATASTEEL"
    stage = "TICK_INGESTION"
    
    # Clean up DB for test run
    database.execute_query("DELETE FROM latency_metrics WHERE symbol = %s;", (symbol,))
    
    # Record
    monitor.record_latency(
        symbol=symbol,
        receive_lat_ms=45,
        processing_lat_ms=12,
        candle_build_lat_ms=5,
        stage=stage
    )
    
    # Query database
    res = database.execute_query(
        "SELECT receive_latency_ms, processing_latency_ms, candle_build_latency_ms, stage FROM latency_metrics WHERE symbol = %s;",
        (symbol,), fetch=True
    )
    assert res is not None
    assert len(res) == 1
    
    rec_lat, proc_lat, build_lat, db_stage = res[0]
    assert rec_lat == 45
    assert proc_lat == 12
    assert build_lat == 5
    assert db_stage == stage
