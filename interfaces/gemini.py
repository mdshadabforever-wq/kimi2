from abc import ABC, abstractmethod
from typing import Dict, Any, List

class GeminiInterface(ABC):

    @abstractmethod
    def analyze_news_impact(self, news_summary: str, fii_dii_trend: str = None, options_concentration: str = None) -> Dict[str, Any]:
        """Analyzes global and Indian news and maps impact to NIFTY 50 stocks (GEIE Engine)."""
        pass

    @abstractmethod
    def analyze_live_signal(self, signal_data: Dict[str, Any], tech_data: Dict[str, Any], current_market: Dict[str, Any], morning_geie: Dict[str, Any], breaking_news: str) -> Dict[str, Any]:
        """Analyzes a live signal under the current market context (GEIE Live Signal Analyzer Prompt 5)."""
        pass

    @abstractmethod
    def generate_report(self, prompt: str, system_context: str = None) -> str:
        """Generates general reports and analysis summaries."""
        pass

    @abstractmethod
    def generate_founder_summary(self, notes: str) -> str:
        """Processes manual founder journal entries to identify behavioral patterns."""
        pass

    @abstractmethod
    def generate_trade_story(self, trade_events: List[Dict[str, Any]]) -> str:
        """Compiles trade timeline milestones into a chronological narrative story."""
        pass

    @abstractmethod
    def generate_daily_narrative(self, session_date: str, metrics: Dict[str, Any]) -> str:
        """Synthesizes daily metrics and events into a morning/afternoon summary report."""
        pass

