import datetime
from scoring_engine.persistence import ScoringPersistence

class ScoreAuditor:
    @staticmethod
    def rebuild_score(symbol: str, timestamp: datetime.datetime) -> dict:
        """Historically reconstructs the exact component sub-scores and composite score for a symbol and timestamp.
        
        Returns:
            A dictionary of all sub-scores, the final composite score, and a validation flag.
        """
        audit = ScoringPersistence.load_audit(symbol, timestamp)
        if audit:
            # Re-verify calculation to verify integrity
            expected_score = (
                audit["regime_score"] * 15 +
                audit["rs_score"] * 10 +
                audit["rvol_score"] * 10 +
                audit["breadth_score"] * 10 +
                audit["sector_score"] * 10 +
                audit["trend_score"] * 15 +
                audit["smc_score"] * 15 +
                audit["options_score"] * 15
            ) / 100
            
            # Allow minor rounding epsilon
            is_valid = abs(expected_score - audit["final_composite_score"]) < 0.1
            
            return {
                "audit_record": audit,
                "reverified": is_valid,
                "status": "PASS" if is_valid else "FAIL"
            }
        return None
