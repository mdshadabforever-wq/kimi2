from decimal import Decimal
import datetime
from config import Config

# Setup timezone info from config
if Config.TIMEZONE == "Asia/Kolkata":
    TZ_INFO = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
else:
    TZ_INFO = datetime.timezone.utc

def make_aware(dt: datetime.datetime) -> datetime.datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ_INFO)
    return dt.astimezone(TZ_INFO)

class IndicatorCache:
    def __init__(self):
        # Cache structure:
        # Key: (symbol, timeframe, boundary_time)
        # Value: (ema_20_value, close_value)
        self._cache = {}

    def get_ema(self, symbol: str, timeframe: str, boundary_time: datetime.datetime) -> tuple[Decimal, Decimal]:
        """Retrieves the cached (ema_20, close) for a symbol and timeframe at a specific boundary time."""
        bt = make_aware(boundary_time)
        return self._cache.get((symbol, timeframe, bt))

    def set_ema(self, symbol: str, timeframe: str, boundary_time: datetime.datetime, ema_value: Decimal, close_value: Decimal):
        """Caches the calculated (ema_20, close) for a specific boundary time."""
        bt = make_aware(boundary_time)
        self._cache[(symbol, timeframe, bt)] = (ema_value, close_value)

    def get_latest_completed_ema(self, symbol: str, timeframe: str, boundary_time: datetime.datetime) -> tuple[datetime.datetime, Decimal]:
        """Finds the chronologically latest cached EMA for a timeframe before a given boundary time.
        Useful for O(1) incremental EMA calculation.
        """
        bt = make_aware(boundary_time)
        matching_keys = [k for k in self._cache.keys() if k[0] == symbol and k[1] == timeframe and k[2] < bt]
        if not matching_keys:
            return None, None
        
        # Sort by boundary_time descending
        latest_key = max(matching_keys, key=lambda k: k[2])
        return latest_key[2], self._cache[latest_key][0]

    def clear(self):
        """Clears the cache state."""
        self._cache.clear()
        
    def size(self) -> int:
        """Returns the number of elements in the cache."""
        return len(self._cache)
