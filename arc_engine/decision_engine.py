from typing import Dict, Any, Tuple, List


class ARCDecisionEngine:
    """Implements the deterministic LONG/SHORT/REJECT/CAUTION rules from Clarification 008.
    Claude's response is validated against these rules. Fallback decisions also use this engine.
    """

    # --- Engine Alignment Classification ---

    @staticmethod
    def classify_engine_alignment(
        bundle: Dict[str, Any],
        signal_direction: str
    ) -> Dict[str, str]:
        """Classifies each engine output as AGREE, PARTIAL, or DISAGREE
        relative to the signal direction (LONG or SHORT).
        Clarification 008, Section 8.1.
        """
        alignment = {}

        # Trend engine
        trend = bundle.get("trend_input", {})
        aligned_dir = trend.get("aligned_direction", "NEUTRAL")
        score = trend.get("alignment_score", 0)
        trend_match = (
            (signal_direction == "LONG" and aligned_dir == "BULLISH") or
            (signal_direction == "SHORT" and aligned_dir == "BEARISH")
        )
        if trend_match and score >= 75:
            alignment["trend"] = "AGREE"
        elif trend_match and score < 75:
            alignment["trend"] = "PARTIAL"
        else:
            alignment["trend"] = "DISAGREE"

        # SMC engine
        smc = bundle.get("smc_input", {})
        smc_dir = smc.get("direction", "NO_DIRECTION")
        ct_status = smc.get("cross_timeframe_status", "FAIL")
        smc_match = (smc_dir == signal_direction)
        if smc_match and ct_status == "PASS":
            alignment["smc"] = "AGREE"
        elif smc_match and ct_status != "PASS":
            alignment["smc"] = "PARTIAL"
        else:
            alignment["smc"] = "DISAGREE"

        # Options engine
        options = bundle.get("options_input", {})
        options_bias = options.get("bias", "NEUTRAL")
        pcr = float(options.get("pcr_oi", 1.0))
        if signal_direction == "LONG":
            if options_bias == "BULLISH" or pcr >= 1.0:
                alignment["options"] = "AGREE"
            elif options_bias == "BEARISH":
                alignment["options"] = "DISAGREE"
            else:
                alignment["options"] = "PARTIAL"
        else:  # SHORT
            if options_bias == "BEARISH" or pcr <= 1.0:
                alignment["options"] = "AGREE"
            elif options_bias == "BULLISH":
                alignment["options"] = "DISAGREE"
            else:
                alignment["options"] = "PARTIAL"

        # Scoring engine
        scoring = bundle.get("scoring_input", {})
        score_val = float(scoring.get("final_composite_score", 0))
        grade = scoring.get("risk_grade", "F")
        if score_val >= 90.0 and grade in ("A", "B"):
            alignment["scoring"] = "AGREE"
        elif score_val >= 86.0 and grade in ("A", "B", "C"):
            alignment["scoring"] = "PARTIAL"
        else:
            alignment["scoring"] = "DISAGREE"

        # Risk engine
        risk = bundle.get("risk_input", {})
        status_code = risk.get("status_code", "UNKNOWN")
        if status_code == "PASS":
            alignment["risk"] = "AGREE"
        elif status_code == "PREMARKET":
            alignment["risk"] = "PARTIAL"
        else:
            alignment["risk"] = "DISAGREE"

        # GEIE engine
        geie = bundle.get("geie_input", {})
        stock_impact = geie.get("stock_impact", {})
        geie_dir = stock_impact.get("direction", "NEUTRAL")
        geie_conf = stock_impact.get("confidence", "LOW")
        if signal_direction == "LONG":
            if geie_dir == "POSITIVE":
                alignment["geie"] = "AGREE"
            elif geie_dir == "NEGATIVE" and geie_conf == "HIGH":
                alignment["geie"] = "DISAGREE"
            else:
                alignment["geie"] = "PARTIAL"
        else:  # SHORT
            if geie_dir == "NEGATIVE":
                alignment["geie"] = "AGREE"
            elif geie_dir == "POSITIVE" and geie_conf == "HIGH":
                alignment["geie"] = "DISAGREE"
            else:
                alignment["geie"] = "PARTIAL"

        return alignment

    # --- REJECT Rules ---

    @staticmethod
    def evaluate_reject_rules(
        bundle: Dict[str, Any],
        signal_direction: str
    ) -> Tuple[bool, List[str]]:
        """Evaluates all 9 REJECT rules from Clarification 008, Section 7.
        Returns: (should_reject, list_of_reject_codes)
        """
        reject_codes = []

        trend = bundle.get("trend_input", {})
        smc = bundle.get("smc_input", {})
        geie = bundle.get("geie_input", {})
        scoring = bundle.get("scoring_input", {})
        risk = bundle.get("risk_input", {})

        aligned_dir = trend.get("aligned_direction", "NEUTRAL")
        smc_dir = smc.get("direction", "NO_DIRECTION")
        geie_status = geie.get("geie_status", "UNAVAILABLE")
        stock_impact = geie.get("stock_impact", {})
        geie_impact_dir = stock_impact.get("direction", "NEUTRAL")
        geie_conf = stock_impact.get("confidence", "LOW")
        market_sentiment = geie.get("market_sentiment", "NEUTRAL")
        score_val = float(scoring.get("final_composite_score", 0))
        hard_stop = risk.get("hard_stop_active", False)

        # R01: Trend contradicts SMC direction
        if signal_direction == "LONG":
            trend_expected = "BULLISH"
        else:
            trend_expected = "BEARISH"
        if aligned_dir not in ("NEUTRAL", trend_expected) and smc_dir == signal_direction:
            reject_codes.append(f"ARC_R01: Trend {aligned_dir} contradicts SMC {smc_dir}")

        # R02: GEIE HIGH NEGATIVE on LONG signal
        if signal_direction == "LONG" and geie_impact_dir == "NEGATIVE" and geie_conf == "HIGH":
            reject_codes.append("ARC_R02: GEIE HIGH confidence NEGATIVE contradicts LONG signal")

        # R03: GEIE HIGH POSITIVE on SHORT signal
        if signal_direction == "SHORT" and geie_impact_dir == "POSITIVE" and geie_conf == "HIGH":
            reject_codes.append("ARC_R03: GEIE HIGH confidence POSITIVE contradicts SHORT signal")

        # R04: Hard stop active
        if hard_stop:
            reject_codes.append("ARC_R04: hard_stop_active=True in risk state")

        # R05: Score below threshold
        if score_val < 86.0:
            reject_codes.append(f"ARC_R05: Composite score {score_val:.2f} below 86.0 threshold")

        # R06: SMC NO_DIRECTION
        if smc_dir == "NO_DIRECTION":
            reject_codes.append("ARC_R06: SMC returned NO_DIRECTION")

        # R07: No trend alignment AND weak SMC
        smc_score = float(smc.get("score", 0))
        is_aligned = trend.get("is_aligned", False)
        if not is_aligned and smc_score < 70:
            reject_codes.append("ARC_R07: No trend alignment and SMC quality score < 70")

        # R08: RISK_OFF market + LONG signal + HIGH GEIE confidence
        if (signal_direction == "LONG" and market_sentiment == "RISK_OFF" and geie_conf == "HIGH"):
            reject_codes.append("ARC_R08: Market sentiment RISK_OFF with LONG signal and HIGH GEIE confidence")

        # R09 is handled at the processor level (parse failure)

        return len(reject_codes) > 0, reject_codes

    # --- Conflict Resolution Matrix ---

    @staticmethod
    def resolve_from_alignment(
        alignment: Dict[str, str],
        reject_codes: List[str]
    ) -> Tuple[str, List[str]]:
        """Applies the conflict resolution matrix from Clarification 008, Section 8.2.
        Returns: (arc_decision, conflict_flags)
        """
        if reject_codes:
            return "REJECT", [f"Reject rule triggered: {r}" for r in reject_codes]

        agree_count = sum(1 for v in alignment.values() if v == "AGREE")
        disagree_count = sum(1 for v in alignment.values() if v == "DISAGREE")
        conflict_flags = [f"{k}=DISAGREE" for k, v in alignment.items() if v == "DISAGREE"]

        if agree_count == 6:
            return "APPROVE", []
        elif agree_count == 5 and disagree_count == 0:
            return "APPROVE", []
        elif agree_count == 5 and disagree_count == 1:
            return "APPROVE", conflict_flags
        elif agree_count == 4 and disagree_count <= 1:
            return "CAUTION", conflict_flags
        elif agree_count == 4 and disagree_count == 2:
            return "CAUTION", conflict_flags
        elif agree_count >= 3 and disagree_count >= 2:
            return "REJECT", conflict_flags
        else:
            return "REJECT", conflict_flags

    # --- Fallback Decision (no Claude available) ---

    @staticmethod
    def build_fallback_decision(
        signal_id: str,
        symbol: str,
        bundle: Dict[str, Any],
        signal_direction: str,
        fallback_reason: str
    ) -> Dict[str, Any]:
        """Builds a fallback ARC decision when Claude is unavailable.
        Fallback never issues APPROVE. Max result is CAUTION.
        Clarification 008, Section 15.2.
        """
        import datetime
        from arc_engine.confidence_calculator import ARCConfidenceCalculator

        scoring = bundle.get("scoring_input", {})
        score_val = float(scoring.get("final_composite_score", 0))

        alignment = ARCDecisionEngine.classify_engine_alignment(bundle, signal_direction)
        agree_count = sum(1 for v in alignment.values() if v == "AGREE")

        # Fallback decision rules
        if score_val >= 90.0 and agree_count >= 5:
            arc_decision = "CAUTION"
            arc_confidence = min(100, max(0, 60))
            reasoning = f"ARC_FALLBACK: {fallback_reason}. Score >= 90, engines aligned. CAUTION applied."
        elif score_val >= 86.0 and agree_count >= 4:
            arc_decision = "CAUTION"
            arc_confidence = min(100, max(0, 40))
            reasoning = f"ARC_FALLBACK: {fallback_reason}. Score >= 86, partial alignment. CAUTION applied."
        else:
            arc_decision = "REJECT"
            arc_confidence = 0
            reasoning = f"ARC_FALLBACK: {fallback_reason}. Insufficient confidence to approve without AI review."

        return {
            "$schema": "iiis-arc-decision-v1",
            "signal_id": signal_id,
            "symbol": symbol,
            "arc_decision": arc_decision,
            "arc_confidence": arc_confidence,
            "reasoning_summary": reasoning,
            "engine_alignment": alignment,
            "conflict_flags": [],
            "reject_reasons": [] if arc_decision != "REJECT" else [reasoning],
            "caution_reasons": [reasoning] if arc_decision == "CAUTION" else [],
            "explainability": {
                "bullish_factors": [],
                "bearish_factors": [],
                "neutral_factors": [reasoning]
            },
            "arc_timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "arc_version": "1.0"
        }

    # --- Cutoff Decision ---

    @staticmethod
    def build_cutoff_decision(signal_id: str, symbol: str) -> Dict[str, Any]:
        """Builds the 08:50 AM cutoff CAUTION decision.
        Clarification 008, Section 16.2.
        """
        import datetime
        return {
            "$schema": "iiis-arc-decision-v1",
            "signal_id": signal_id,
            "symbol": symbol,
            "arc_decision": "CAUTION",
            "arc_confidence": 30,
            "reasoning_summary": "ARC_CUTOFF: 08:50 AM cutoff reached. Symbol not reviewed before market open.",
            "engine_alignment": {k: "PARTIAL" for k in ["trend", "smc", "options", "scoring", "risk", "geie"]},
            "conflict_flags": [],
            "reject_reasons": [],
            "caution_reasons": ["ARC_CUTOFF: 08:50 AM hard cutoff applied"],
            "explainability": {
                "bullish_factors": [],
                "bearish_factors": [],
                "neutral_factors": ["ARC_CUTOFF: Premarket review window expired before this symbol was processed"]
            },
            "arc_timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "arc_version": "1.0"
        }
