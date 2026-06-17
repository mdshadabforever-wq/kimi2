import datetime
from decimal import Decimal
import database

class TrendPersistence:
    @staticmethod
    def save_trend_state(boundary_time: datetime.datetime, symbol: str, timeframe: str, trend: str, ema_20: Decimal, close: Decimal):
        """Saves or updates a calculated trend state in the database."""
        query = """
            INSERT INTO trend_states (time, symbol, timeframe, trend, ema_20, close)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, symbol, timeframe)
            DO UPDATE SET
                trend = EXCLUDED.trend,
                ema_20 = EXCLUDED.ema_20,
                close = EXCLUDED.close;
        """
        try:
            database.execute_query(query, (boundary_time, symbol, timeframe, trend, ema_20, close))
        except Exception as e:
            print(f"[TREND PERSISTENCE] Database write error: {e}")

    @staticmethod
    def save_trend_states_bulk(states: list[tuple]):
        """Saves trend states in bulk for high performance."""
        if not states:
            return
        chunk_size = 500
        for idx in range(0, len(states), chunk_size):
            chunk = states[idx:idx + chunk_size]
            placeholders = ",".join(["(%s, %s, %s, %s, %s, %s)"] * len(chunk))
            query = f"""
                INSERT INTO trend_states (time, symbol, timeframe, trend, ema_20, close)
                VALUES {placeholders}
                ON CONFLICT (time, symbol, timeframe)
                DO UPDATE SET
                    trend = EXCLUDED.trend,
                    ema_20 = EXCLUDED.ema_20,
                    close = EXCLUDED.close;
            """
            flat_args = []
            for r in chunk:
                flat_args.extend(r)
            try:
                database.execute_query(query, tuple(flat_args))
            except Exception as e:
                print(f"[TREND PERSISTENCE] Bulk write error: {e}")

    @staticmethod
    def load_trend_state(symbol: str, timeframe: str, boundary_time: datetime.datetime) -> dict:
        """Loads a specific trend state from the database."""
        query = """
            SELECT trend, ema_20, close FROM trend_states
            WHERE symbol = %s AND timeframe = %s AND time = %s;
        """
        try:
            res = database.execute_query(query, (symbol, timeframe, boundary_time), fetch=True)
            if res:
                row = res[0]
                return {
                    "trend": row[0],
                    "ema_20": Decimal(str(row[1])),
                    "close": Decimal(str(row[2]))
                }
        except Exception as e:
            print(f"[TREND PERSISTENCE] Database read error: {e}")
        return None

    @staticmethod
    def load_latest_trend_states(symbol: str) -> dict[str, dict]:
        """Loads the latest trend states across all timeframes for a symbol.
        Used to restore in-memory state after a process restart.
        """
        query = """
            SELECT DISTINCT ON (timeframe) timeframe, time, trend, ema_20, close
            FROM trend_states
            WHERE symbol = %s
            ORDER BY timeframe, time DESC;
        """
        states = {}
        try:
            res = database.execute_query(query, (symbol,), fetch=True)
            for row in res:
                tf, t_time, trend, ema_val, close_val = row
                states[tf] = {
                    "time": t_time,
                    "trend": trend,
                    "ema_20": Decimal(str(ema_val)),
                    "close": Decimal(str(close_val))
                }
        except Exception as e:
            print(f"[TREND PERSISTENCE] Database query latest trend error: {e}")
        return states
