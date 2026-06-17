from abc import ABC, abstractmethod
from typing import Dict, Any

class GeminiInterface(ABC):

    @abstractmethod
    def analyze_news_impact(self, news_summary: str, fii_dii_trend: str, options_concentration: str) -> Dict[str, Any]:
        """Analyzes global and Indian news and maps impact to NIFTY 50 stocks (GEIE Engine)."""
        pass
