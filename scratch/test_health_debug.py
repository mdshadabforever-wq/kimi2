import sys
import os
import asyncio
os.environ["IIIS_TESTING"] = "True"
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from interfaces.base import ServiceRegistry
from bootstrap import register_services
import health_monitor

async def debug():
    register_services()
    upstox = ServiceRegistry.get("upstox")
    upstox.websocket_connected = True
    upstox.simulate_websocket_disconnect = False
    upstox.simulate_data_gap = True
    
    status, latency, err = await health_monitor.check_component("upstox")
    print(f"health check status: {status}")
    print(f"health check error: {err}")

if __name__ == "__main__":
    asyncio.run(debug())
