from decimal import Decimal
import datetime
import database

class MarketRegimeScorer:
    @staticmethod
    def calculate_score(symbol: str, as_of_time: datetime.datetime) -> Decimal:
        """Fetches the latest market regime from regime_history and scores it.
        Trending/Bullish -> 100
        Ranging/Neutral -> 50
        Volatile/Bearish -> 0
        """
        query = """
            SELECT regime FROM regime_history
            WHERE timestamp <= %s
            ORDER BY timestamp DESC LIMIT 1;
        """
        try:
            res = database.execute_query(query, (as_of_time,), fetch=True)
            if res:
                regime = res[0][0].upper()
                if "BULLISH" in regime or "TRENDING" in regime:
                    return Decimal("100.0")
                elif "BEARISH" in regime or "VOLATILE" in regime:
                    return Decimal("0.0")
        except Exception as e:
            print(f"[REGIME SCORER] Error fetching regime: {e}")
            
        return Decimal("50.0") # Neutral fallback
