import datetime
from decimal import Decimal
import database
from config import Config
from risk_gates.gate_validator import GateValidator
from risk_gates.position_sizer import PositionSizer
from backtesting.backtest_runner import BacktestRunner

def setup_clean_db():
    database.init_db("schema.sql")

def verify_gates():
    print("=== Verification of Phase 7 Gates ===")
    
    # Initialize basic daily state for testing
    state = {
        "hard_stop_active": False,
        "consecutive_losses": 0,
        "daily_risk_used": Decimal("0.0")
    }
    
    gates_test_cases = [
        # 1. Liquidity Gate
        {
            "name": "1. Liquidity Gate (Low ADTV)",
            "context": {"adtv": Decimal("400000000"), "spread_pct": Decimal("0.0010"), "rvol": Decimal("1.5")},
            "expected": "BLOCK_LIQUIDITY_ADTV"
        },
        {
            "name": "1. Liquidity Gate (High Spread)",
            "context": {"adtv": Decimal("600000000"), "spread_pct": Decimal("0.0025"), "rvol": Decimal("1.5")},
            "expected": "BLOCK_LIQUIDITY_SPREAD"
        },
        {
            "name": "1. Liquidity Gate (Low RVOL)",
            "context": {"adtv": Decimal("600000000"), "spread_pct": Decimal("0.0010"), "rvol": Decimal("0.8")},
            "expected": "BLOCK_LIQUIDITY_RVOL"
        },
        # 2. SMC Validation Gate
        {
            "name": "2. SMC Validation Gate (Failed)",
            "context": {"smc_confirmed": False},
            "expected": "BLOCK_SMC_VALIDATION"
        },
        # 3. Correlation Gate
        {
            "name": "3. Correlation Gate (High Sector Exposure)",
            "context": {"sector_alerts_last_30m": 2},
            "expected": "BLOCK_CORRELATION_SECTOR"
        },
        {
            "name": "3. Correlation Gate (High Total Active Exposure)",
            "context": {"total_active_alerts": 4},
            "expected": "BLOCK_CORRELATION_TOTAL"
        },
        # 4. Earnings Gate
        {
            "name": "4. Earnings Gate (Upcoming Earnings)",
            "context": {"earnings_within_24h": True},
            "expected": "BLOCK_EARNINGS_RISK"
        },
        # 5. Event Risk Gate
        {
            "name": "5. Event Risk Gate (Macro Event Approaching)",
            "context": {"minutes_to_next_macro_event": 10},
            "expected": "BLOCK_EVENT_RISK"
        },
        {
            "name": "5. Event Risk Gate (Macro Event Recently Passed)",
            "context": {"minutes_since_last_macro_event": 12},
            "expected": "BLOCK_EVENT_RISK"
        },
        # 6. Choppy Filter Gate
        {
            "name": "6. Choppy Filter Gate (All Choppy conditions met)",
            "context": {
                "nifty_adx": 18.0,
                "nifty_ad_ratio": 1.0,
                "nifty_inside_atr_30m": True
            },
            "expected": "BLOCK_CHOPPY_MARKET"
        },
        # 7. Circuit Breaker Gate
        {
            "name": "7. Circuit Breaker Gate (Nifty flash move)",
            "context": {"nifty_15m_move_pct": 1.7},
            "expected": "BLOCK_CIRCUIT_BREAKER"
        },
        # 8. Volatility Regime Gate (ATR Pause)
        {
            "name": "8. Volatility Regime Gate (Nifty ATR surge)",
            "context": {"nifty_atr_vs_30day_ratio": 1.6},
            "expected": "BLOCK_ATR_VOLATILITY"
        }
    ]
    
    for tc in gates_test_cases:
        passed, actual = GateValidator.validate_gates(
            symbol="RELIANCE",
            target_risk_pct=Decimal("0.5"),
            current_state=state,
            has_duplicate=False,
            market_context=tc["context"]
        )
        status = "Pass" if actual == tc["expected"] else "Fail"
        print(f"Gate: {tc['name']}")
        print(f"  Input Context : {tc['context']}")
        print(f"  Expected      : {tc['expected']}")
        print(f"  Actual        : {actual}")
        print(f"  Verification  : {status}\n")

    # 9. Volatility Regime Gate (VIX position size reduction)
    print("=== Volatility Regime Gate: VIX Position Sizing Adjustment ===")
    
    # Case A: VIX = 14 (No size reduction -> 100%)
    res_vix_14 = PositionSizer.calculate_size(
        entry_low=Decimal("100.0"),
        entry_high=Decimal("102.0"),
        stop_loss=Decimal("99.0"),
        direction="LONG",
        india_vix=14.0
    )
    
    # Case B: VIX = 22 (Reduce position by 50%)
    res_vix_22 = PositionSizer.calculate_size(
        entry_low=Decimal("100.0"),
        entry_high=Decimal("102.0"),
        stop_loss=Decimal("99.0"),
        direction="LONG",
        india_vix=22.0
    )
    
    vix_reduction_status = "Pass" if res_vix_22["quantity"] == res_vix_14["quantity"] // 2 else "Fail"
    
    print(f"VIX 14.0 Sizing (Normal)   : Quantity = {res_vix_14['quantity']}, Risk = {res_vix_14['risk_amount']}")
    print(f"VIX 22.0 Sizing (Reduced)  : Quantity = {res_vix_22['quantity']}, Risk = {res_vix_22['risk_amount']}")
    print(f"Verification Check         : {vix_reduction_status}\n")

def run_backtest_verification():
    print("=== Run 90-Day Backtest and Performance Metrics ===")
    setup_clean_db()
    
    # Run Backtest
    perf = BacktestRunner.run_90_day_backtest()
    
    # Validate criteria
    win_rate_ok = perf["win_rate"] > 45.0
    profit_factor_ok = perf["profit_factor"] > 1.5
    drawdown_ok = perf["max_drawdown"] < 15.0
    
    print("\n=== Validation Against Criteria ===")
    print(f"Win Rate (>45%)      : {perf['win_rate']}% -> {'PASS' if win_rate_ok else 'FAIL'}")
    print(f"Profit Factor (>1.5) : {perf['profit_factor']} -> {'PASS' if profit_factor_ok else 'FAIL'}")
    print(f"Max Drawdown (<15%)  : {perf['max_drawdown']}% -> {'PASS' if drawdown_ok else 'FAIL'}")
    
    overall = "PASS" if (win_rate_ok and profit_factor_ok and drawdown_ok) else "FAIL"
    print(f"\nOverall Backtest Validation: {overall}")

if __name__ == "__main__":
    verify_gates()
    run_backtest_verification()
