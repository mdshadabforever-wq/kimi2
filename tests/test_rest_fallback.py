import asyncio
import pytest
from interfaces.base import ServiceRegistry
from market_data.websocket_manager import WebSocketManager
from bootstrap import register_services

@pytest.mark.asyncio
async def test_rest_fallback_activation_and_deactivation():
    """Verify transition from WebSocket failure to REST polling and back to WebSocket recovery."""
    register_services()
    
    upstox = ServiceRegistry.get("upstox")
    upstox.simulate_websocket_disconnect = True
    
    received_ticks = []
    def dummy_callback(tick):
        received_ticks.append(tick)

    # Initialize manager
    manager = WebSocketManager(symbols=["TATASTEEL"], tick_processor_callback=dummy_callback)
    manager.max_ws_reconnects = 2
    manager.backoff_delay = 0.1
    
    # 1. Start manager loop
    manager.start()
    
    # Wait for reconnect attempts to trigger REST fallback
    await asyncio.sleep(0.5)
    
    # Check that REST polling was activated
    assert manager.rest_fallback.is_polling is True
    assert manager.websocket_connected is False
    
    # Wait for REST fallback to poll at least once
    await asyncio.sleep(0.6)
    assert len(received_ticks) > 0
    assert received_ticks[0]["symbol"] == "TATASTEEL"
    
    # 2. Simulate WebSocket recovery
    upstox.simulate_websocket_disconnect = False
    
    # Wait for manager to reconnect and shutdown REST
    await asyncio.sleep(0.5)
    
    assert manager.websocket_connected is True
    assert manager.rest_fallback.is_polling is False
    
    # Stop manager
    manager.stop()
