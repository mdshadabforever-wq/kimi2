import json
import time
import datetime
from typing import List, Dict, Any
from interfaces.claude import ClaudeInterface


class ClaudeMock(ClaudeInterface):
    """Mock Claude implementation for testing. Supports ARC decision simulation."""

    def __init__(self):
        self.simulate_error = False
        self.simulate_timeout = False
        self.consecutive_failures = 0

    def _handle_failures(self):
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated Claude API Error")
        if self.simulate_timeout:
            self.consecutive_failures += 1
            raise TimeoutError("Simulated Claude API Timeout")
        self.consecutive_failures = 0

    def review_watchlist_premarket(self, watchlist: List[str], context: Dict[str, Any]) -> Dict[str, str]:
        self._handle_failures()
        decisions = {}
        for symbol in watchlist:
            if symbol == "RELIANCE":
                decisions[symbol] = "CAUTION"
            elif symbol == "WIPRO":
                decisions[symbol] = "REJECT"
            else:
                decisions[symbol] = "APPROVE"
        return decisions

    def review_symbol(self, signal_id: str, arc_input_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Returns a mock ARC decision JSON. Simulates APPROVE for most signals,
        CAUTION for RELIANCE, REJECT for WIPRO (mirrors premarket behavior for test consistency).
        """
        self._handle_failures()

        symbol = arc_input_bundle.get("symbol", "UNKNOWN")
        scoring = arc_input_bundle.get("scoring_input", {})
        composite_score = float(scoring.get("final_composite_score", 90.0))
        geie = arc_input_bundle.get("geie_input", {})
        geie_direction = geie.get("stock_impact", {}).get("direction", "NEUTRAL")
        geie_confidence = geie.get("stock_impact", {}).get("confidence", "LOW")
        smc = arc_input_bundle.get("smc_input", {})
        smc_direction = smc.get("direction", "LONG")
        trend = arc_input_bundle.get("trend_input", {})
        aligned_direction = trend.get("aligned_direction", "BULLISH")

        # Determine decision based on mock rules
        arc_decision = "APPROVE"
        arc_confidence = 85
        reject_reasons = []
        caution_reasons = []
        conflict_flags = []

        if symbol == "WIPRO":
            arc_decision = "REJECT"
            arc_confidence = 10
            reject_reasons = ["ARC_R01: Test symbol WIPRO always rejected in mock mode"]
        elif symbol == "RELIANCE":
            arc_decision = "CAUTION"
            arc_confidence = 55
            caution_reasons = ["Mock: RELIANCE designated as CAUTION for test coverage"]
        elif geie_direction == "NEGATIVE" and geie_confidence == "HIGH" and smc_direction == "LONG":
            arc_decision = "REJECT"
            arc_confidence = 5
            reject_reasons = ["ARC_R02: GEIE HIGH confidence NEGATIVE contradicts LONG signal"]
        elif geie_direction == "POSITIVE" and geie_confidence == "HIGH" and smc_direction == "SHORT":
            arc_decision = "REJECT"
            arc_confidence = 5
            reject_reasons = ["ARC_R03: GEIE HIGH confidence POSITIVE contradicts SHORT signal"]
        elif composite_score < 86.0:
            arc_decision = "REJECT"
            arc_confidence = 0
            reject_reasons = ["ARC_R05: Composite score below 86.0 threshold"]
        elif smc_direction == "NO_DIRECTION":
            arc_decision = "REJECT"
            arc_confidence = 0
            reject_reasons = ["ARC_R06: SMC returned NO_DIRECTION"]
        elif (smc_direction == "LONG" and aligned_direction == "BEARISH") or \
             (smc_direction == "SHORT" and aligned_direction == "BULLISH"):
            arc_decision = "REJECT"
            arc_confidence = 0
            reject_reasons = ["ARC_R01: Trend direction contradicts SMC direction"]
            conflict_flags = [f"Trend={aligned_direction}, SMC={smc_direction}"]

        engine_alignment = {
            "trend": "AGREE" if arc_decision != "REJECT" else "DISAGREE",
            "smc": "AGREE" if arc_decision != "REJECT" else "DISAGREE",
            "options": "AGREE",
            "scoring": "AGREE",
            "risk": "AGREE",
            "geie": "DISAGREE" if geie_direction == "NEGATIVE" and arc_decision == "REJECT" else "AGREE"
        }

        return {
            "$schema": "iiis-arc-decision-v1",
            "signal_id": signal_id,
            "symbol": symbol,
            "arc_decision": arc_decision,
            "arc_confidence": arc_confidence,
            "reasoning_summary": f"Mock ARC decision for {symbol}: {arc_decision}",
            "engine_alignment": engine_alignment,
            "conflict_flags": conflict_flags,
            "reject_reasons": reject_reasons,
            "caution_reasons": caution_reasons,
            "explainability": {
                "bullish_factors": ["Mock positive factor 1"] if arc_decision == "APPROVE" else [],
                "bearish_factors": reject_reasons,
                "neutral_factors": caution_reasons
            },
            "arc_timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "arc_version": "1.0"
        }

    def review_signals_postmarket(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        self._handle_failures()
        return {
            "status": "SUCCESS",
            "reviewed_count": len(signals),
            "next_day_watchlist_additions": ["TATASTEEL", "HDFCBANK"]
        }



DefinitionClass = ClaudeMock
