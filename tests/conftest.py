import pytest
import os
import datetime

# Ensure testing env is active
os.environ["IIIS_TESTING"] = "True"

from interfaces.base import ServiceRegistry
import database
import redis_client
import ghost_mode
import health_monitor
from bootstrap import register_services

@pytest.fixture(autouse=True)
def reset_global_simulation_states():
    """Autouse fixture that resets all simulated API, database, and Redis outages
    before every single test run to prevent test cross-contamination.
    """
    # 1. Register mocks
    register_services()
    
    # 2. Reset database and redis outage settings
    database.set_db_outage(False)
    redis_client.set_redis_outage(False)
    
    # 3. Reset Ghost Mode state
    if ghost_mode.is_ghost_mode_active():
        ghost_mode.resume_system()
        
    # 4. Reset health tracker counters
    for comp in health_monitor.failures_tracker:
        health_monitor.failures_tracker[comp] = 0
        
    # 5. Reset mock states
    upstox = ServiceRegistry.get("upstox")
    upstox.simulate_error = False
    upstox.simulate_timeout = False
    upstox.simulate_websocket_disconnect = False
    upstox.simulate_data_gap = False
    upstox.websocket_connected = True
    upstox.last_tick_time = datetime.datetime.now()
    
    perplexity = ServiceRegistry.get("perplexity")
    perplexity.simulate_error = False
    perplexity.simulate_timeout = False
    
    gemini = ServiceRegistry.get("gemini")
    gemini.simulate_error = False
    gemini.simulate_timeout = False
    
    claude = ServiceRegistry.get("claude")
    claude.simulate_error = False
    claude.simulate_timeout = False
    
    telegram = ServiceRegistry.get("telegram")
    if hasattr(telegram, "simulate_error"):
        telegram.simulate_error = False
    if hasattr(telegram, "simulate_timeout"):
        telegram.simulate_timeout = False
    if hasattr(telegram, "clear"):
        telegram.clear()
    
    nse = ServiceRegistry.get("nse")
    nse.simulate_error = False
    nse.simulate_timeout = False
    
    yield
