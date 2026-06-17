import datetime
from decimal import Decimal
import database

def get_seeder_boundary(dt: datetime.datetime, timeframe: str) -> datetime.datetime:
    if timeframe == "1h":
        return dt.replace(minute=0, second=0, microsecond=0)
    from market_data.candle_builder import get_candle_boundary
    return get_candle_boundary(dt, timeframe)

def seed_mock_data_for_demo(symbols: list[str]):
    """Seeds database tables with mock historical candles, option chains,
    FII trend data, active order blocks, and BOS breaks so that live evaluations succeed.
    """
    print("[SEEDER] Seeding mock historical database tables for Trend, SMC, Options, and Scoring...")
    
    now = datetime.datetime.now()
    today = now.date()
    
    # 1. Seed Bullish Regime History
    try:
        res = database.execute_query("SELECT count(*) FROM regime_history;", fetch=True)
        if res[0][0] == 0:
            database.execute_query(
                "INSERT INTO regime_history (timestamp, regime, regime_score, adx, nifty_price, ad_ratio) "
                "VALUES (%s, %s, %s, %s, %s, %s);",
                (now, 'BULLISH_TRENDING', Decimal('100.0'), Decimal('28.5'), Decimal('23200.0'), Decimal('1.8'))
            )
            print("[SEEDER] Seeded market regime history.")
    except Exception as e:
        print(f"[SEEDER] Error seeding regime_history: {e}")
        
    # 2. Seed FII buying bias for the last 3 days
    try:
        res = database.execute_query("SELECT count(*) FROM fii_dii_tracker;", fetch=True)
        if res[0][0] == 0:
            for i in range(4):
                d = today - datetime.timedelta(days=i)
                if d.weekday() < 5: # Weekdays
                    database.execute_query(
                        "INSERT INTO fii_dii_tracker (date, fii_action, fii_amount_crores, dii_action, dii_amount_crores, combined_bias, consecutive_fii_buy_days) "
                        "VALUES (%s, 'BUYER', 1250.00, 'BUYER', 850.00, 'BULLISH', 4) "
                        "ON CONFLICT (date) DO NOTHING;",
                        (d,)
                    )
            print("[SEEDER] Seeded FII/DII tracking bias.")
    except Exception as e:
        print(f"[SEEDER] Error seeding fii_dii_tracker: {e}")

    # 3. Seed Bulk Deal
    try:
        res = database.execute_query("SELECT count(*) FROM bulk_deal_tracker;", fetch=True)
        if res[0][0] == 0:
            database.execute_query(
                "INSERT INTO bulk_deal_tracker (timestamp, symbol, deal_type, quantity, price, value_crores, deal_category) "
                "VALUES (%s, 'TATASTEEL', 'BUY', 3000000, 150.25, 45.08, 'BULK');",
                (now - datetime.timedelta(minutes=30),)
            )
            print("[SEEDER] Seeded institutional bulk deals.")
    except Exception as e:
        print(f"[SEEDER] Error seeding bulk_deal_tracker: {e}")

    # 4. Seed 40 completed historical candles for symbols + NIFTY 50 (rising trend)
    all_symbols = symbols + ["NIFTY 50"]
    try:
        res = database.execute_query("SELECT count(*) FROM market_data;", fetch=True)
        if res[0][0] == 0:
            print(f"[SEEDER] Inserting historical candles for {len(all_symbols)} symbols...")
            for symbol in all_symbols:
                base_price = Decimal("150.0") if symbol != "NIFTY 50" else Decimal("23000.0")
                
                # Seed 5m and 15m timeframes
                for tf in ["5m", "15m"]:
                    interval_min = 5 if tf == "5m" else 15
                    for i in range(40, -1, -1):
                        t_candle = get_seeder_boundary(now - datetime.timedelta(minutes=i * interval_min), tf)
                        
                        # Rising price trend simulation
                        price = base_price + Decimal(str((40 - i) * 0.1))
                        open_val = price - Decimal("0.2")
                        high_val = price + Decimal("0.5")
                        low_val = price - Decimal("0.3")
                        close_val = price
                        volume = 50000 if symbol != "NIFTY 50" else 2000000
                        vwap = (open_val + high_val + low_val + close_val) / Decimal("4")
                        
                        database.execute_query(
                            "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                            "ON CONFLICT (time, symbol, timeframe) DO NOTHING;",
                            (t_candle, symbol, open_val, high_val, low_val, close_val, volume, vwap, tf)
                        )
                        
                        # Seed trend_state for 5m and 15m
                        ema_20 = close_val - Decimal("1.0")
                        database.execute_query(
                            "INSERT INTO trend_states (time, symbol, timeframe, trend, ema_20, close) "
                            "VALUES (%s, %s, %s, 'BULLISH', %s, %s) "
                            "ON CONFLICT (time, symbol, timeframe) DO NOTHING;",
                            (t_candle, symbol, tf, ema_20, close_val)
                        )
                
                # Seed trend_states and market_data for Daily and 1h so that multi-timeframe alignment finds BULLISH trends
                for tf in ["Daily", "1h"]:
                    interval_hours = 24 if tf == "Daily" else 1
                    for i in range(40, -1, -1):
                        t_candle = get_seeder_boundary(now - datetime.timedelta(hours=i * interval_hours), tf)
                        
                        price = base_price + Decimal(str((40 - i) * 0.1))
                        open_val = price - Decimal("0.2")
                        high_val = price + Decimal("0.5")
                        low_val = price - Decimal("0.3")
                        close_val = price
                        volume = 1000000 if symbol != "NIFTY 50" else 50000000
                        vwap = (open_val + high_val + low_val + close_val) / Decimal("4")
                        
                        database.execute_query(
                            "INSERT INTO market_data (time, symbol, open, high, low, close, volume, vwap, timeframe) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                            "ON CONFLICT (time, symbol, timeframe) DO NOTHING;",
                            (t_candle, symbol, open_val, high_val, low_val, close_val, volume, vwap, tf)
                        )
                        
                        ema_20 = close_val - Decimal("1.0")
                        database.execute_query(
                            "INSERT INTO trend_states (time, symbol, timeframe, trend, ema_20, close) "
                            "VALUES (%s, %s, %s, 'BULLISH', %s, %s) "
                            "ON CONFLICT (time, symbol, timeframe) DO NOTHING;",
                            (t_candle, symbol, tf, ema_20, close_val)
                        )
            print("[SEEDER] Seeded market_data and trend_states.")
    except Exception as e:
        print(f"[SEEDER] Error seeding market_data: {e}")

    # 5. Seed Order Blocks (for both 5m and 15m timeframes)
    try:
        res = database.execute_query("SELECT count(*) FROM order_block_memory;", fetch=True)
        if res[0][0] == 0:
            for symbol in symbols:
                for tf in ["5m", "15m"]:
                    database.execute_query(
                        "INSERT INTO order_block_memory (symbol, timeframe, ob_type, ob_high, ob_low, ob_midpoint, first_detected, test_count, held_count, broken) "
                        "VALUES (%s, %s, 'BULLISH', 151.0, 147.0, 149.0, %s, 3, 3, FALSE);",
                        (symbol, tf, now - datetime.timedelta(hours=2))
                    )
            print("[SEEDER] Seeded order block structures.")
    except Exception as e:
        print(f"[SEEDER] Error seeding order_block_memory: {e}")

    # 6. Seed Option Chains (options_data)
    try:
        res = database.execute_query("SELECT count(*) FROM options_data;", fetch=True)
        if res[0][0] == 0:
            expiry_date = today + datetime.timedelta(days=7)
            for symbol in symbols:
                for i in range(2):
                    t_option = now - datetime.timedelta(minutes=i * 15)
                    database.execute_query(
                        "INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp) "
                        "VALUES (%s, %s, 150.0, %s, 'CE', 300000, 50000, 10000, 0.15, 2.5) "
                        "ON CONFLICT DO NOTHING;",
                        (t_option, symbol, expiry_date)
                    )
                    database.execute_query(
                        "INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp) "
                        "VALUES (%s, %s, 150.0, %s, 'PE', 500000, 150000, 15000, 0.16, 1.8) "
                        "ON CONFLICT DO NOTHING;",
                        (t_option, symbol, expiry_date)
                    )
            print("[SEEDER] Seeded option chain details.")
    except Exception as e:
        print(f"[SEEDER] Error seeding options_data: {e}")

    # 7. Seed BOS Breaks in smc_structures (for both 5m and 15m timeframes)
    try:
        res = database.execute_query("SELECT count(*) FROM smc_structures;", fetch=True)
        if res[0][0] == 0:
            for symbol in symbols:
                for tf in ["5m", "15m"]:
                    database.execute_query(
                        "INSERT INTO smc_structures (time, symbol, timeframe, structure_type, direction, top_price, bottom_price) "
                        "VALUES (%s, %s, %s, 'BOS', 'BULLISH', 150.00, 145.00) "
                        "ON CONFLICT DO NOTHING;",
                        (now - datetime.timedelta(minutes=10), symbol, tf)
                    )
            print("[SEEDER] Seeded smc_structures (BOS Bullish Breaks).")
    except Exception as e:
        print(f"[SEEDER] Error seeding smc_structures: {e}")
        
    print("[SEEDER] Database seeding successfully complete.")
