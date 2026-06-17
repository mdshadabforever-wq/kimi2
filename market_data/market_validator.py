import datetime
import os
from market_data.instrument_loader import InstrumentLoader

class MarketValidator:
    def __init__(self):
        self.loader = InstrumentLoader()

    def validate_tick(self, tick: dict) -> tuple[bool, str]:
        """Validates standard fields in a tick object.
        Returns: (is_valid, reason)
        """
        symbol = tick.get("symbol")
        price = tick.get("price")
        volume = tick.get("volume")
        tick_time = tick.get("time")

        if not symbol:
            return False, "Missing symbol"
        if not self.loader.is_valid_symbol(symbol):
            return False, f"Invalid constituent symbol: {symbol}"
        if price is None or price <= 0:
            return False, f"Invalid price: {price}"
        if volume is None or volume < 0:
            return False, f"Invalid volume: {volume}"
        if not tick_time or not isinstance(tick_time, datetime.datetime):
            return False, "Invalid or missing tick timestamp"

        # Check for stale data (timestamp older than 2 minutes)
        # Skip this check in test environment to allow historic deterministic test inputs
        if os.getenv("IIIS_TESTING") != "True":
            gap = datetime.datetime.now() - tick_time
            if gap.total_seconds() > 120:
                return False, f"Stale tick data: {gap.total_seconds():.1f}s delay"

        # Check bid-ask spread if provided
        bid = tick.get("bid")
        ask = tick.get("ask")
        if bid is not None and ask is not None:
            if bid <= 0 or ask <= 0:
                return False, f"Invalid bid/ask values: bid={bid}, ask={ask}"
            spread_pct = (ask - bid) / bid
            if spread_pct > 0.0020: # 0.20%
                return False, f"Bid-ask spread too wide: {spread_pct*100:.3f}%"

        return True, ""
