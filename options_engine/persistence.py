import datetime
from decimal import Decimal
import database

class OptionsPersistence:
    @staticmethod
    def save_intelligence(
        date: datetime.date,
        symbol: str,
        max_pain: Decimal,
        highest_put_strike: Decimal,
        highest_call_strike: Decimal,
        unusual_activity: bool = False,
        unusual_strike: Decimal = None,
        unusual_type: str = None,
        unusual_oi_change: int = None
    ):
        """Saves or updates options intelligence data in options_intelligence table."""
        query = """
            INSERT INTO options_intelligence (
                date, symbol, max_pain_level, highest_put_oi_strike, highest_call_oi_strike, 
                unusual_activity_detected, unusual_strike, unusual_type, unusual_oi_change
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, symbol)
            DO UPDATE SET
                max_pain_level = EXCLUDED.max_pain_level,
                highest_put_oi_strike = EXCLUDED.highest_put_oi_strike,
                highest_call_oi_strike = EXCLUDED.highest_call_oi_strike,
                unusual_activity_detected = EXCLUDED.unusual_activity_detected,
                unusual_strike = EXCLUDED.unusual_strike,
                unusual_type = EXCLUDED.unusual_type,
                unusual_oi_change = EXCLUDED.unusual_oi_change;
        """
        try:
            database.execute_query(query, (
                date, symbol, max_pain, highest_put_strike, highest_call_strike,
                unusual_activity, unusual_strike, unusual_type, unusual_oi_change
            ))
        except Exception as e:
            print(f"[OPTIONS PERSISTENCE] Error saving options intelligence for {symbol}: {e}")

    @staticmethod
    def load_latest_intelligence(symbol: str) -> dict:
        """Loads the most recent options intelligence data for a symbol."""
        query = """
            SELECT date, max_pain_level, highest_put_oi_strike, highest_call_oi_strike,
                   unusual_activity_detected, unusual_strike, unusual_type, unusual_oi_change
            FROM options_intelligence
            WHERE symbol = %s
            ORDER BY date DESC LIMIT 1;
        """
        try:
            res = database.execute_query(query, (symbol,), fetch=True)
            if res:
                row = res[0]
                return {
                    "date": row[0],
                    "max_pain_level": Decimal(str(row[1])),
                    "highest_put_oi_strike": Decimal(str(row[2])),
                    "highest_call_oi_strike": Decimal(str(row[3])),
                    "unusual_activity_detected": row[4],
                    "unusual_strike": Decimal(str(row[5])) if row[5] is not None else None,
                    "unusual_type": row[6],
                    "unusual_oi_change": int(row[7]) if row[7] is not None else None
                }
        except Exception as e:
            print(f"[OPTIONS PERSISTENCE] Error loading latest intelligence for {symbol}: {e}")
        return None
