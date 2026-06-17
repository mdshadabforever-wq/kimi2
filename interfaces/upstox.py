from abc import ABC, abstractmethod

class UpstoxInterface(ABC):
    
    @abstractmethod
    def connect_websocket(self):
        """Initializes and connects the live WebSocket feed."""
        pass
        
    @abstractmethod
    def disconnect_websocket(self):
        """Disconnects the WebSocket feed."""
        pass

    @abstractmethod
    def get_live_data(self, symbol: str, is_rest: bool = False):
        """Retrieves latest tick/price data for a symbol.
        is_rest: set to True if pulling via REST fallback quote API.
        """
        pass

    @abstractmethod
    def get_option_chain(self, symbol: str):
        """Retrieves options data chain for a symbol."""
        pass

    @abstractmethod
    def get_historical_candles(self, symbol: str, timeframe: str, lookback_days: int):
        """Fetches historical OHLCV data."""
        pass
