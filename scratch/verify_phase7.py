import datetime
import asyncio
import time
from decimal import Decimal
import database
from config import Config
from risk_gates.position_sizer import PositionSizer
from risk_gates.risk_grader import RiskGrader
from risk_gates.gate_validator import GateValidator
from risk_gates.persistence import RiskPersistence
from risk_gates.recovery_manager import RiskRecoveryManager
from risk_gates.risk_engine import RiskEngine
from market_data.instrument_loader import InstrumentLoader

def setup_clean_db():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM signals;")
    database.execute_query("DELETE FROM risk_state;")
    database.execute_query("DELETE FROM latency_metrics;")

def run_risk_gates_verification():
    print("=== Phase 7 Risk Gates Engine Verification ===")
    setup_clean_db()
    
    session_date = datetime.date(2026, 6, 15)
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # --- A. Position Sizing Verification ---
    print("\nA. Position Sizing Examples")
    print("--------------------------")
    # Long Setup
    # Entry Zone: 100 to 102 (Avg = 101), SL: 99. Target Risk: 5000 (0.5% of 1,000,000)
    # Expected Qty: 5000 / 2 = 2500
    long_res = PositionSizer.calculate_size(
        entry_low=Decimal("100.0"),
        entry_high=Decimal("102.0"),
        stop_loss=Decimal("99.0"),
        direction="LONG"
    )
    print(f"LONG Setup:")
    print(f"  Entry Zone : 100.0 - 102.0 (Avg: {long_res['entry_avg']})")
    print(f"  Stop Loss  : 99.0")
    print(f"  Capital    : {Config.CAPITAL}, Risk Pct: {Config.RISK_PCT}%")
    print(f"  Target Risk: {long_res['risk_amount']}")
    print(f"  Calculated Quantity: {long_res['quantity']}")
    
    # Short Setup
    # Entry Zone: 100 to 102 (Avg = 101), SL: 104. Target Risk: 5000 (0.5% of 1,000,000)
    # Expected Qty: 5000 / 3 = 1666
    short_res = PositionSizer.calculate_size(
        entry_low=Decimal("100.0"),
        entry_high=Decimal("102.0"),
        stop_loss=Decimal("104.0"),
        direction="SHORT"
    )
    print(f"SHORT Setup:")
    print(f"  Entry Zone : 100.0 - 102.0 (Avg: {short_res['entry_avg']})")
    print(f"  Stop Loss  : 104.0")
    print(f"  Capital    : {Config.CAPITAL}, Risk Pct: {Config.RISK_PCT}%")
    print(f"  Target Risk: {short_res['risk_amount']}")
    print(f"  Calculated Quantity: {short_res['quantity']}")

    # --- B. Risk Grading Verification ---
    print("\nB. Risk Grading Rules")
    print("---------------------")
    scores = [Decimal("96.5"), Decimal("92.0"), Decimal("87.5"), Decimal("84.0")]
    for s in scores:
        grade = RiskGrader.get_grade(s)
        print(f"  Composite Score: {s} -> Risk Grade: {grade}")

    # --- C. Sequential Verification Gates ---
    print("\nC. Sequential Verification Gates")
    print("--------------------------------")
    
    # Initialize fresh risk state
    RiskPersistence.save_risk_state(session_date, Decimal("0.0"), 0, False)
    
    # 1. Gate 1: Hard Stop Gate
    state_hard_stop = {
        "daily_risk_used": Decimal("0.0"),
        "consecutive_losses": 0,
        "hard_stop_active": True
    }
    passed, code = GateValidator.validate_gates("SBIN", Decimal("0.5"), state_hard_stop, False)
    print(f"  Gate 1 (Hard Stop Active=True): Passed={passed}, Code={code}")

    # 2. Gate 2: Daily Risk Limit Gate
    # Max daily risk = 2.0%. Already used 1.6%. New trade risk = 0.5% (Total 2.1%)
    state_daily_limit = {
        "daily_risk_used": Decimal("1.6"),
        "consecutive_losses": 0,
        "hard_stop_active": False
    }
    passed, code = GateValidator.validate_gates("SBIN", Decimal("0.5"), state_daily_limit, False)
    print(f"  Gate 2 (Daily Risk Used=1.6%, New=0.5%): Passed={passed}, Code={code}")

    # 3. Gate 3: Duplicate Signal Gate
    state_dup = {
        "daily_risk_used": Decimal("0.0"),
        "consecutive_losses": 0,
        "hard_stop_active": False
    }
    passed, code = GateValidator.validate_gates("SBIN", Decimal("0.5"), state_dup, True)
    print(f"  Gate 3 (Duplicate Signal=True): Passed={passed}, Code={code}")

    # 4. Gate 4: Consecutive Losses Gate
    state_losses = {
        "daily_risk_used": Decimal("0.0"),
        "consecutive_losses": 3,
        "hard_stop_active": False
    }
    passed, code = GateValidator.validate_gates("SBIN", Decimal("0.5"), state_losses, False)
    print(f"  Gate 4 (Consecutive Losses=3): Passed={passed}, Code={code}, State Hard Stop Active={state_losses['hard_stop_active']}")

    # --- D. Trade Outcome & Database Persistence ---
    print("\nD. Trade Outcome and Persistence")
    print("---------------------------------")
    engine = RiskEngine()
    
    # Reset State in DB
    RiskPersistence.save_risk_state(session_date, Decimal("0.0"), 0, False)
    print("  Initial state saved.")
    
    # Process 1st Loss
    engine.record_trade_outcome(session_date, "HIT_SL")
    state = RiskPersistence.load_risk_state(session_date)
    print(f"  After 1st Loss  -> Consecutive Losses: {state['consecutive_losses']}, Hard Stop Active: {state['hard_stop_active']}")
    
    # Process 2nd Loss
    engine.record_trade_outcome(session_date, "HIT_SL")
    state = RiskPersistence.load_risk_state(session_date)
    print(f"  After 2nd Loss  -> Consecutive Losses: {state['consecutive_losses']}, Hard Stop Active: {state['hard_stop_active']}")
    
    # Process 3rd Loss
    engine.record_trade_outcome(session_date, "HIT_SL")
    state = RiskPersistence.load_risk_state(session_date)
    print(f"  After 3rd Loss  -> Consecutive Losses: {state['consecutive_losses']}, Hard Stop Active: {state['hard_stop_active']}")
    
    # Reset via profit
    engine.record_trade_outcome(session_date, "HIT_T1")
    state = RiskPersistence.load_risk_state(session_date)
    print(f"  After Hit Target 1 -> Consecutive Losses: {state['consecutive_losses']}, Hard Stop Active: {state['hard_stop_active']}")

async def run_concurrent_nifty_load():
    print("\nE. Concurrent NIFTY 50 Load & Telemetry")
    print("---------------------------------------")
    loader = InstrumentLoader()
    symbols = loader.symbols
    t = datetime.datetime.now()
    engine = RiskEngine()
    
    # Re-reset the state in database so we can pass
    RiskPersistence.save_risk_state(t.date(), Decimal("0.0"), 0, False)
    
    async def process_signal_async(symbol, idx):
        return engine.process_signal(
            signal_id=f"SIG_V_{idx}",
            timestamp=t,
            symbol=symbol,
            direction="LONG",
            score=Decimal("92.5"),
            confidence="HIGH",
            regime="BULLISH",
            entry_low=Decimal("100.0"),
            entry_high=Decimal("102.0"),
            stop_loss=Decimal("99.0"),
            target_1=Decimal("105.0"),
            target_2=Decimal("110.0"),
            valid_until=t + datetime.timedelta(hours=1)
        )
        
    start_time = time.perf_counter()
    results = await asyncio.gather(*(process_signal_async(sym, i) for i, sym in enumerate(symbols)))
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    avg_latency = elapsed_ms / len(symbols)
    
    accepted_count = sum(1 for r in results if r["is_accepted"])
    rejected_count = sum(1 for r in results if not r["is_accepted"])
    
    print(f"Processed all {len(symbols)} NIFTY symbols concurrently.")
    print(f"Total Execution Time: {elapsed_ms:.2f}ms")
    print(f"Average Latency: {avg_latency:.2f}ms per symbol (Required < 50ms)")
    print(f"Accepted: {accepted_count}, Rejected: {rejected_count}")
    
    # Check if they failed due to Daily Risk Limit (Gate 2)
    rejection_reasons = {}
    for r in results:
        if not r["is_accepted"]:
            code = r["status_code"]
            rejection_reasons[code] = rejection_reasons.get(code, 0) + 1
    
    if rejection_reasons:
        print(f"Rejection breakdown: {rejection_reasons}")
        
    # Check Telemetry Table
    res = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'RISK_GATES';", fetch=True)
    print(f"Telemetry entries recorded in DB: {res[0][0]} rows")

if __name__ == "__main__":
    run_risk_gates_verification()
    asyncio.run(run_concurrent_nifty_load())
