import asyncio
import datetime
import pytest
from interfaces.base import ServiceRegistry
import database
import redis_client
import ghost_mode
import health_monitor
from bootstrap import register_services

@pytest.mark.asyncio
async def test_health_check_cycle_success():
    """Verify that a successful health check cycle resets counters and doesn't trigger Ghost Mode."""
    register_services()
    
    # Force reset Ghost Mode
    if ghost_mode.is_ghost_mode_active():
        ghost_mode.resume_system()
        
    # Set all mocks and DB/Redis to operational
    database.set_db_outage(False)
    redis_client.set_redis_outage(False)
    
    upstox = ServiceRegistry.get("upstox")
    upstox.simulate_error = False
    upstox.simulate_timeout = False
    upstox.simulate_websocket_disconnect = False
    upstox.simulate_data_gap = False
    upstox.websocket_connected = True
    upstox.last_tick_time = datetime.datetime.now()
    
    # Run cycle
    await health_monitor.run_single_health_cycle()
    
    # Ensure tracker counts are zero
    for comp, count in health_monitor.failures_tracker.items():
        assert count == 0, f"Component {comp} has non-zero failure count: {count}"
        
    assert ghost_mode.is_ghost_mode_active() is False

@pytest.mark.asyncio
async def test_health_check_outage_triggers_ghost_mode():
    """Verify that 4 consecutive failures of a single component trigger Ghost Mode."""
    register_services()
    
    if ghost_mode.is_ghost_mode_active():
        ghost_mode.resume_system()
        
    # Simulate Redis outage
    redis_client.set_redis_outage(True)
    
    # Run 3 checks - should increment count but NOT trigger Ghost Mode yet
    for i in range(3):
        await health_monitor.run_single_health_cycle()
        assert health_monitor.failures_tracker["redis"] == i + 1
        assert ghost_mode.is_ghost_mode_active() is False
        
    # 4th check triggers Ghost Mode
    await health_monitor.run_single_health_cycle()
    assert health_monitor.failures_tracker["redis"] >= 4
    assert ghost_mode.is_ghost_mode_active() is True
    
    # Clean up and restore
    redis_client.set_redis_outage(False)
    ghost_mode.resume_system()

@pytest.mark.asyncio
async def test_upstox_websocket_failures():
    """Verify Upstox WebSocket disconnect and market data gap checks."""
    register_services()
    if ghost_mode.is_ghost_mode_active():
        ghost_mode.resume_system()
        
    upstox = ServiceRegistry.get("upstox")
    upstox.websocket_connected = True
    
    # 1. Test WebSocket disconnect simulation
    upstox.simulate_websocket_disconnect = True
    status, _, _ = await health_monitor.check_component("upstox")
    assert status == "DOWN"
    
    # 2. Test data gap simulation
    upstox.simulate_websocket_disconnect = False
    upstox.simulate_data_gap = True
    status, _, _ = await health_monitor.check_component("upstox")
    assert status == "DOWN"
    
    # Restore
    upstox.simulate_data_gap = False
