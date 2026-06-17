from typing import Dict, Any

class ARCConfidenceCalculator:
    """Implements Step 13 - Algorithmic Confidence Filter from the frozen specification.
    Calculates confidence (HIGH, MEDIUM, LOW) based on composite score, GEIE direction, and historical win rate.
    """

    @staticmethod
    def calculate(score: float, geie_direction: str, win_rate: float) -> str:
        """Determines the algorithmic confidence level (HIGH/MEDIUM/LOW).

        Args:
            score: Composite score.
            geie_direction: GEIE impact direction (POSITIVE/NEGATIVE/NEUTRAL/UNAVAILABLE).
            win_rate: Historical win rate (as percentage, e.g. 55.0, or decimal, e.g. 0.55).

        Returns:
            Confidence string label ('HIGH', 'MEDIUM', 'LOW').
        """
        score = float(score)
        win_rate = float(win_rate)

        # Normalize win_rate to percentage format (e.g. 0.65 -> 65.0)
        if win_rate < 1.0:
            win_rate = win_rate * 100.0

        # 1. HIGH confidence when:
        # - Score above 92
        # - AND GEIE direction POSITIVE
        # - AND Historical win rate above 60%
        if score > 92.0 and geie_direction == "POSITIVE" and win_rate > 60.0:
            return "HIGH"

        # 2. MEDIUM confidence when:
        # - Score 88 to 92
        # - AND GEIE direction POSITIVE or NEUTRAL
        # - AND Historical win rate 50% to 60%
        if (88.0 <= score <= 92.0) and (geie_direction in ("POSITIVE", "NEUTRAL")) and (50.0 <= win_rate <= 60.0):
            return "MEDIUM"

        # 3. LOW confidence when:
        # - Score 86 to 88
        # - AND GEIE direction NEUTRAL
        # - AND Historical win rate below 50%
        # - Or default fallback when other criteria aren't met
        return "LOW"

    @staticmethod
    def from_bundle(bundle: Dict[str, Any]) -> str:
        """Calculates confidence string label from the ARC input bundle."""
        scoring = bundle.get("scoring_input", {})
        score = float(scoring.get("final_composite_score", 0.0))

        geie_input = bundle.get("geie_input", {})
        stock_impact = geie_input.get("stock_impact", {})
        geie_direction = stock_impact.get("direction", "NEUTRAL")

        # Try to extract win rate from different possible locations in the bundle
        win_rate = 0.0
        if "historical_win_rate" in bundle:
            win_rate = float(bundle["historical_win_rate"])
        elif "historical_wr" in bundle:
            win_rate = float(bundle["historical_wr"])
        elif "historical_win_rate" in scoring:
            win_rate = float(scoring["historical_win_rate"])
        elif "historical_wr" in scoring:
            win_rate = float(scoring["historical_wr"])
        else:
            # Fallback to database query if signal_id is present
            signal_id = bundle.get("signal_id")
            if signal_id:
                import database
                try:
                    res = database.execute_query(
                        "SELECT historical_wr FROM signals WHERE signal_id = %s;",
                        (signal_id,),
                        fetch=True
                    )
                    if res and res[0][0] is not None:
                        win_rate = float(res[0][0])
                except Exception:
                    pass

        # Default fallback to 55.0% if still zero/not found
        if win_rate == 0.0:
            win_rate = 55.0

        return ARCConfidenceCalculator.calculate(score, geie_direction, win_rate)
