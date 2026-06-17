import datetime
from decimal import Decimal

class FVGDetector:
    @staticmethod
    def detect_fvgs(candles: list[dict]) -> list[dict]:
        """Detects Fair Value Gaps (FVG) in the candle list.
        Uses a 3-candle window:
          - Bullish FVG: Candle i-1 is green, and Low[i] > High[i-2]
          - Bearish FVG: Candle i-1 is red, and High[i] < Low[i-2]
        """
        detected_fvgs = []
        n = len(candles)
        if n < 3:
            return detected_fvgs
            
        for i in range(2, n):
            low_curr = Decimal(str(candles[i]["low"]))
            high_curr = Decimal(str(candles[i]["high"]))
            
            low_prev2 = Decimal(str(candles[i-2]["low"]))
            high_prev2 = Decimal(str(candles[i-2]["high"]))
            
            close_prev1 = Decimal(str(candles[i-1]["close"]))
            open_prev1 = Decimal(str(candles[i-1]["open"]))
            
            # 1. Bullish FVG
            if close_prev1 > open_prev1 and low_curr > high_prev2:
                detected_fvgs.append({
                    "time": candles[i-1]["time"],
                    "structure_type": "FVG",
                    "direction": "BULLISH",
                    "top_price": low_curr,
                    "bottom_price": high_prev2
                })
                
            # 2. Bearish FVG
            elif close_prev1 < open_prev1 and high_curr < low_prev2:
                detected_fvgs.append({
                    "time": candles[i-1]["time"],
                    "structure_type": "FVG",
                    "direction": "BEARISH",
                    "top_price": low_prev2,
                    "bottom_price": high_curr
                })
                
        return detected_fvgs
