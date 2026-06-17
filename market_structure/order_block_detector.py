import datetime
from decimal import Decimal

def calculate_atr_14(candles: list[dict]) -> Decimal:
    """Calculates Average True Range over 14 periods.
    TR = max(high - low, |high - prev_close|, |low - prev_close|)
    """
    n = len(candles)
    if n < 15:
        return Decimal("0.01") # fallback if history too short
        
    tr_values = []
    for i in range(1, n):
        high = Decimal(str(candles[i]["high"]))
        low = Decimal(str(candles[i]["low"]))
        prev_close = Decimal(str(candles[i-1]["close"]))
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
        
    # Standard Wilder's smoothing
    atr = sum(tr_values[:14]) / Decimal("14")
    for tr in tr_values[14:]:
        atr = (atr * Decimal("13") + tr) / Decimal("14")
        
    return atr if atr > 0 else Decimal("0.01")

class OrderBlockDetector:
    @staticmethod
    def detect_order_blocks(candles: list[dict]) -> list[dict]:
        """Detects new Order Blocks from a series of candles.
        An Order Block is the last opposite candle before a strong impulse move (gain/loss >= 1.5 * ATR).
        """
        detected_obs = []
        n = len(candles)
        if n < 18:
            return detected_obs
            
        atr = calculate_atr_14(candles)
        impulse_threshold = atr * Decimal("1.5")
        
        for i in range(15, n - 3):
            # 1. Bullish Impulse: 3 consecutive green candles
            is_bull_impulse = (
                candles[i]["close"] > candles[i]["open"] and
                candles[i+1]["close"] > candles[i+1]["open"] and
                candles[i+2]["close"] > candles[i+2]["open"]
            )
            if is_bull_impulse:
                total_gain = Decimal(str(candles[i+2]["close"])) - Decimal(str(candles[i]["open"]))
                if total_gain >= impulse_threshold:
                    # Find last opposite (bearish) candle preceding index i
                    last_bearish_idx = None
                    for j in range(i - 1, max(0, i - 6), -1):
                        if candles[j]["close"] < candles[j]["open"]:
                            last_bearish_idx = j
                            break
                    if last_bearish_idx is not None:
                        ob_candle = candles[last_bearish_idx]
                        ob_high = Decimal(str(ob_candle["high"]))
                        ob_low = Decimal(str(ob_candle["low"]))
                        detected_obs.append({
                            "time": ob_candle["time"],
                            "ob_type": "BULLISH",
                            "ob_high": ob_high,
                            "ob_low": ob_low,
                            "ob_midpoint": (ob_high + ob_low) / Decimal("2")
                        })
                        
            # 2. Bearish Impulse: 3 consecutive red candles
            is_bear_impulse = (
                candles[i]["close"] < candles[i]["open"] and
                candles[i+1]["close"] < candles[i+1]["open"] and
                candles[i+2]["close"] < candles[i+2]["open"]
            )
            if is_bear_impulse:
                total_drop = Decimal(str(candles[i]["open"])) - Decimal(str(candles[i+2]["close"]))
                if total_drop >= impulse_threshold:
                    # Find last opposite (bullish) candle preceding index i
                    last_bullish_idx = None
                    for j in range(i - 1, max(0, i - 6), -1):
                        if candles[j]["close"] > candles[j]["open"]:
                            last_bullish_idx = j
                            break
                    if last_bullish_idx is not None:
                        ob_candle = candles[last_bullish_idx]
                        ob_high = Decimal(str(ob_candle["high"]))
                        ob_low = Decimal(str(ob_candle["low"]))
                        detected_obs.append({
                            "time": ob_candle["time"],
                            "ob_type": "BEARISH",
                            "ob_high": ob_high,
                            "ob_low": ob_low,
                            "ob_midpoint": (ob_high + ob_low) / Decimal("2")
                        })
                        
        return detected_obs
