from decimal import Decimal
import datetime
import database

class MarketBreadthScorer:
    @staticmethod
    def calculate_score(as_of_time: datetime.datetime, timeframe: str = "15m") -> Decimal:
        """Calculates market breadth: percentage of constituents that are BULLISH in trend_states."""
        query_latest_time = """
            SELECT max(time) FROM trend_states
            WHERE time <= %s AND timeframe = %s;
        """
        try:
            res_time = database.execute_query(query_latest_time, (as_of_time, timeframe), fetch=True)
            if res_time and res_time[0][0] is not None:
                latest_time = res_time[0][0]
                
                query_counts = """
                    SELECT 
                        count(*) filter (where trend = 'BULLISH') as bullish,
                        count(*) as total
                    FROM trend_states
                    WHERE time = %s AND timeframe = %s;
                """
                res_counts = database.execute_query(query_counts, (latest_time, timeframe), fetch=True)
                if res_counts and res_counts[0][1] > 0:
                    bullish = res_counts[0][0]
                    total = res_counts[0][1]
                    breadth_pct = (float(bullish) / float(total)) * 100.0
                    return Decimal(str(round(breadth_pct, 2)))
        except Exception as e:
            print(f"[BREADTH SCORER] Error calculating market breadth: {e}")
            
        return Decimal("60.0") # Standard default bullish market breadth
