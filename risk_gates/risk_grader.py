from decimal import Decimal

class RiskGrader:
    """Implements Section 15 of the frozen specification: RISK GRADE DEFINITIONS
    Determines final risk grade (A+, A, B+, B, C, F) based on composite score,
    caution flags, and Big Money upgrades.
    """

    @staticmethod
    def get_grade(score: Decimal, has_caution: bool = False, big_money_score: float = 0.0) -> str:
        """Assigns the final risk grade.

        Args:
            score: Composite score.
            has_caution: True if the alert is tagged with a CAUTION flag.
            big_money_score: Big Money Confluence Score (0 to 100).

        Returns:
            Risk grade string ('A+', 'A', 'B+', 'B', 'C', 'F').
        """
        score_val = float(score)

        # Grade C: Any score, tagged with CAUTION flag
        if has_caution:
            return "C"

        # Determine base grade
        if score_val >= 95.0:
            base_grade = "A+"
        elif score_val >= 90.0:
            base_grade = "A"
        elif score_val >= 87.0:
            base_grade = "B+"
        elif score_val >= 86.0:
            base_grade = "B"
        else:
            return "F"  # score < 86 is rejected

        # Big Money Upgrade Rules (Confluence Score >= 80 upgrades grade by +1 notch)
        if big_money_score >= 80.0:
            if base_grade == "B":
                return "B+"
            elif base_grade == "B+":
                return "A"
            elif base_grade == "A":
                return "A+"

        return base_grade
