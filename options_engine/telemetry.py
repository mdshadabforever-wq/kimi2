import database

class OptionsTelemetry:
    @staticmethod
    def record_latency(symbol: str, duration_ms: float):
        """Saves latency metrics into the latency_metrics table."""
        query = """
            INSERT INTO latency_metrics (symbol, receive_latency_ms, processing_latency_ms, candle_build_latency_ms, stage)
            VALUES (%s, %s, %s, %s, %s);
        """
        try:
            database.execute_query(query, (symbol, 0, int(duration_ms), 0, "OPTIONS_INTELLIGENCE"))
        except Exception as e:
            # Silent fallback if telemetry table is blocked or locked
            pass
