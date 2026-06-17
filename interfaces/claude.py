from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ClaudeInterface(ABC):

    @abstractmethod
    def review_watchlist_premarket(self, watchlist: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs pre-market review of the watchlist (ARC Engine 08:30 AM). Returns Prompt 4 JSON."""
        pass

    @abstractmethod
    def review_live_signal(self, signal_data: Dict[str, Any], tech_summary: Dict[str, Any], intelligence_summary: Dict[str, Any], risk_summary: Dict[str, Any], market_now: Dict[str, Any]) -> Dict[str, Any]:
        """Runs live signal review before alerting the human (ARC Live Reviewer Prompt 6)."""
        pass


    @abstractmethod
    def review_symbol(self, signal_id: str, arc_input_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Reviews a single symbol bundle.
        Returns structured ARC decision JSON matching the ARC Decision Schema v1.0.
        """
        pass

    @abstractmethod
    def review_signals_postmarket(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reviews EOD execution signals and updates inputs for next day (ARC Engine 04:00 PM)."""
        pass

    @abstractmethod
    def generate_postmortem(self, trade_facts: Dict[str, Any]) -> Dict[str, Any]:
        """Generates structured failure audits and avoidability metrics for the graveyard logs."""
        pass

    @abstractmethod
    def analyze_patterns(self, trade_logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extracts repeating win rate and R-multiple configurations for the pattern library."""
        pass

    @abstractmethod
    def generate_memory_insights(self, category: str, content: str) -> Dict[str, Any]:
        """Synthesizes structured lessons and system optimization notes."""
        pass

    @abstractmethod
    def generate_founder_review(self, notes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyzes manual notes to highlight psychological patterns, biases, and rules deviations."""
        pass


