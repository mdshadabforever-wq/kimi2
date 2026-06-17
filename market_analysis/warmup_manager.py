import datetime
from decimal import Decimal
import database
from market_analysis.indicator_cache import IndicatorCache
from market_analysis.timeframe_analyzer import TimeframeAnalyzer
from market_analysis.trend_persistence import TrendPersistence

class WarmupManager:
    def __init__(self, cache: IndicatorCache, analyzer: TimeframeAnalyzer):
        self.cache = cache
        self.analyzer = analyzer

    def warmup_symbol(self, symbol: str, timeframes: list[str] = None):
        """Warm up the trend cache and database state for a specific symbol."""
        if timeframes is None:
            timeframes = ["Daily", "1h", "15m", "5m"]
            
        states_to_save = []
        for tf in timeframes:
            # Query only the latest candle time to bootstrap from
            query = """
                SELECT time FROM market_data
                WHERE symbol = %s AND timeframe = %s
                ORDER BY time DESC LIMIT 1;
            """
            try:
                res = database.execute_query(query, (symbol, tf), fetch=True)
                if not res:
                    continue
                latest_time = res[0][0]
                
                # Compute trend and EMA for the latest completed candle
                # This automatically populates the cache for all preceding candles!
                self.analyzer.analyze_timeframe(symbol, tf, latest_time)
                
                # Collect all cached entries for this symbol and timeframe to persist
                for key, val in self.cache._cache.items():
                    if key[0] == symbol and key[1] == tf:
                        t_time = key[2]
                        ema_val, close_val = val
                        if ema_val > 0:
                            trend = self.analyzer._get_trend_direction(close_val, ema_val)
                            states_to_save.append((t_time, symbol, tf, trend, ema_val, close_val))
            except Exception as e:
                print(f"[WARMUP MANAGER] Error warming up {symbol} on {tf}: {e}")
                
        # Bulk save all trend states for this symbol
        if states_to_save:
            TrendPersistence.save_trend_states_bulk(states_to_save)

    def warmup_all_symbols(self, symbols: list[str]):
        """Warm up all given constituent symbols."""
        print(f"[WARMUP] Starting historical warmup for {len(symbols)} symbols...")
        import time
        start = time.perf_counter()
        for symbol in symbols:
            self.warmup_symbol(symbol)
        duration = (time.perf_counter() - start) * 1000
        print(f"[WARMUP] Completed historical warmup for {len(symbols)} symbols in {duration:.1f}ms.")
