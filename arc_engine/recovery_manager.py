import json
import datetime
import redis_client
from arc_engine.persistence import ARCPersistence


class ARCRecoveryManager:
    """Handles ARC Engine restart recovery from Redis and database.
    Clarification 008, Section 13.

    Recovery order:
    1. Load watchlist decisions from Redis arc:watchlist:{date}
    2. Load individual signal decisions from Redis arc:decision:{signal_id}
    3. If Redis empty, start fresh — first premarket call rebuilds cache.
    """

    WATCHLIST_KEY_PREFIX = "arc:watchlist"
    DECISION_KEY_PREFIX = "arc:decision"
    PREMARKET_KEY_PREFIX = "arc:premarket"

    @staticmethod
    def recover_watchlist(session_date: datetime.date) -> dict:
        """Restores in-memory watchlist decision map {symbol: arc_decision} from Redis.

        Returns:
            Dict of symbol → arc_decision. Empty dict if no cache.
        """
        key = f"{ARCRecoveryManager.WATCHLIST_KEY_PREFIX}:{session_date}"
        try:
            cached = redis_client.get_val(key)
            if cached:
                data = json.loads(cached)
                print(f"[ARC RECOVERY] Restored watchlist decisions for {session_date}: {len(data)} symbols")
                return data
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to load watchlist from Redis: {e}")
        return {}

    @staticmethod
    def save_watchlist(session_date: datetime.date, decisions: dict) -> bool:
        """Persists full watchlist decision map to Redis with 24h TTL."""
        key = f"{ARCRecoveryManager.WATCHLIST_KEY_PREFIX}:{session_date}"
        try:
            redis_client.set_val(key, json.dumps(decisions), ex=86400)
            return True
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to save watchlist to Redis: {e}")
            return False

    @staticmethod
    def get_cached_signal_decision(signal_id: str) -> dict | None:
        """Returns cached ARC decision JSON for a signal_id, or None if not cached."""
        key = f"{ARCRecoveryManager.DECISION_KEY_PREFIX}:{signal_id}"
        try:
            cached = redis_client.get_val(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to read signal cache for {signal_id}: {e}")
        return None

    @staticmethod
    def cache_signal_decision(signal_id: str, arc_decision_json: dict) -> bool:
        """Caches ARC decision JSON for a signal_id with 4h TTL (intraday)."""
        key = f"{ARCRecoveryManager.DECISION_KEY_PREFIX}:{signal_id}"
        try:
            redis_client.set_val(key, json.dumps(arc_decision_json, default=str), ex=14400)
            return True
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to cache signal decision for {signal_id}: {e}")
            return False

    @staticmethod
    def get_cached_premarket_decision(session_date: datetime.date, symbol: str) -> dict | None:
        """Returns cached premarket ARC decision for a symbol, or None."""
        key = f"{ARCRecoveryManager.PREMARKET_KEY_PREFIX}:{session_date}:{symbol}"
        try:
            cached = redis_client.get_val(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to read premarket cache for {symbol}: {e}")
        return None

    @staticmethod
    def cache_premarket_decision(session_date: datetime.date, symbol: str, arc_decision_json: dict) -> bool:
        """Caches premarket ARC decision for a symbol with 24h TTL."""
        key = f"{ARCRecoveryManager.PREMARKET_KEY_PREFIX}:{session_date}:{symbol}"
        try:
            redis_client.set_val(key, json.dumps(arc_decision_json, default=str), ex=86400)
            return True
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to cache premarket decision for {symbol}: {e}")
            return False

    @staticmethod
    def invalidate_signal(signal_id: str) -> bool:
        """Removes a signal's cached ARC decision from Redis (e.g., on force_refresh)."""
        key = f"{ARCRecoveryManager.DECISION_KEY_PREFIX}:{signal_id}"
        try:
            redis_client.delete_val(key)
            return True
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to invalidate cache for {signal_id}: {e}")
            return False

    @staticmethod
    def recover_signal_decisions(session_date: datetime.date) -> dict:
        """Loads signal-level ARC decisions from DB for restart recovery.
        Returns dict of {signal_id: arc_decision_label}.
        """
        try:
            rows = ARCPersistence.load_active_signals_with_arc(session_date)
            return {r["signal_id"]: r["arc_decision"] for r in rows}
        except Exception as e:
            print(f"[ARC RECOVERY] Failed to recover signal decisions from DB: {e}")
            return {}
