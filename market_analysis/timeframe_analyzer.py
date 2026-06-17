import datetime
from decimal import Decimal
import database
from market_analysis.indicator_cache import IndicatorCache, make_aware

EMA_PERIOD = 20
ALPHA = Decimal("2") / Decimal(str(EMA_PERIOD + 1))  # 2 / 21

class TimeframeAnalyzer:
    def __init__(self, cache: IndicatorCache):
        self.cache = cache

    def analyze_timeframe(self, symbol: str, timeframe: str, boundary_time: datetime.datetime, current_price: Decimal = None) -> tuple[str, Decimal]:
        boundary_time = make_aware(boundary_time)
        """Calculates the trend for a given symbol, timeframe, and boundary time.
        Trend is BULLISH if close > EMA_20, BEARISH if close < EMA_20, NEUTRAL otherwise.
        Returns: (trend_direction, ema_20_value)
        """
        if current_price is None:
            # --- Warmup / Historical Completed Candle Mode ---
            # 1. Check if the EMA is already cached for this exact boundary time
            cached = self.cache.get_ema(symbol, timeframe, boundary_time)
            if cached:
                ema_val, close_val = cached
                return self._get_trend_direction(close_val, ema_val), ema_val

            # 2. Try to get the latest cached EMA before this boundary time
            prev_time, prev_ema = self.cache.get_latest_completed_ema(symbol, timeframe, boundary_time)
            
            if prev_ema is not None:
                # Incremental calculation: fetch all candles between prev_time (exclusive) and boundary_time (inclusive)
                query = """
                    SELECT time, close FROM market_data
                    WHERE symbol = %s AND timeframe = %s AND time > %s AND time <= %s
                    ORDER BY time ASC;
                """
                rows = database.execute_query(query, (symbol, timeframe, prev_time, boundary_time), fetch=True)
                
                curr_ema = prev_ema
                for row in rows:
                    t_time, close_val = row[0], Decimal(str(row[1]))
                    curr_ema = (close_val * ALPHA) + (curr_ema * (Decimal("1") - ALPHA))
                    self.cache.set_ema(symbol, timeframe, t_time, curr_ema, close_val)
                    
                # Check trend
                if rows:
                    final_close = Decimal(str(rows[-1][1]))
                    trend = self._get_trend_direction(final_close, curr_ema)
                    return trend, curr_ema

            # 3. Bootstrapping/Fallback: Query historical candles to compute EMA from scratch
            query = """
                SELECT time, close FROM market_data
                WHERE symbol = %s AND timeframe = %s AND time <= %s
                ORDER BY time DESC LIMIT 50;
            """
            rows = database.execute_query(query, (symbol, timeframe, boundary_time), fetch=True)
            if len(rows) < EMA_PERIOD:
                # Insufficient data to calculate 20 EMA
                return "NEUTRAL", Decimal("0")

            # Reverse to chronological order (ascending)
            rows.reverse()
            
            # Calculate SMA of first 20 candles as starting EMA
            first_20_closes = [Decimal(str(r[1])) for r in rows[:EMA_PERIOD]]
            curr_ema = sum(first_20_closes) / Decimal(str(EMA_PERIOD))
            
            # Cache the initial starting EMA
            start_time, start_close = rows[EMA_PERIOD - 1][0], Decimal(str(rows[EMA_PERIOD - 1][1]))
            self.cache.set_ema(symbol, timeframe, start_time, curr_ema, start_close)

            # Apply EMA formula for subsequent candles
            for row in rows[EMA_PERIOD:]:
                t_time, close_val = row[0], Decimal(str(row[1]))
                curr_ema = (close_val * ALPHA) + (curr_ema * (Decimal("1") - ALPHA))
                self.cache.set_ema(symbol, timeframe, t_time, curr_ema, close_val)

            # Retrieve the close price of the candle at boundary_time
            final_row = rows[-1]
            final_close = Decimal(str(final_row[1]))
            
            trend = self._get_trend_direction(final_close, curr_ema)
            return trend, curr_ema

        else:
            # --- Live Forming Candle Mode ---
            # 1. Try to get the latest cached completed EMA *before* boundary_time
            prev_time, prev_ema = self.cache.get_latest_completed_ema(symbol, timeframe, boundary_time)
            
            if prev_ema is not None:
                # Query completed candles between prev_time (exclusive) and boundary_time (exclusive)
                query = """
                    SELECT time, close FROM market_data
                    WHERE symbol = %s AND timeframe = %s AND time > %s AND time < %s
                    ORDER BY time ASC;
                """
                rows = database.execute_query(query, (symbol, timeframe, prev_time, boundary_time), fetch=True)
                curr_ema = prev_ema
                for row in rows:
                    t_time, close_val = row[0], Decimal(str(row[1]))
                    curr_ema = (close_val * ALPHA) + (curr_ema * (Decimal("1") - ALPHA))
                    self.cache.set_ema(symbol, timeframe, t_time, curr_ema, close_val)
                
                # Apply current forming price on top of the latest completed EMA
                forming_ema = (current_price * ALPHA) + (curr_ema * (Decimal("1") - ALPHA))
                trend = self._get_trend_direction(current_price, forming_ema)
                return trend, forming_ema
                
            # 2. Bootstrapping/Fallback: Query historical candles before boundary_time
            query = """
                SELECT time, close FROM market_data
                WHERE symbol = %s AND timeframe = %s AND time < %s
                ORDER BY time DESC LIMIT 50;
            """
            rows = database.execute_query(query, (symbol, timeframe, boundary_time), fetch=True)
            if len(rows) < EMA_PERIOD:
                return "NEUTRAL", Decimal("0")

            rows.reverse()
            first_20_closes = [Decimal(str(r[1])) for r in rows[:EMA_PERIOD]]
            curr_ema = sum(first_20_closes) / Decimal(str(EMA_PERIOD))
            start_time, start_close = rows[EMA_PERIOD - 1][0], Decimal(str(rows[EMA_PERIOD - 1][1]))
            self.cache.set_ema(symbol, timeframe, start_time, curr_ema, start_close)

            for row in rows[EMA_PERIOD:]:
                t_time, close_val = row[0], Decimal(str(row[1]))
                curr_ema = (close_val * ALPHA) + (curr_ema * (Decimal("1") - ALPHA))
                self.cache.set_ema(symbol, timeframe, t_time, curr_ema, close_val)

            # Apply current forming price on top of the latest completed EMA
            forming_ema = (current_price * ALPHA) + (curr_ema * (Decimal("1") - ALPHA))
            trend = self._get_trend_direction(current_price, forming_ema)
            return trend, forming_ema

    def _get_trend_direction(self, price: Decimal, ema: Decimal) -> str:
        if price > ema:
            return "BULLISH"
        elif price < ema:
            return "BEARISH"
        return "NEUTRAL"
