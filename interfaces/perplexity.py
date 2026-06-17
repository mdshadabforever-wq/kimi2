from abc import ABC, abstractmethod

class PerplexityInterface(ABC):

    @abstractmethod
    def fetch_global_news(self) -> str:
        """Fetches international news data relating to trade/markets."""
        pass

    @abstractmethod
    def fetch_india_news(self) -> str:
        """Fetches domestic news data relating to Indian trade/markets."""
        pass

    @abstractmethod
    def fetch_macro_news(self) -> str:
        """Fetches macroeconomic events and updates."""
        pass

    @abstractmethod
    def fetch_sector_news(self) -> str:
        """Fetches sector specific indicators and rotations updates."""
        pass

    @abstractmethod
    def fetch_symbol_news(self, symbol: str) -> str:
        """Fetches news reports for a specific trading symbol."""
        pass

    @abstractmethod
    def fetch_earnings_lookup(self, symbol: str) -> str:
        """Fetches recent/upcoming earnings reports calendars for a symbol."""
        pass

    @abstractmethod
    def fetch_corporate_event_lookup(self, symbol: str) -> str:
        """Fetches key events, board meetings, and listings for a symbol."""
        pass

