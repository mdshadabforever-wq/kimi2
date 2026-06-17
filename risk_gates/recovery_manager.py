import datetime
from decimal import Decimal
from risk_gates.persistence import RiskPersistence

class RiskRecoveryManager:
    @staticmethod
    def recover_risk_state(session_date: datetime.date) -> dict:
        """Restores risk state from database or initializes a new one if not present."""
        state = RiskPersistence.load_risk_state(session_date)
        if state:
            return state
            
        # Initialize new state for today
        clean_state = {
            "session_date": session_date,
            "daily_risk_used": Decimal("0.0"),
            "consecutive_losses": 0,
            "hard_stop_active": False,
            "total_signals": 0,
            "signals_hit_sl": 0,
            "signals_hit_t1": 0,
            "signals_hit_t2": 0
        }
        RiskPersistence.save_risk_state(
            session_date=session_date,
            daily_risk_used=clean_state["daily_risk_used"],
            consecutive_losses=clean_state["consecutive_losses"],
            hard_stop_active=clean_state["hard_stop_active"]
        )
        return clean_state
