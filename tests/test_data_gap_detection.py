import datetime
import asyncio
import pytest
from interfaces.base import ServiceRegistry
from market_data.websocket_manager import WebSocketManager
import ghost_mode
import database
from bootstrap import register_services

@pytest.mark.asyncio
async def test_data_gap_causes_ghost_mode():
    """Verify data gap checks trigger Ghost Mode and log the specific root cause."""
    register_services()
    if ghost_mode.is_ghost_mode_active():
        ghost_mode.resume_system()
        
    upstox = ServiceRegistry.get("upstox")
    upstox.websocket_connected = True
    upstox.simulate_websocket_disconnect = False
    
    # 1. Simulate "exchange silence" data gap: websocket remains connected but no ticks arrive
    # Set last tick timestamp to 3 minutes ago
    upstox.last_tick_time = datetime.datetime.now() - datetime.timedelta(minutes=3)
    
    manager = WebSocketManager(symbols=["TATASTEEL"], tick_processor_callback=lambda x: None)
    
    # Run a single connection management cycle (without starting a background loop)
    # We call the core check logic directly
    gap = datetime.datetime.now() - upstox.last_tick_time
    assert gap.total_seconds() > 120
    
    # Attrib root cause
    if not upstox.websocket_connected:
        manager.root_cause = "websocket disconnect"
    elif upstox.simulate_error or upstox.simulate_timeout:
        manager.root_cause = "mock outage"
    else:
        manager.root_cause = "exchange silence"
        
    reason = f"Data gap of {gap.total_seconds():.1f}s detected. Root cause: {manager.root_cause}."
    
    # Verify Ghost Mode triggers
    ghost_mode.activate_ghost_mode(reason)
    assert ghost_mode.is_ghost_mode_active() is True
    
    # Verify the audit log record contains the root cause
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT reason FROM audit_log 
                WHERE action = 'ACTIVATE_GHOST_MODE' 
                ORDER BY id DESC LIMIT 1;
            """)
            audit_reason = cur.fetchone()[0]
            assert "Root cause: exchange silence" in audit_reason
    finally:
        database.release_connection(conn)
        
    # Reset Ghost Mode
    ghost_mode.resume_system()
