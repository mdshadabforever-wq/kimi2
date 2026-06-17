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
