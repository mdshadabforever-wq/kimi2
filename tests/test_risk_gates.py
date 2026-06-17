import datetime
import pytest
import asyncio
from decimal import Decimal
import database
from config import Config
from risk_gates.position_sizer import PositionSizer
from risk_gates.risk_grader import RiskGrader
from risk_gates.gate_validator import GateValidator
from risk_gates.persistence import RiskPersistence
from risk_gates.recovery_manager import RiskRecoveryManager
from risk_gates.telemetry import RiskTelemetry
from risk_gates.risk_engine import RiskEngine
from market_data.instrument_loader import InstrumentLoader

@pytest.fixture(scope="module", autouse=True)
def setup_database_schema():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM signals;")
    database.execute_query("DELETE FROM risk_state;")
    database.execute_query("DELETE FROM latency_metrics;")

def test_position_sizing():
    """1. Test dynamic position sizing calculation."""
    # Sizing for LONG
    # Capital = 1,000,000, Risk = 0.5% -> Target Risk = 5000
    # Entry: (100 + 102) / 2 = 101
    # SL: 99
    # Distance = 2.0
    # Expected Qty = 5000 / 2 = 2500
    res = PositionSizer.calculate_size(
        entry_low=Decimal("100.0"),
        entry_high=Decimal("102.0"),
        stop_loss=Decimal("99.0"),
        direction="LONG"
    )
    assert res["quantity"] == 2500
    assert res["risk_amount"] == Decimal("5000.0")

def test_risk_grading():
    """2. Test risk grading rules."""
    assert RiskGrader.get_grade(Decimal("96.5")) == "A+"
    assert RiskGrader.get_grade(Decimal("92.0")) == "A"
    assert RiskGrader.get_grade(Decimal("87.5")) == "B+"
    assert RiskGrader.get_grade(Decimal("86.0")) == "B"
    assert RiskGrader.get_grade(Decimal("84.0")) == "F"

    # Test Big Money Upgrades
    assert RiskGrader.get_grade(Decimal("86.0"), big_money_score=80.0) == "B+"
    assert RiskGrader.get_grade(Decimal("87.5"), big_money_score=80.0) == "A"
    assert RiskGrader.get_grade(Decimal("92.0"), big_money_score=80.0) == "A+"
    assert RiskGrader.get_grade(Decimal("96.5"), big_money_score=80.0) == "A+"

    # Test Caution Flag
    assert RiskGrader.get_grade(Decimal("96.5"), has_caution=True) == "C"


def test_hard_stop_gate():
    """3. Test Gate 1: Hard Stop Gate."""
    current_state = {
        "daily_risk_used": Decimal("0.0"),
        "consecutive_losses": 0,
        "hard_stop_active": True
    }
    is_passed, status = GateValidator.validate_gates("SBIN", Decimal("0.5"), current_state, False)
    assert is_passed is False
    assert status == "BLOCK_HARD_STOP"

def test_daily_risk_limit_gate():
    """4. Test Gate 2: Daily Risk Limit Gate."""
    # Max daily risk = 2.0%
    # If 1.6% is already used, adding a new 0.5% trade should exceed 2.0% and fail
    current_state = {
        "daily_risk_used": Decimal("1.6"),
        "consecutive_losses": 0,
        "hard_stop_active": False
    }
    is_passed, status = GateValidator.validate_gates("SBIN", Decimal("0.5"), current_state, False)
    assert is_passed is False
    assert status == "BLOCK_DAILY_RISK_LIMIT"

def test_duplicate_signal_gate():
    """5. Test Gate 3: Duplicate Signal Gate."""
    current_state = {
        "daily_risk_used": Decimal("0.0"),
        "consecutive_losses": 0,
        "hard_stop_active": False
    }
    is_passed, status = GateValidator.validate_gates("SBIN", Decimal("0.5"), current_state, True)
    assert is_passed is False
    assert status == "BLOCK_DUPLICATE_SIGNAL"

def test_consecutive_losses_gate():
    """6. Test Gate 4: Consecutive Losses Gate."""
    # Hard stop losses = 3.
    # If consecutive_losses = 3, GateValidator should mark hard_stop_active=True and FAIL
    current_state = {
        "daily_risk_used": Decimal("0.0"),
        "consecutive_losses": 3,
        "hard_stop_active": False
    }
    is_passed, status = GateValidator.validate_gates("SBIN", Decimal("0.5"), current_state, False)
    assert is_passed is False
    assert status == "BLOCK_CONSECUTIVE_LOSSES"
    assert current_state["hard_stop_active"] is True

def test_risk_persistence_and_recovery():
    """7 & 8. Test persistence and recovery of risk states."""
    session_date = datetime.date(2026, 6, 15)
    database.execute_query("DELETE FROM risk_state WHERE session_date = %s;", (session_date,))
    
    # Re-verify clean startup initialization
    state = RiskRecoveryManager.recover_risk_state(session_date)
    assert state["session_date"] == session_date
    assert state["daily_risk_used"] == Decimal("0.0")
    assert state["hard_stop_active"] is False
    
    # Modify and Save
    RiskPersistence.save_risk_state(
        session_date=session_date,
        daily_risk_used=Decimal("1.0"),
        consecutive_losses=1,
        hard_stop_active=False
    )
    
    # Reload
    state_reload = RiskRecoveryManager.recover_risk_state(session_date)
    assert state_reload["daily_risk_used"] == Decimal("1.0")
    assert state_reload["consecutive_losses"] == 1

def test_record_trade_outcome_losses():
    """9. Test consecutive losses increment and hard stop activation."""
    engine = RiskEngine()
    session_date = datetime.date(2026, 6, 15)
    
    # Reset state
    RiskPersistence.save_risk_state(session_date, Decimal("0.0"), 0, False)
    
    # 1st Loss
    engine.record_trade_outcome(session_date, "HIT_SL")
    state = RiskPersistence.load_risk_state(session_date)
    assert state["consecutive_losses"] == 1
    assert state["hard_stop_active"] is False
    
    # 2nd Loss
    engine.record_trade_outcome(session_date, "HIT_SL")
    state = RiskPersistence.load_risk_state(session_date)
    assert state["consecutive_losses"] == 2
    assert state["hard_stop_active"] is False
    
    # 3rd Loss -> Hard Stop triggers
    engine.record_trade_outcome(session_date, "HIT_SL")
    state = RiskPersistence.load_risk_state(session_date)
    assert state["consecutive_losses"] == 3
    assert state["hard_stop_active"] is True
    
    # Profit resets consecutive losses
    engine.record_trade_outcome(session_date, "HIT_T1")
    state = RiskPersistence.load_risk_state(session_date)
    assert state["consecutive_losses"] == 0

def test_risk_engine_signals_rejection():
    """10. Test entire signal validation cycle and database saving."""
    engine = RiskEngine()
    symbol = "INFY"
    t = datetime.datetime(2026, 6, 15, 12, 0, 0)
    
    # Reset risk state to isolate from other tests
    RiskPersistence.save_risk_state(t.date(), Decimal("0.0"), 0, False)
    
    # Seed duplicate active signal
    RiskPersistence.save_signal(
        signal_id="SIG_DUP_1",
        timestamp=t,
        symbol=symbol,
        direction="LONG",
        score=Decimal("91.0"),
        confidence="HIGH",
        regime="BULLISH",
        entry_low=Decimal("100.0"),
        entry_high=Decimal("102.0"),
        stop_loss=Decimal("99.0"),
        target_1=Decimal("105.0"),
        target_2=Decimal("110.0"),
        quantity=2500,
        risk_amount=Decimal("5000.0"),
        risk_grade="B",
        valid_until=t + datetime.timedelta(hours=1),
        status="ACTIVE"
    )
    
    # Process signal for duplicate stock -> Rejects it
    res = engine.process_signal(
        signal_id="SIG_NEW_1",
        timestamp=t,
        symbol=symbol,
        direction="LONG",
        score=Decimal("91.0"),
        confidence="HIGH",
        regime="BULLISH",
        entry_low=Decimal("100.0"),
        entry_high=Decimal("102.0"),
        stop_loss=Decimal("99.0"),
        target_1=Decimal("105.0"),
        target_2=Decimal("110.0"),
        valid_until=t + datetime.timedelta(hours=1)
    )
    
    assert res["is_accepted"] is False
    assert res["status_code"] == "BLOCK_DUPLICATE_SIGNAL"

def test_nifty_50_loader():
    """11. Test loader constituents."""
    loader = InstrumentLoader()
    symbols = loader.symbols
    assert len(symbols) == 50

@pytest.mark.asyncio
async def test_concurrent_execution_and_telemetry():
    """12. Test concurrent signals validation and latency telemetries."""
    engine = RiskEngine()
    symbols = ["RELIANCE", "TCS", "INFY", "SBIN", "ICICIBANK"]
    t = datetime.datetime(2026, 6, 15, 16, 0, 0)
    
    database.execute_query("DELETE FROM signals;")
    database.execute_query("DELETE FROM latency_metrics;")
    
    async def run_signal(s, idx):
        return engine.process_signal(
            signal_id=f"SIG_CONCUR_{idx}",
            timestamp=t,
            symbol=s,
            direction="LONG",
            score=Decimal("90.0"),
            confidence="HIGH",
            regime="BULLISH",
            entry_low=Decimal("100.0"),
            entry_high=Decimal("102.0"),
            stop_loss=Decimal("99.0"),
            target_1=Decimal("105.0"),
            target_2=Decimal("110.0"),
            valid_until=t + datetime.timedelta(hours=1)
        )
        
    results = await asyncio.gather(*(run_signal(sym, i) for i, sym in enumerate(symbols)))
    
    assert len(results) == len(symbols)
    # Check that telemetry recorded rows
    metrics_count = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'RISK_GATES';", fetch=True)
    assert metrics_count[0][0] == len(symbols)
