from decimal import Decimal
import datetime
import time

from market_analysis.indicator_cache import IndicatorCache
from market_analysis.timeframe_analyzer import TimeframeAnalyzer
from market_analysis.alignment_engine import AlignmentEngine
from market_analysis.warmup_manager import WarmupManager
from market_analysis.trend_persistence import TrendPersistence

class TrendEngine:
    def __init__(self):
        self.cache = IndicatorCache()
        self.analyzer = TimeframeAnalyzer(self.cache)
        self.warmup_manager = WarmupManager(self.cache, self.analyzer)
        
        # In-memory latest computed trends per symbol
        # Key: symbol, Value: dict of {timeframe: trend}
        self.latest_trends = {}
        
        # Track last persisted completed boundary to avoid duplicate DB writes on every tick
        # Key: (symbol, timeframe), Value: completed_boundary (datetime)
        self.last_persisted = {}

    def warmup_system(self, symbols: list[str]):
        """Warm up indicator cache and trend state from database history."""
        self.warmup_manager.warmup_all_symbols(symbols)
        # Load the latest states into memory for recovery
        for sym in symbols:
            self.restore_state_from_db(sym)

    def restore_state_from_db(self, symbol: str):
        """Restores in-memory latest trend state from the database for restart recovery."""
        from market_analysis.indicator_cache import make_aware
        db_states = TrendPersistence.load_latest_trend_states(symbol)
        if db_states:
            self.latest_trends[symbol] = {tf: data["trend"] for tf, data in db_states.items()}
            # Also populate last_persisted to prevent duplicate DB writes
            for tf, data in db_states.items():
                if "time" in data:
                    self.last_persisted[(symbol, tf)] = make_aware(data["time"])
            print(f"[TREND ENGINE] Restored latest trend state for {symbol} from DB: {self.latest_trends[symbol]}")

    def process_tick(self, tick: dict) -> tuple[bool, str, int, dict]:
        """Calculates multi-timeframe trend alignment for a validated tick.
        
        Returns: (is_aligned, aligned_direction, alignment_score, timeframe_trends)
        """
        symbol = tick["symbol"]
        price = Decimal(str(tick["price"]))
        tick_time = tick["time"]

        # Ensure we have a dict entry for the symbol
        if symbol not in self.latest_trends:
            self.latest_trends[symbol] = {"Daily": "NEUTRAL", "1h": "NEUTRAL", "15m": "NEUTRAL", "5m": "NEUTRAL"}

        timeframes = ["Daily", "1h", "15m", "5m"]
        current_trends = {}
        
        # Start processing latency telemetry measurement
        start_time = time.perf_counter()

        for tf in timeframes:
            # 1. Calculate the candle boundary time for this tick
            boundary_time = self._get_boundary_time(tick_time, tf)
            
            # 2. Analyze the trend on this timeframe incorporating the live tick price
            trend, ema_val = self.analyzer.analyze_timeframe(symbol, tf, boundary_time, current_price=price)
            current_trends[tf] = trend

            # 3. Persist the completed candle trend only once when the boundary transitions
            completed_boundary = self._get_previous_boundary(boundary_time, tf)
            last_p = self.last_persisted.get((symbol, tf))
            
            if last_p is None or completed_boundary > last_p:
                # Calculate the final completed EMA and trend for the completed boundary
                self.analyzer.analyze_timeframe(symbol, tf, completed_boundary)
                cached_completed = self.cache.get_ema(symbol, tf, completed_boundary)
                if cached_completed:
                    comp_ema, comp_close = cached_completed
                    comp_trend = self.analyzer._get_trend_direction(comp_close, comp_ema)
                    # Persist completed state to DB
                    TrendPersistence.save_trend_state(completed_boundary, symbol, tf, comp_trend, comp_ema, comp_close)
                    self.last_persisted[(symbol, tf)] = completed_boundary

        # Update in-memory latest trends
        self.latest_trends[symbol].update(current_trends)

        # 4. Compute alignment
        is_aligned, direction, score = AlignmentEngine.calculate_alignment(current_trends)
        
        # Telemetry processing latency
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Persist latency metrics to database if needed (Requirement 18)
        self._record_telemetry(symbol, duration_ms)

        return is_aligned, direction, score, current_trends

    def _get_boundary_time(self, dt: datetime.datetime, timeframe: str) -> datetime.datetime:
        """Helper to get candle floor boundary."""
        if timeframe == "5m":
            minute = (dt.minute // 5) * 5
            return dt.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "15m":
            minute = (dt.minute // 15) * 15
            return dt.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "1h":
            return dt.replace(minute=0, second=0, microsecond=0)
        elif timeframe == "Daily":
            return datetime.datetime.combine(dt.date(), datetime.time.min).replace(tzinfo=dt.tzinfo)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    def _get_previous_boundary(self, boundary_time: datetime.datetime, timeframe: str) -> datetime.datetime:
        """Helper to calculate the previous completed candle boundary."""
        from market_analysis.indicator_cache import make_aware
        bt = make_aware(boundary_time)
        if timeframe == "5m":
            return bt - datetime.timedelta(minutes=5)
        elif timeframe == "15m":
            return bt - datetime.timedelta(minutes=15)
        elif timeframe == "1h":
            return bt - datetime.timedelta(hours=1)
        elif timeframe == "Daily":
            return bt - datetime.timedelta(days=1)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    def _record_telemetry(self, symbol: str, duration_ms: float):
        """Persists trend analysis latency to latency_metrics table."""
        # Use simple direct DB write
        query = """
            INSERT INTO latency_metrics (symbol, receive_latency_ms, processing_latency_ms, candle_build_latency_ms, stage)
            VALUES (%s, %s, %s, %s, %s);
        """
        try:
            database.execute_query(query, (symbol, 0, int(duration_ms), 0, "TREND_ANALYSIS"))
        except Exception:
            pass
