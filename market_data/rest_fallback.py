import asyncio
import datetime
from interfaces.base import ServiceRegistry

class RESTFallbackClient:
    def __init__(self, tick_processor_callback):
        self.tick_processor_callback = tick_processor_callback
        self.is_polling = False
        self.poll_task = None
        self.consecutive_polls = 0

    def start_polling(self, symbols: list):
        """Starts the REST API fallback polling loop."""
        if self.is_polling:
            return
        self.is_polling = True
        self.consecutive_polls = 0
        self.poll_task = asyncio.create_task(self._poll_loop(symbols))
        print("[REST FALLBACK] Activated. Polling market data...")

    def stop_polling(self):
        """Stops the REST API fallback polling loop."""
        if not self.is_polling:
            return
        self.is_polling = False
        if self.poll_task:
            self.poll_task.cancel()
        print("[REST FALLBACK] Deactivated. Swapping back to WebSocket.")

    async def _poll_loop(self, symbols: list):
        while self.is_polling:
            try:
                upstox = ServiceRegistry.get("upstox")
                self.consecutive_polls += 1
                
                # Fetch option chains/quotes for NIFTY constituents (mocked)
                for symbol in symbols:
                    # Fetch mock tick data via REST (specifying is_rest=True)
                    quote = upstox.get_live_data(symbol, is_rest=True)
                    
                    # Feed tick to tick processor
                    if self.tick_processor_callback:
                        self.tick_processor_callback(quote)
                        
            except Exception as e:
                print(f"[REST FALLBACK] Error in polling cycle: {e}")
                
            # Poll every 5 seconds under fallback mode
            await asyncio.sleep(5)
