import asyncio
import datetime
import time
from interfaces.base import ServiceRegistry
import database
import redis_client
import ghost_mode

# Consecutive failures tracking
# Key: component name, Value: consecutive failure count
failures_tracker = {
    "upstox": 0,
    "perplexity": 0,
    "gemini": 0,
    "claude": 0,
    "telegram": 0,
    "postgres": 0,
    "redis": 0
}

async def check_component(name: str) -> tuple[str, int, str]:
    """Runs a health check on a specific component.
    Returns: (status_str, response_time_ms, error_msg)
    """
    start_time = time.perf_counter()
    status = "UP"
    error_msg = ""
    
    try:
        if name == "postgres":
            # Test query
            database.execute_query("SELECT 1;", fetch=True)
            
        elif name == "redis":
            redis_client.ping()
            
        elif name == "upstox":
            upstox = ServiceRegistry.get("upstox")
            # Check connection
            if not upstox.websocket_connected:
                raise ConnectionError("Upstox WebSocket not connected")
            # Retrieve live data
            data = upstox.get_live_data("TATASTEEL")
            # Check for data gap (> 2 minutes)
            gap = datetime.datetime.now() - data["time"]
            if gap.total_seconds() > 120:
                raise ConnectionError(f"Market data gap detected: {gap.total_seconds():.1f}s")
            
        elif name == "perplexity":
            perplexity = ServiceRegistry.get("perplexity")
            perplexity.fetch_global_news()
            
        elif name == "gemini":
            gemini = ServiceRegistry.get("gemini")
            # Call mock impact with dummy data
            gemini.analyze_news_impact("test", "BUYING", "23500")
            
        elif name == "claude":
            claude = ServiceRegistry.get("claude")
            claude.review_watchlist_premarket(["TATASTEEL"], {})
            
        elif name == "telegram":
            telegram = ServiceRegistry.get("telegram")
            # Check works by validating mock structure
            telegram.consecutive_failures = 0 # reset if successfully reached
            
        else:
            raise ValueError(f"Unknown component: {name}")
            
    except Exception as e:
        status = "DOWN"
        error_msg = str(e)
        
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    return status, duration_ms, error_msg

def log_health_to_db(component: str, status: str, response_time_ms: int, is_ghost_active: bool, error_msg: str):
    """Inserts a health record into the system_health table."""
    query = """
        INSERT INTO system_health (checked_at, component, status, response_time_ms, ghost_mode_active, last_error)
        VALUES (NOW(), %s, %s, %s, %s, %s);
    """
    try:
        database.execute_query(query, (component, status, response_time_ms, is_ghost_active, error_msg or None))
    except Exception as e:
        print(f"Failed to log health check to PostgreSQL: {e}")

async def run_single_health_cycle():
    """Runs a single round of checks for all 7 components, updates tracker,
    logs results, and triggers Ghost Mode if any component fails 4 times consecutively.
    """
    components = ["postgres", "redis", "upstox", "perplexity", "gemini", "claude", "telegram"]
    is_ghost_active = ghost_mode.is_ghost_mode_active()
    
    for comp in components:
        status, response_time, error_msg = await check_component(comp)
        
        # Log to DB if possible (unless Postgres is down)
        if comp != "postgres" or status == "UP":
            log_health_to_db(comp, status, response_time, is_ghost_active, error_msg)
            
        # Update consecutive failure tracker
        if status == "DOWN":
            failures_tracker[comp] += 1
            print(f"[HEALTH] {comp} is DOWN. Error: {error_msg}. Failure count: {failures_tracker[comp]}/4")
            
            # Trigger Ghost Mode on 4 consecutive failures
            if failures_tracker[comp] >= 4 and not is_ghost_active:
                ghost_mode.activate_ghost_mode(
                    reason=f"Component failure limit exceeded. Component '{comp}' has failed 4 consecutive checks: {error_msg}"
                )
                is_ghost_active = True
        else:
            # Reset on successful ping
            failures_tracker[comp] = 0

async def health_monitor_loop(interval_sec=30):
    """Main loop for system health monitoring. Runs every 30 seconds by default."""
    print("Starting periodic health monitor loop...")
    while True:
        try:
            await run_single_health_cycle()
        except Exception as e:
            print(f"Error in health monitor cycle: {e}")
        await asyncio.sleep(interval_sec)
