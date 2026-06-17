import datetime
from decimal import Decimal
import database

class OptionChainLoader:
    @staticmethod
    def get_expiries(symbol: str) -> list[datetime.date]:
        """Gets all distinct expiry dates available in the database for the given symbol."""
        query = """
            SELECT DISTINCT expiry FROM options_data
            WHERE symbol = %s
            ORDER BY expiry ASC;
        """
        expiries = []
        try:
            res = database.execute_query(query, (symbol,), fetch=True)
            for row in res:
                expiries.append(row[0])
        except Exception as e:
            print(f"[OPTION CHAIN LOADER] Error fetching expiries for {symbol}: {e}")
        return expiries

    @staticmethod
    def load_chain(symbol: str, expiry: datetime.date, as_of_time: datetime.datetime) -> list[dict]:
        """Loads the option chain for a symbol, expiry, and timestamp."""
        time_query = """
            SELECT MAX(time) FROM options_data
            WHERE symbol = %s AND expiry = %s AND time <= %s;
        """
        chain = []
        try:
            res_time = database.execute_query(time_query, (symbol, expiry, as_of_time), fetch=True)
            if not res_time or not res_time[0][0]:
                return []
            target_time = res_time[0][0]
            
            query = """
                SELECT time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp
                FROM options_data
                WHERE symbol = %s AND expiry = %s AND time = %s
                ORDER BY strike ASC;
            """
            res = database.execute_query(query, (symbol, expiry, target_time), fetch=True)
            for row in res:
                chain.append({
                    "time": row[0],
                    "symbol": row[1],
                    "strike": Decimal(str(row[2])),
                    "expiry": row[3],
                    "option_type": row[4],
                    "oi": int(row[5]) if row[5] is not None else 0,
                    "oi_change": int(row[6]) if row[6] is not None else 0,
                    "volume": int(row[7]) if row[7] is not None else 0,
                    "iv": Decimal(str(row[8])) if row[8] is not None else Decimal("0"),
                    "ltp": Decimal(str(row[9])) if row[9] is not None else Decimal("0")
                })
        except Exception as e:
            print(f"[OPTION CHAIN LOADER] Error loading chain for {symbol} at {as_of_time}: {e}")
        return chain
