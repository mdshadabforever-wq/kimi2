import datetime
from decimal import Decimal

def find_swing_points(candles: list[dict]) -> tuple[list[dict], list[dict]]:
    """Finds Swing Highs and Swing Lows using a 5-bar lookback.
    A swing high is confirmed at index i when we have candles up to i+2, 
    so it is confirmed at t+2 where t is the swing high time.
    """
    swing_highs = []
    swing_lows = []
    
    n = len(candles)
    if n < 5:
        return swing_highs, swing_lows
        
    for i in range(2, n - 2):
        highs = [Decimal(str(candles[j]["high"])) for j in range(i - 2, i + 3)]
        lows = [Decimal(str(candles[j]["low"])) for j in range(i - 2, i + 3)]
        
        center_high = Decimal(str(candles[i]["high"]))
        center_low = Decimal(str(candles[i]["low"]))
        
        # Center must be local peak
        if center_high == max(highs):
            swing_highs.append({
                "time": candles[i]["time"],
                "price": center_high,
                "index": i
            })
            
        if center_low == min(lows):
            swing_lows.append({
                "time": candles[i]["time"],
                "price": center_low,
                "index": i
            })
            
    return swing_highs, swing_lows

class BOSDetector:
    @staticmethod
    def detect_bos(candles: list[dict], current_trend: str) -> list[dict]:
        """Detects Break of Structure (BOS) in the chronological candles.
        BOS represents trend continuation:
          - Bullish BOS: Close breaks swing high when trend is BULLISH
          - Bearish BOS: Close breaks swing low when trend is BEARISH
        """
        detected_bos = []
        n = len(candles)
        if n < 5:
            return detected_bos
            
        swing_highs, swing_lows = find_swing_points(candles)
        
        # We track which swing high/low has already caused a BOS to avoid duplicates
        triggered_highs = set()
        triggered_lows = set()
        
        for i in range(2, n):
            # A swing point is confirmed if its center index + 2 <= i
            confirmed_highs = [sh for sh in swing_highs if sh["index"] + 2 <= i]
            confirmed_lows = [sl for sl in swing_lows if sl["index"] + 2 <= i]
            
            close_val = Decimal(str(candles[i]["close"]))
            
            if current_trend == "BULLISH" and confirmed_highs:
                latest_high = confirmed_highs[-1]
                high_key = (latest_high["time"], latest_high["price"])
                if close_val > latest_high["price"] and high_key not in triggered_highs:
                    detected_bos.append({
                        "time": candles[i]["time"],
                        "structure_type": "BOS",
                        "direction": "BULLISH",
                        "top_price": latest_high["price"],
                        "bottom_price": latest_high["price"],
                        "trigger_price": close_val
                    })
                    triggered_highs.add(high_key)
                    
            elif current_trend == "BEARISH" and confirmed_lows:
                latest_low = confirmed_lows[-1]
                low_key = (latest_low["time"], latest_low["price"])
                if close_val < latest_low["price"] and low_key not in triggered_lows:
                    detected_bos.append({
                        "time": candles[i]["time"],
                        "structure_type": "BOS",
                        "direction": "BEARISH",
                        "top_price": latest_low["price"],
                        "bottom_price": latest_low["price"],
                        "trigger_price": close_val
                    })
                    triggered_lows.add(low_key)
                    
        return detected_bos
