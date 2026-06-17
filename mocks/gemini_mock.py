import time
from typing import Dict, Any
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

    def analyze_news_impact(self, news_summary: str, fii_dii_trend: str, options_concentration: str) -> Dict[str, Any]:
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
DefinitionClass = GeminiMock
