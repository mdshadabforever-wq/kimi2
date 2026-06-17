import datetime
from decimal import Decimal
import database

class RiskPersistence:
    @staticmethod
    def load_risk_state(session_date: datetime.date) -> dict:
        """Loads risk state from database for a given date."""
        query = """
            SELECT daily_risk_used, consecutive_losses, hard_stop_active, total_signals,
                   signals_hit_sl, signals_hit_t1, signals_hit_t2
            FROM risk_state
            WHERE session_date = %s;
        """
        try:
            res = database.execute_query(query, (session_date,), fetch=True)
            if res:
                row = res[0]
                return {
                    "session_date": session_date,
                    "daily_risk_used": Decimal(str(row[0])),
                    "consecutive_losses": int(row[1]),
                    "hard_stop_active": bool(row[2]),
                    "total_signals": int(row[3]),
                    "signals_hit_sl": int(row[4]),
                    "signals_hit_t1": int(row[5]),
                    "signals_hit_t2": int(row[6])
                }
        except Exception as e:
            print(f"[RISK PERSISTENCE] Error loading risk state for {session_date}: {e}")
        return None

    @staticmethod
    def save_risk_state(
        session_date: datetime.date,
        daily_risk_used: Decimal,
        consecutive_losses: int,
        hard_stop_active: bool,
        total_signals: int = 0,
        signals_hit_sl: int = 0,
        signals_hit_t1: int = 0,
        signals_hit_t2: int = 0
    ):
        """Saves or updates risk state in database for a date."""
        query = """
            INSERT INTO risk_state (
                session_date, daily_risk_used, consecutive_losses, hard_stop_active, 
                total_signals, signals_hit_sl, signals_hit_t1, signals_hit_t2
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_date)
            DO UPDATE SET
                daily_risk_used = EXCLUDED.daily_risk_used,
                consecutive_losses = EXCLUDED.consecutive_losses,
                hard_stop_active = EXCLUDED.hard_stop_active,
                total_signals = EXCLUDED.total_signals,
                signals_hit_sl = EXCLUDED.signals_hit_sl,
                signals_hit_t1 = EXCLUDED.signals_hit_t1,
                signals_hit_t2 = EXCLUDED.signals_hit_t2,
                updated_at = NOW();
        """
        try:
            database.execute_query(query, (
                session_date, daily_risk_used, consecutive_losses, hard_stop_active,
                total_signals, signals_hit_sl, signals_hit_t1, signals_hit_t2
            ))
        except Exception as e:
            print(f"[RISK PERSISTENCE] Error saving risk state: {e}")

    @staticmethod
    def save_signal(
        signal_id: str,
        timestamp: datetime.datetime,
        symbol: str,
        direction: str,
        score: Decimal,
        confidence: str,
        regime: str,
        entry_low: Decimal,
        entry_high: Decimal,
        stop_loss: Decimal,
        target_1: Decimal,
        target_2: Decimal,
        quantity: int,
        risk_amount: Decimal,
        risk_grade: str,
        valid_until: datetime.datetime,
        status: str = 'ACTIVE'
    ):
        """Saves a signal generated and validated by the risk engine."""
        query = """
            INSERT INTO signals (
                signal_id, timestamp, symbol, direction, score, confidence, regime, 
                entry_low, entry_high, stop_loss, target_1, target_2, quantity, 
                risk_amount, risk_grade, valid_until, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (signal_id) DO NOTHING;
        """
        try:
            database.execute_query(query, (
                signal_id, timestamp, symbol, direction, score, confidence, regime,
                entry_low, entry_high, stop_loss, target_1, target_2, quantity,
                risk_amount, risk_grade, valid_until, status
            ))
        except Exception as e:
            print(f"[RISK PERSISTENCE] Error saving signal {signal_id}: {e}")

    @staticmethod
    def has_active_signal(symbol: str, now: datetime.datetime = None) -> bool:
        """Checks if there is a duplicate active signal in signals table."""
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)
            
        query = """
            SELECT count(*) FROM signals
            WHERE symbol = %s AND status = 'ACTIVE' AND valid_until > %s;
        """
        try:
            res = database.execute_query(query, (symbol, now), fetch=True)
            return res[0][0] > 0 if res else False
        except Exception as e:
            print(f"[RISK PERSISTENCE] Error checking active signal: {e}")
        return False
