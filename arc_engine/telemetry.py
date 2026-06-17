import database


class ARCTelemetry:
    """Records ARC Engine processing latency to latency_metrics table.
    Clarification 008, Section 14.
    Stage tag: ARC_REVIEW
    """

    @staticmethod
    def record_latency(symbol: str, total_latency_ms: float, claude_latency_ms: float = 0.0, cache_hit: bool = False) -> None:
        """Persists ARC processing latency to latency_metrics.

        Args:
            symbol: The symbol being reviewed.
            total_latency_ms: Full ARC processing time (input assembly + Claude + parse).
            claude_latency_ms: Claude API call time only.
            cache_hit: Whether the decision was served from Redis cache.
        """
        query = """
            INSERT INTO latency_metrics (symbol, receive_latency_ms, processing_latency_ms, candle_build_latency_ms, stage)
            VALUES (%s, %s, %s, %s, %s);
        """
        try:
            database.execute_query(query, (
                symbol,
                int(claude_latency_ms),   # reuse receive_latency_ms to store Claude-specific latency
                int(total_latency_ms),
                1 if cache_hit else 0,    # reuse candle_build_latency_ms as cache_hit flag (0/1)
                "ARC_REVIEW"
            ))
        except Exception:
            pass  # Fire-and-forget: telemetry never blocks signal processing
