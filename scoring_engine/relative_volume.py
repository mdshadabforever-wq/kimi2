from decimal import Decimal
import datetime
import database

class RelativeVolumeScorer:
    @staticmethod
    def calculate_score(symbol: str, as_of_time: datetime.datetime, timeframe: str = "15m") -> Decimal:
        """Calculates RVOL = Volume / SMA_20(Volume) and maps to score.
        RVOL >= 1.5 -> 100.0
        1.0 <= RVOL < 1.5 -> 70.0
        RVOL < 1.0 -> 40.0
        """
        query = """
            SELECT volume FROM market_data
            WHERE symbol = %s AND timeframe = %s AND time <= %s
            ORDER BY time DESC LIMIT 20;
        """
        try:
            rows = database.execute_query(query, (symbol, timeframe, as_of_time), fetch=True)
            if rows:
                latest_volume = int(rows[0][0])
                # Compute average volume of last 20 periods
                volumes = [int(r[0]) for r in rows]
                avg_volume = sum(volumes) / len(volumes)
                
                if avg_volume > 0:
                    rvol = float(latest_volume) / float(avg_volume)
                    if rvol >= 1.5:
                        return Decimal("100.0")
                    elif rvol >= 1.0:
                        return Decimal("70.0")
                    else:
                        return Decimal("40.0")
        except Exception as e:
            print(f"[RVOL SCORER] Error calculating relative volume for {symbol}: {e}")
            
        return Decimal("40.0") # Fallback to low volume score
