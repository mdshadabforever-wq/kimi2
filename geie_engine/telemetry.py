import database

class GEIETelemetry:
    @staticmethod
    def record_latency(symbol: str, duration_ms: float):
        """Records GEIE processing latency in the latency_metrics table."""
        query = """
            INSERT INTO latency_metrics (symbol, receive_latency_ms, processing_latency_ms, candle_build_latency_ms, stage)
            VALUES (%s, %s, %s, %s, %s);
        """
        try:
            # GEIE uses symbol "GLOBAL" for telemetry unless symbol specific
            database.execute_query(query, (symbol, 0, int(duration_ms), 0, "GEIE_ENGINE"))
        except Exception:
            pass
