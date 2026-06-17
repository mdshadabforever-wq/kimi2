import datetime
from decimal import Decimal
from market_structure.bos_detector import find_swing_points

class CHOCHDetector:
    @staticmethod
    def detect_choch(candles: list[dict], initial_trend: str) -> tuple[list[dict], str]:
        """Detects Change of Character (CHOCH) which represents trend reversal.
          - Bullish CHOCH: Trend is BEARISH, and Close breaks the latest swing high.
                          Trend flips to BULLISH.
          - Bearish CHOCH: Trend is BULLISH, and Close breaks the latest swing low.
                          Trend flips to BEARISH.
        Returns: (detected_choch_list, final_trend_direction)
        """
        detected_choch = []
        trend = initial_trend
        n = len(candles)
        if n < 5:
            return detected_choch, trend
            
        swing_highs, swing_lows = find_swing_points(candles)
        
        triggered_highs = set()
        triggered_lows = set()
        
        for i in range(2, n):
            confirmed_highs = [sh for sh in swing_highs if sh["index"] + 2 <= i]
            confirmed_lows = [sl for sl in swing_lows if sl["index"] + 2 <= i]
            
            close_val = Decimal(str(candles[i]["close"]))
            
            if trend == "BEARISH" and confirmed_highs:
                latest_high = confirmed_highs[-1]
                high_key = (latest_high["time"], latest_high["price"])
                if close_val > latest_high["price"] and high_key not in triggered_highs:
                    detected_choch.append({
                        "time": candles[i]["time"],
                        "structure_type": "CHOCH",
                        "direction": "BULLISH",
                        "top_price": latest_high["price"],
                        "bottom_price": latest_high["price"],
                        "trigger_price": close_val
                    })
                    triggered_highs.add(high_key)
                    trend = "BULLISH"
                    
            elif trend == "BULLISH" and confirmed_lows:
                latest_low = confirmed_lows[-1]
                low_key = (latest_low["time"], latest_low["price"])
                if close_val < latest_low["price"] and low_key not in triggered_lows:
                    detected_choch.append({
                        "time": candles[i]["time"],
                        "structure_type": "CHOCH",
                        "direction": "BEARISH",
                        "top_price": latest_low["price"],
                        "bottom_price": latest_low["price"],
                        "trigger_price": close_val
                    })
                    triggered_lows.add(low_key)
                    trend = "BEARISH"
                    
        return detected_choch, trend
