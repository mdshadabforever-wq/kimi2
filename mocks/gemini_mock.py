from typing import Dict, Any, List
from interfaces.gemini import GeminiInterface

class GeminiMock(GeminiInterface):
    def __init__(self):
        self.simulate_error = False
        self.simulate_timeout = False
        self.consecutive_failures = 0

    def _handle_failures(self):
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated Gemini API Error")
        if self.simulate_timeout:
            self.consecutive_failures += 1
            raise TimeoutError("Simulated Gemini API Timeout")
        self.consecutive_failures = 0

    def analyze_news_impact(self, news_summary: str, fii_dii_trend: str = None, options_concentration: str = None) -> Dict[str, Any]:
        self._handle_failures()
        return {
            "event_id": "GEIE-2026-06-15-001",
            "timestamp": "2026-06-15 08:05:00 IST",
            "market_sentiment": "RISK_ON",
            "stock_impacts": {
                "TATASTEEL": {
                    "direction": "POSITIVE",
                    "magnitude": 2,
                    "reasons": ["China production cuts"],
                    "confidence": "HIGH",
                    "urgency": "INTRADAY"
                },
                "INFY": {
                    "direction": "NEUTRAL",
                    "magnitude": 1,
                    "reasons": ["Stable US IT spending"],
                    "confidence": "MEDIUM",
                    "urgency": "INTRADAY"
                }
            },
            "fii_5day_trend": "BUYING",
            "institutional_bias": "BULLISH",
            "key_support_from_options": "23400",
            "key_resistance_from_options": "23700",
            "top_beneficiaries": ["TATASTEEL", "JSWSTEEL"],
            "top_losers": [],
            "geie_status": "ACTIVE"
        }

    def analyze_live_signal(self, signal_data: Dict[str, Any], tech_data: Dict[str, Any], current_market: Dict[str, Any], morning_geie: Dict[str, Any], breaking_news: str) -> Dict[str, Any]:
        self._handle_failures()
        symbol = signal_data.get("symbol", "RELIANCE")
        import time
        return {
            "geie_live_id": f"GEIE-LIVE-{int(time.time())}",
            "symbol": symbol,
            "recommendation": "PROCEED",
            "confidence_boost": True,
            "key_observation": "Mock live check holds positive volume metrics.",
            "risk_flag": "NONE",
            "geie_still_valid": True
        }

    def generate_report(self, prompt: str, system_context: str = None) -> str:
        self._handle_failures()
        return "## Mock Gemini Report\n\nThis is a mock generated report summarizing trade attributes and scores."

    def generate_founder_summary(self, notes: str) -> str:
        self._handle_failures()
        return "Founder Summary: The founder shows trading discipline in following the trend but displays exit anxiety."

    def generate_trade_story(self, trade_events: List[Dict[str, Any]]) -> str:
        self._handle_failures()
        return "Chronological Trade Story: Position opened on bullish BOS, tracked via 15m candles, closed at Target 1."

    def generate_daily_narrative(self, session_date: str, metrics: Dict[str, Any]) -> str:
        self._handle_failures()
        return f"Daily narrative summary for {session_date}. Net R-multiple: +3.5R. Total trades: 4."

DefinitionClass = GeminiMock

