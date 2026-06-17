import datetime
import random
from decimal import Decimal
import psycopg2.extras
import database
from market_data.instrument_loader import InstrumentLoader

class HistoricalDownloader:
    @staticmethod
    def generate_and_save_data(days_lookback: int = 90):
        """Generates synthetic high-fidelity historical data for all 50 symbols and saves to DB."""
        loader = InstrumentLoader()
        symbols = loader.symbols
        
        # Calculate start and end dates
        end_date = datetime.date.today()
        # Find 90 trading days
        trading_days = []
        curr = end_date - datetime.timedelta(days=days_lookback * 1.5)
        while curr <= end_date:
            # Skip weekends (Saturday=5, Sunday=6)
            if curr.weekday() < 5:
                trading_days.append(curr)
            curr += datetime.timedelta(days=1)
            
        # Limit to last days_lookback trading days
        trading_days = trading_days[-days_lookback:]
        
        print(f"[HISTORICAL DOWNLOADER] Generating {len(trading_days)} days of market data for {len(symbols)} symbols...")
        
        # Clear existing historical data for backtesting to avoid primary key duplicates
        database.execute_query("DELETE FROM market_data;")
        
        daily_inserts = []
        hourly_inserts = []
        
        # Seed prices for each symbol
        random.seed(42) # For reproducible paths
        symbol_seeds = {sym: random.uniform(100.0, 1500.0) for sym in symbols}
        
        for symbol in symbols:
            price = symbol_seeds[symbol]
            for t_date in trading_days:
                # Daily candle parameters
                # Daily drift is slightly positive to simulate realistic bull/bear trends
                drift = random.uniform(-0.02, 0.025)
                daily_open = price * (1.0 + random.uniform(-0.01, 0.01))
                daily_close = price * (1.0 + drift)
                daily_high = max(daily_open, daily_close) * (1.0 + random.uniform(0.0, 0.015))
                daily_low = min(daily_open, daily_close) * (1.0 - random.uniform(0.0, 0.015))
                daily_volume = random.randint(100000, 5000000)
                
                # Align time with Asia/Kolkata timezone (15:30)
                daily_time = datetime.datetime.combine(t_date, datetime.time(15, 30))
                
                daily_inserts.append((
                    daily_time, symbol, 
                    Decimal(str(round(daily_open, 4))), 
                    Decimal(str(round(daily_high, 4))), 
                    Decimal(str(round(daily_low, 4))), 
                    Decimal(str(round(daily_close, 4))), 
                    daily_volume, 
                    Decimal(str(round((daily_open + daily_close + daily_high + daily_low) / 4, 4))),
                    "Daily"
                ))
                
                # Hourly candles (6 hours per trading day)
                hr_price = daily_open
                for hour_idx in range(6):
                    hr_drift = random.uniform(-0.01, 0.012)
                    hr_open = hr_price
                    hr_close = hr_price * (1.0 + hr_drift)
                    hr_high = max(hr_open, hr_close) * (1.0 + random.uniform(0.0, 0.005))
                    hr_low = min(hr_open, hr_close) * (1.0 - random.uniform(0.0, 0.005))
                    hr_volume = daily_volume // 6
                    
                    hr_time = datetime.datetime.combine(t_date, datetime.time(9 + hour_idx, 30))
                    hourly_inserts.append((
                        hr_time, symbol,
                        Decimal(str(round(hr_open, 4))),
                        Decimal(str(round(hr_high, 4))),
                        Decimal(str(round(hr_low, 4))),
                        Decimal(str(round(hr_close, 4))),
                        hr_volume,
                        Decimal(str(round((hr_open + hr_close + hr_high + hr_low) / 4, 4))),
                        "1h"
                    ))
                    hr_price = hr_close
                
                # Update base price for next trading day
                price = daily_close
                
        # Batch insert daily records using pool connection
        query = """
            INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe)
            VALUES %s
            ON CONFLICT DO NOTHING;
        """
        
        conn = database.get_connection()
        try:
            with conn.cursor() as cursor:
                psycopg2.extras.execute_values(cursor, query, daily_inserts)
                psycopg2.extras.execute_values(cursor, query, hourly_inserts)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[HISTORICAL DOWNLOADER] Error inserting records: {e}")
            raise e
        finally:
            database.release_connection(conn)
            
        print(f"[HISTORICAL DOWNLOADER] Successfully loaded {len(daily_inserts)} Daily and {len(hourly_inserts)} 1h records.")
