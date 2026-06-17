import datetime
from decimal import Decimal
import database
from config import Config

# Asia/Kolkata timezone offset is UTC+5:30
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

# NSE Market Session constants
MARKET_OPEN_TIME = datetime.time(9, 15)
MARKET_CLOSE_TIME = datetime.time(15, 30)

# Holiday list (mock)
HOLIDAYS = {
    datetime.date(2026, 1, 26),  # Republic Day
    datetime.date(2026, 8, 15),  # Independence Day
    datetime.date(2026, 10, 2),  # Gandhi Jayanti
}

def is_market_session_active(dt: datetime.datetime) -> bool:
    """Returns True if the datetime is within NSE normal market hours.
    NSE hours: Monday to Friday, 09:15:00 to 15:30:00 IST. Excludes holidays.
    """
    from config import Config
    if Config.MOCK_MODE:
        return True

    dt_local = make_aware(dt)
    if dt_local.date() in HOLIDAYS:
        return False
    # Weekday check (0=Monday, 6=Sunday)
    if dt_local.weekday() >= 5:
        return False
        
    t = dt_local.time()
    return MARKET_OPEN_TIME <= t <= MARKET_CLOSE_TIME

def get_candle_boundary(dt: datetime.datetime, timeframe: str) -> datetime.datetime:
    """Calculates the floor boundary timestamp for a given timeframe."""
    is_aware = dt.tzinfo is not None
    dt_local = make_aware(dt)
    if timeframe == "1m":
        res = dt_local.replace(second=0, microsecond=0)
    elif timeframe == "5m":
        minute = (dt_local.minute // 5) * 5
        res = dt_local.replace(minute=minute, second=0, microsecond=0)
    elif timeframe == "15m":
        minute = (dt_local.minute // 15) * 15
        res = dt_local.replace(minute=minute, second=0, microsecond=0)
    elif timeframe == "30m":
        minute = (dt_local.minute // 30) * 30
        res = dt_local.replace(minute=minute, second=0, microsecond=0)
    elif timeframe == "Daily":
        res = datetime.datetime.combine(dt_local.date(), datetime.time.min).replace(tzinfo=dt_local.tzinfo)
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
        
    if not is_aware:
        res = res.replace(tzinfo=None)
    return res

class CandleBuilder:
    def __init__(self):
        # In-memory store of active candles
        # Key: (symbol, timeframe, boundary_time), Value: dict (O, H, L, C, V, VWAP)
        self.active_candles = {}
        
        # Cache of processed tick signatures to discard duplicates (Requirement 4)
        # Store tuples of (symbol, time, price, volume)
        self.processed_ticks_cache = set()

    def clear_cache(self):
        """Clears memory state (useful for test resets)."""
        self.active_candles.clear()
        self.processed_ticks_cache.clear()

    def process_tick(self, tick: dict):
        """Processes an incoming tick, updates all active candles, and writes them to the DB."""
        symbol = tick["symbol"]
        price = Decimal(str(tick["price"]))
        volume = int(tick["volume"])
        tick_time = tick["time"]

        # 1. Market Session Awareness Check (Requirement 2)
        if not is_market_session_active(tick_time):
            print(f"[CANDLE BUILDER] Ignoring tick for {symbol} at {tick_time}: Outside market hours.")
            return

        # 2. Duplicate Check (Requirement 4)
        tick_sig = (symbol, tick_time.isoformat(), float(price), volume)
        if tick_sig in self.processed_ticks_cache:
            print(f"[CANDLE BUILDER] Discarding duplicate tick: {tick_sig}")
            return
        self.processed_ticks_cache.add(tick_sig)
        
        # Limit cache size to prevent leak
        if len(self.processed_ticks_cache) > 10000:
            self.processed_ticks_cache.pop()

        # 3. Update candles for all 5 timeframes
        timeframes = ["1m", "5m", "15m", "30m", "Daily"]
        for tf in timeframes:
            boundary_time = get_candle_boundary(tick_time, tf)
            self._update_and_persist_candle(symbol, tf, boundary_time, price, volume, tick_time)

    def _get_candle_end_time(self, boundary_time: datetime.datetime, timeframe: str) -> datetime.datetime:
        if timeframe == "1m":
            return boundary_time + datetime.timedelta(minutes=1)
        elif timeframe == "5m":
            return boundary_time + datetime.timedelta(minutes=5)
        elif timeframe == "15m":
            return boundary_time + datetime.timedelta(minutes=15)
        elif timeframe == "30m":
            return boundary_time + datetime.timedelta(minutes=30)
        elif timeframe == "Daily":
            return boundary_time + datetime.timedelta(days=1)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    def _update_and_persist_candle(self, symbol: str, timeframe: str, boundary_time: datetime.datetime, price: Decimal, volume: int, tick_time: datetime.datetime):
        key = (symbol, timeframe, boundary_time)
        
        # Try to load existing state if not in memory (Recovery logic / Out-of-order handling)
        if key not in self.active_candles:
            # Query the database to see if we have this candle already (Requirement 3)
            db_candle = self._load_candle_from_db(symbol, timeframe, boundary_time)
            if db_candle:
                self.active_candles[key] = db_candle
            else:
                # Initialize new candle with 0 volume and value, so the first tick aggregates correctly
                self.active_candles[key] = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 0,
                    "total_value": Decimal("0"),
                    "latest_tick_time": tick_time
                }

        candle = self.active_candles[key]
        
        # Handle Out-of-Order / Delayed ticks (Requirement 4)
        # If tick_time is earlier than the latest tick we used to set 'close', we still update High/Low/Volume.
        # But we only set 'close' if this tick is chronologically the latest in this boundary period.
        if price > candle["high"]:
            candle["high"] = price
        if price < candle["low"]:
            candle["low"] = price
            
        # Accumulate volume
        candle["volume"] += volume
        candle["total_value"] += price * volume
        
        # Update close price only if tick_time is the latest chronologically
        if "latest_tick_time" not in candle or make_aware(tick_time) >= make_aware(candle["latest_tick_time"]):
            candle["close"] = price
            candle["latest_tick_time"] = tick_time

        # Save to TimescaleDB (UPSERT operation)
        self._save_candle_to_db(symbol, timeframe, boundary_time, candle)

    def _load_candle_from_db(self, symbol: str, timeframe: str, boundary_time: datetime.datetime) -> dict:
        query = """
            SELECT open, high, low, close, volume, vwap
            FROM market_data
            WHERE symbol = %s AND timeframe = %s AND time = %s;
        """
        try:
            res = database.execute_query(query, (symbol, timeframe, boundary_time), fetch=True)
            if res:
                row = res[0]
                
                # Fetch latest tick time for recovery boundary
                end_time = self._get_candle_end_time(boundary_time, timeframe)
                latest_tick_time = boundary_time
                try:
                    ticks_res = database.execute_query(
                        "SELECT MAX(time) FROM raw_ticks WHERE symbol = %s AND time >= %s AND time < %s;",
                        (symbol, boundary_time, end_time), fetch=True
                    )
                    if ticks_res and ticks_res[0][0]:
                        latest_tick_time = ticks_res[0][0]
                except Exception:
                    pass

                return {
                    "open": Decimal(str(row[0])),
                    "high": Decimal(str(row[1])),
                    "low": Decimal(str(row[2])),
                    "close": Decimal(str(row[3])),
                    "volume": int(row[4]),
                    "total_value": Decimal(str(row[5])) * int(row[4]),
                    "latest_tick_time": latest_tick_time
                }
        except Exception as e:
            pass
        return None

    def _save_candle_to_db(self, symbol: str, timeframe: str, boundary_time: datetime.datetime, candle: dict):
        # Calculate VWAP
        vwap = candle["total_value"] / candle["volume"] if candle["volume"] > 0 else candle["close"]
        
        query = """
            INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, symbol, timeframe) 
            DO UPDATE SET 
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                vwap = EXCLUDED.vwap;
        """
        try:
            database.execute_query(query, (
                boundary_time, symbol,
                candle["open"], candle["high"], candle["low"], candle["close"],
                candle["volume"], vwap, timeframe
            ))
            if timeframe == "15m":
                print(f"[CANDLE BUILDER] Persisted 15m candle for {symbol} at {boundary_time} (Close={candle['close']}, Volume={candle['volume']})")
        except Exception as e:
            print(f"[CANDLE BUILDER] DB Write Error: {e}")

    def rebuild_candles_from_raw_ticks(self, symbol: str, timeframe: str, start_time: datetime.datetime, end_time: datetime.datetime):
        """Loads raw ticks from database and rebuilds candles chronologically (Requirement 1)."""
        query = """
            SELECT time, price, volume FROM raw_ticks
            WHERE symbol = %s AND time >= %s AND time <= %s
            ORDER BY time ASC;
        """
        try:
            ticks = database.execute_query(query, (symbol, start_time, end_time), fetch=True)
            print(f"[REBUILD] Found {len(ticks)} raw ticks for {symbol} between {start_time} and {end_time}.")
            
            # Temporary clear active memory for this run
            self.clear_cache()
            
            for row in ticks:
                t_time, price, volume = row
                tick = {
                    "symbol": symbol,
                    "price": float(price),
                    "volume": int(volume),
                    "time": t_time
                }
                # Process normally (this aggregates and writes to market_data table)
                self.process_tick(tick)
            print(f"[REBUILD] Completed candle rebuild for {symbol} ({timeframe}).")
        except Exception as e:
            print(f"[REBUILD] Error rebuilding candles: {e}")
            raise e
