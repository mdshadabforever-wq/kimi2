from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ClaudeInterface(ABC):

    @abstractmethod
    def review_watchlist_premarket(self, watchlist: List[str], context: Dict[str, Any]) -> Dict[str, str]:
        """Runs pre-market review of the watchlist (ARC Engine 08:20 AM). Returns APPROVE/CAUTION/REJECT per symbol."""
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

