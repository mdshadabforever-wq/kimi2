import datetime
import database

class LatencyMonitor:
    def __init__(self):
        pass

    def record_latency(self, symbol: str, receive_lat_ms: int, processing_lat_ms: int, candle_build_lat_ms: int, stage: str):
        """Saves latency telemetry to the database latency_metrics table."""
        query = """
            INSERT INTO latency_metrics (timestamp, symbol, receive_latency_ms, processing_latency_ms, candle_build_latency_ms, stage)
            VALUES (NOW(), %s, %s, %s, %s, %s);
        """
        try:
            database.execute_query(query, (symbol, int(receive_lat_ms), int(processing_lat_ms), int(candle_build_lat_ms), stage))
        except Exception as e:
            # Catch silently if database is simulating outage or down
            pass
