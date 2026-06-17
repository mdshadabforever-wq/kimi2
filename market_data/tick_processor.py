import datetime
import time
from market_data.market_validator import MarketValidator
from market_data.latency_monitor import LatencyMonitor
import database

class TickProcessor:
    def __init__(self, candle_builder_callback=None):
        self.validator = MarketValidator()
        self.latency_monitor = LatencyMonitor()
        self.candle_builder_callback = candle_builder_callback

    def process_tick(self, tick: dict) -> bool:
        """Processes a single tick: validates it, measures receive latency,
        persists it in raw_ticks database table, and forwards it to the aggregator.
        """
        proc_start = time.perf_counter()
        
        # 1. Validate Tick
        is_valid, reason = self.validator.validate_tick(tick)
        if not is_valid:
            print(f"[TICK PROCESSOR] Rejecting tick for {tick.get('symbol')}: {reason}")
            return False

        symbol = tick["symbol"]
        price = tick["price"]
        volume = tick["volume"]
        tick_time = tick["time"]

        # 2. Measure Receive Latency
        now = datetime.datetime.now()
        receive_latency_ms = int((now - tick_time).total_seconds() * 1000)
        if receive_latency_ms < 0:
            receive_latency_ms = 0 # Clock skew safeguard

        # 3. Persist Raw Tick (Requirement 1)
        query = """
            INSERT INTO raw_ticks (time, symbol, price, volume, received_at)
            VALUES (%s, %s, %s, %s, NOW());
        """
        try:
            database.execute_query(query, (tick_time, symbol, price, volume))
        except Exception as e:
            # Print DB error but don't crash tick pipeline (robust fallback)
            print(f"[TICK PROCESSOR] Failed to persist raw tick for {symbol}: {e}")

        # 4. Measure Processing Latency
        processing_latency_ms = int((time.perf_counter() - proc_start) * 1000)

        # 5. Route to Candle Builder
        candle_build_latency_ms = 0
        if self.candle_builder_callback:
            agg_start = time.perf_counter()
            try:
                self.candle_builder_callback(tick)
            except Exception as e:
                print(f"[TICK PROCESSOR] Error in candle builder callback: {e}")
            candle_build_latency_ms = int((time.perf_counter() - agg_start) * 1000)

        # 6. Record Latency Metrics (Requirement 6)
        self.latency_monitor.record_latency(
            symbol=symbol,
            receive_lat_ms=receive_latency_ms,
            processing_lat_ms=processing_latency_ms,
            candle_build_lat_ms=candle_build_latency_ms,
            stage="TICK_INGESTION"
        )

        return True
