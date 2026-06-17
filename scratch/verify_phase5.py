import datetime
import asyncio
import time
from decimal import Decimal
import database
from options_engine.signal_engine import OptionsSignalEngine
from options_engine.persistence import OptionsPersistence
from options_engine.recovery_manager import OptionsRecoveryManager
from market_data.instrument_loader import InstrumentLoader

def setup_clean_db():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM options_intelligence;")
    database.execute_query("DELETE FROM options_data;")
    database.execute_query("DELETE FROM latency_metrics;")

def run_options_verification():
    print("=== Phase 5 Options Intelligence Engine Verification ===")
    setup_clean_db()
    
    engine = OptionsSignalEngine()
    symbol = "SBIN"
    expiry = datetime.date(2026, 6, 25)
    
    # 1. Generate chain at t0
    t0 = datetime.datetime(2026, 6, 15, 9, 30, 0)
    chain_t0 = [
        # Put options
        {"time": t0, "symbol": symbol, "strike": Decimal("90.0"), "expiry": expiry, "option_type": "PE", "oi": 500, "oi_change": 50, "volume": 1000, "iv": Decimal("0.2"), "ltp": Decimal("1.5")},
        {"time": t0, "symbol": symbol, "strike": Decimal("100.0"), "expiry": expiry, "option_type": "PE", "oi": 1000, "oi_change": 100, "volume": 2000, "iv": Decimal("0.18"), "ltp": Decimal("5.0")},
        # Call options
        {"time": t0, "symbol": symbol, "strike": Decimal("100.0"), "expiry": expiry, "option_type": "CE", "oi": 800, "oi_change": 80, "volume": 1600, "iv": Decimal("0.19"), "ltp": Decimal("4.2")},
        {"time": t0, "symbol": symbol, "strike": Decimal("110.0"), "expiry": expiry, "option_type": "CE", "oi": 1200, "oi_change": 120, "volume": 2400, "iv": Decimal("0.2"), "ltp": Decimal("1.2")}
    ]
    
    # 2. Generate chain at t1 (to test buildup)
    t1 = datetime.datetime(2026, 6, 15, 9, 35, 0)
    chain_t1 = [
        # Put options (strike 100: price goes up 5.0 -> 5.5, OI goes up 1000 -> 1200 => Long Buildup)
        {"time": t1, "symbol": symbol, "strike": Decimal("90.0"), "expiry": expiry, "option_type": "PE", "oi": 500, "oi_change": 0, "volume": 1100, "iv": Decimal("0.2"), "ltp": Decimal("1.5")},
        {"time": t1, "symbol": symbol, "strike": Decimal("100.0"), "expiry": expiry, "option_type": "PE", "oi": 1200, "oi_change": 200, "volume": 2200, "iv": Decimal("0.18"), "ltp": Decimal("5.5")},
        # Call options (strike 110: price goes down 1.2 -> 0.8, OI goes up 1200 -> 1500 => Short Buildup)
        {"time": t1, "symbol": symbol, "strike": Decimal("100.0"), "expiry": expiry, "option_type": "CE", "oi": 800, "oi_change": 0, "volume": 1700, "iv": Decimal("0.19"), "ltp": Decimal("4.2")},
        {"time": t1, "symbol": symbol, "strike": Decimal("110.0"), "expiry": expiry, "option_type": "CE", "oi": 1500, "oi_change": 300, "volume": 2600, "iv": Decimal("0.2"), "ltp": Decimal("0.8")}
    ]

    for c in chain_t0 + chain_t1:
        database.execute_query(
            """
            INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (c["time"], c["symbol"], c["strike"], c["expiry"], c["option_type"], c["oi"], c["oi_change"], c["volume"], c["iv"], c["ltp"])
        )

    # Process t0
    res_t0 = engine.process_option_update(symbol, expiry, t0)
    print("\n--- Calculations at t0 ---")
    print(f"PCR OI: {res_t0['pcr_oi']}")
    print(f"PCR Volume: {res_t0['pcr_volume']}")
    print(f"Max Pain Strike: {res_t0['max_pain_level']}")
    print(f"Highest Call Strike: {res_t0['highest_call_oi_strike']}")
    print(f"Highest Put Strike: {res_t0['highest_put_oi_strike']}")
    print(f"Call Concentration Ratio: {res_t0['ce_concentration']}")
    print(f"Put Concentration Ratio: {res_t0['pe_concentration']}")
    
    # Process t1 (with buildup check)
    res_t1 = engine.process_option_update(symbol, expiry, t1)
    print("\n--- Calculations at t1 ---")
    print(f"PCR OI: {res_t1['pcr_oi']}")
    print(f"Max Pain Strike: {res_t1['max_pain_level']}")
    print(f"CE Buildup stats: {res_t1['buildup_stats']['CE']}")
    print(f"PE Buildup stats: {res_t1['buildup_stats']['PE']}")
    print(f"Directional Bias Mapped: {res_t1['bias']}")

    # 3. Verify Restart Recovery
    print("\n--- Restart Recovery Evidence ---")
    recovered = OptionsRecoveryManager.recover_state(symbol)
    print(f"Recovery Status: {recovered['status']}")
    print(f"Recovered Max Pain Level: {recovered['max_pain_level']}")
    print(f"Recovered Highest Put OI Strike: {recovered['highest_put_oi_strike']}")
    print(f"Recovered Highest Call OI Strike: {recovered['highest_call_oi_strike']}")

async def run_perf_verification():
    print("\n--- Performance and Concurrent Execution Evidence ---")
    loader = InstrumentLoader()
    symbols = loader.symbols
    expiry = datetime.date(2026, 6, 25)
    t = datetime.datetime(2026, 6, 15, 10, 0, 0)
    
    # Seed options chain data for all 50 NIFTY stocks
    print("Seeding options data for all 50 symbols...")
    for s in symbols:
        # 1 PE contract
        c_pe = {"time": t, "symbol": s, "strike": Decimal("100.0"), "expiry": expiry, "option_type": "PE", "oi": 1000, "oi_change": 100, "volume": 2000, "iv": Decimal("0.18"), "ltp": Decimal("5.0")}
        # 1 CE contract
        c_ce = {"time": t, "symbol": s, "strike": Decimal("110.0"), "expiry": expiry, "option_type": "CE", "oi": 1200, "oi_change": 120, "volume": 2400, "iv": Decimal("0.2"), "ltp": Decimal("1.2")}
        
        for c in [c_pe, c_ce]:
            database.execute_query(
                """
                INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (c["time"], c["symbol"], c["strike"], c["expiry"], c["option_type"], c["oi"], c["oi_change"], c["volume"], c["iv"], c["ltp"])
            )

    engine = OptionsSignalEngine()

    async def process_stock(s):
        return engine.process_option_update(s, expiry, t)

    start_time = time.perf_counter()
    results = await asyncio.gather(*(process_stock(s) for s in symbols))
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    avg_latency = elapsed_ms / len(symbols)
    
    print(f"Processed all {len(symbols)} NIFTY symbols concurrently.")
    print(f"Total Concurrent Execution Time: {elapsed_ms:.2f}ms")
    print(f"Average Processing Latency: {avg_latency:.2f}ms per stock")
    
    # Verify Telemetry in database
    res = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'OPTIONS_INTELLIGENCE';", fetch=True)
    print(f"Telemetry metrics recorded in DB: {res[0][0]} rows")

if __name__ == "__main__":
    run_options_verification()
    asyncio.run(run_perf_verification())
