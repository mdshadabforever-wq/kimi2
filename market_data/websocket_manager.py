import asyncio
import datetime
from interfaces.base import ServiceRegistry
from market_data.rest_fallback import RESTFallbackClient
import ghost_mode

class WebSocketManager:
    def __init__(self, symbols: list, tick_processor_callback):
        self.symbols = symbols
        self.tick_processor_callback = tick_processor_callback
        
        self.rest_fallback = RESTFallbackClient(tick_processor_callback)
        self.websocket_connected = False
        
        # Connection parameters
        self.reconnect_attempts = 0
        self.max_ws_reconnects = 3
        self.backoff_delay = 1.0 # starts at 1s
        self.max_backoff = 60.0
        
        self.ws_loop_task = None
        self.running = False
        
        # Diagnostics
        self.root_cause = "unknown"

    def start(self):
        """Starts the main WebSocket management loop."""
        self.running = True
        self.ws_loop_task = asyncio.create_task(self._management_loop())
        print("[WS MANAGER] Started.")

    def stop(self):
        """Stops the WebSocket management loop and any fallback polling."""
        self.running = False
        self.websocket_connected = False
        if self.ws_loop_task:
            self.ws_loop_task.cancel()
        self.rest_fallback.stop_polling()
        print("[WS MANAGER] Stopped.")

    async def _management_loop(self):
        upstox = ServiceRegistry.get("upstox")
        
        while self.running:
            try:
                if not self.websocket_connected:
                    print(f"[WS MANAGER] Connecting to Upstox WebSocket (Attempt {self.reconnect_attempts + 1})...")
                    upstox.connect_websocket()
                    
                    # Connection succeeded!
                    self.websocket_connected = True
                    self.reconnect_attempts = 0
                    self.backoff_delay = 1.0 # Reset backoff delay
                    
                    # Stop REST polling if active
                    if self.rest_fallback.is_polling:
                        self.rest_fallback.stop_polling()
                        
                    print("[WS MANAGER] WebSocket connection established successfully.")
                    
                # Monitor tick gap while connected
                gap = datetime.datetime.now() - upstox.last_tick_time
                if gap.total_seconds() > 120:
                    # Data gap detected! Determine root cause (Requirement 7)
                    if not upstox.websocket_connected:
                        self.root_cause = "websocket disconnect"
                    elif upstox.simulate_error or upstox.simulate_timeout:
                        self.root_cause = "mock outage"
                    else:
                        self.root_cause = "exchange silence"
                        
                    reason = f"Data gap of {gap.total_seconds():.1f}s detected. Root cause: {self.root_cause}."
                    ghost_mode.activate_ghost_mode(reason)
                    self.stop()
                    break

            except Exception as e:
                # Connection failed! Apply reconnect / backoff logic
                self.websocket_connected = False
                self.reconnect_attempts += 1
                
                print(f"[WS MANAGER] WebSocket failure: {e}")
                
                # Check if we should activate REST fallback
                if self.reconnect_attempts >= self.max_ws_reconnects:
                    if not self.rest_fallback.is_polling:
                        print(f"[WS MANAGER] Max reconnect attempts reached ({self.max_ws_reconnects}). Swapping to REST fallback.")
                        self.rest_fallback.start_polling(self.symbols)
                
                # Calculate backoff delay
                delay = self.backoff_delay
                self.backoff_delay = min(self.backoff_delay * 2, self.max_backoff) # Double delay
                
                print(f"[WS MANAGER] Reconnecting in {delay} seconds...")
                await asyncio.sleep(delay)
                continue
                
            # Check state every 5 seconds
            await asyncio.sleep(5)
