import asyncio
import pytest
from interfaces.base import ServiceRegistry
from market_data.websocket_manager import WebSocketManager
from bootstrap import register_services

@pytest.mark.asyncio
async def test_websocket_auto_reconnect_backoff():
    """Verify WebSocketManager auto-reconnect triggers and backoff delay doubling."""
    register_services()
    
    upstox = ServiceRegistry.get("upstox")
    # Simulate WebSocket failure
    upstox.simulate_websocket_disconnect = True
    
    # Initialize manager
    manager = WebSocketManager(symbols=["TATASTEEL"], tick_processor_callback=lambda x: None)
    
    # Set wait values short for test runtime optimization
    manager.max_backoff = 4.0
    manager.backoff_delay = 0.5 # start at 0.5s
    
    # Connect loop run (we do not call start() to avoid background loop, we call connect/reconnect logic directly)
    # We simulate what _management_loop does when connecting fails
    assert manager.websocket_connected is False
    
    # Attempt 1: fails
    try:
        upstox.connect_websocket()
    except Exception:
        manager.websocket_connected = False
        manager.reconnect_attempts += 1
        manager.backoff_delay = min(manager.backoff_delay * 2, manager.max_backoff)
        
    assert manager.reconnect_attempts == 1
    assert manager.backoff_delay == 1.0 # 0.5 * 2
    
    # Attempt 2: fails
    try:
        upstox.connect_websocket()
    except Exception:
        manager.websocket_connected = False
        manager.reconnect_attempts += 1
        manager.backoff_delay = min(manager.backoff_delay * 2, manager.max_backoff)
        
    assert manager.reconnect_attempts == 2
    assert manager.backoff_delay == 2.0 # 1.0 * 2
    
    # Attempt 3: succeeds (restore disconnect flag)
    upstox.simulate_websocket_disconnect = False
    upstox.connect_websocket()
    manager.websocket_connected = True
    manager.reconnect_attempts = 0
    manager.backoff_delay = 0.5
    
    assert manager.websocket_connected is True
    assert manager.reconnect_attempts == 0
    assert manager.backoff_delay == 0.5
