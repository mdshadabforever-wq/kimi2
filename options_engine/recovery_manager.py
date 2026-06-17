from options_engine.persistence import OptionsPersistence

class OptionsRecoveryManager:
    @staticmethod
    def recover_state(symbol: str) -> dict:
        """Restores latest options intelligence stats from the database for restart recovery."""
        latest = OptionsPersistence.load_latest_intelligence(symbol)
        if latest:
            return {
                "max_pain_level": latest["max_pain_level"],
                "highest_put_oi_strike": latest["highest_put_oi_strike"],
                "highest_call_oi_strike": latest["highest_call_oi_strike"],
                "recovered_date": latest["date"],
                "status": "RECOVERED"
            }
        return {
            "max_pain_level": None,
            "highest_put_oi_strike": None,
            "highest_call_oi_strike": None,
            "recovered_date": None,
            "status": "NEW"
        }
