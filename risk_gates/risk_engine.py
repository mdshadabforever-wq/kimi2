import datetime
import time
from decimal import Decimal
from config import Config
from risk_gates.position_sizer import PositionSizer
from risk_gates.risk_grader import RiskGrader
from risk_gates.gate_validator import GateValidator
from risk_gates.persistence import RiskPersistence
from risk_gates.recovery_manager import RiskRecoveryManager
from risk_gates.telemetry import RiskTelemetry

class RiskEngine:
    def __init__(self):
        pass

    def process_signal(
        self,
        signal_id: str,
        timestamp: datetime.datetime,
        symbol: str,
        direction: str,
        score: Decimal,
        confidence: str,
        regime: str,
        entry_low: Decimal,
        entry_high: Decimal,
        stop_loss: Decimal,
        target_1: Decimal,
        target_2: Decimal,
        valid_until: datetime.datetime,
        market_context: dict = None
    ) -> dict:
        """Processes and validates an incoming signal through position sizing, grading, and risk gates."""
        start_time = time.perf_counter()
        session_date = timestamp.date()

        # 1. Recover or initialize risk state for today
        state = RiskRecoveryManager.recover_risk_state(session_date)

        # 2. Check for duplicate active signal
        has_duplicate = RiskPersistence.has_active_signal(symbol, timestamp)

        # 3. Calculate quantity and risk size
        vix = float(market_context.get("india_vix", 14.0)) if market_context else 14.0
        sizer_res = PositionSizer.calculate_size(
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop_loss,
            direction=direction,
            india_vix=vix,
            enable_cap=True
        )
        qty = sizer_res["quantity"]
        risk_amt = sizer_res["risk_amount"]

        # 4. Grade the risk
        arc_premarket = market_context.get("arc_premarket", "APPROVE") if market_context else "APPROVE"
        has_caution = (confidence == "LOW") or (arc_premarket == "CAUTION")
        big_money_score = float(market_context.get("big_money_score", 0.0)) if market_context else 0.0
        grade = RiskGrader.get_grade(
            score=score,
            has_caution=has_caution,
            big_money_score=big_money_score
        )

        # 5. Run Gates Validation
        target_risk_pct = Decimal(str(Config.RISK_PCT))
        is_passed, status_code = GateValidator.validate_gates(
            symbol=symbol,
            target_risk_pct=target_risk_pct,
            current_state=state,
            has_duplicate=has_duplicate,
            market_context=market_context
        )

        if is_passed:
            # Update state with risk used
            state["daily_risk_used"] += target_risk_pct
            state["total_signals"] += 1
            
            # Save updated state
            RiskPersistence.save_risk_state(
                session_date=session_date,
                daily_risk_used=state["daily_risk_used"],
                consecutive_losses=state["consecutive_losses"],
                hard_stop_active=state["hard_stop_active"],
                total_signals=state["total_signals"],
                signals_hit_sl=state["signals_hit_sl"],
                signals_hit_t1=state["signals_hit_t1"],
                signals_hit_t2=state["signals_hit_t2"]
            )
            
            # Save signal as ACTIVE
            RiskPersistence.save_signal(
                signal_id=signal_id,
                timestamp=timestamp,
                symbol=symbol,
                direction=direction,
                score=score,
                confidence=confidence,
                regime=regime,
                entry_low=entry_low,
                entry_high=entry_high,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                quantity=qty,
                risk_amount=risk_amt,
                risk_grade=grade,
                valid_until=valid_until,
                status="ACTIVE"
            )
        else:
            # Save state in case consecutive losses gate activated hard stop
            RiskPersistence.save_risk_state(
                session_date=session_date,
                daily_risk_used=state["daily_risk_used"],
                consecutive_losses=state["consecutive_losses"],
                hard_stop_active=state["hard_stop_active"],
                total_signals=state["total_signals"],
                signals_hit_sl=state["signals_hit_sl"],
                signals_hit_t1=state["signals_hit_t1"],
                signals_hit_t2=state["signals_hit_t2"]
            )
            
            # Save signal as CANCELLED
            RiskPersistence.save_signal(
                signal_id=signal_id,
                timestamp=timestamp,
                symbol=symbol,
                direction=direction,
                score=score,
                confidence=confidence,
                regime=regime,
                entry_low=entry_low,
                entry_high=entry_high,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                quantity=0,
                risk_amount=Decimal("0.0"),
                risk_grade="F",
                valid_until=valid_until,
                status="CANCELLED"
            )

        # 6. Record Latency Telemetry
        duration_ms = (time.perf_counter() - start_time) * 1000
        RiskTelemetry.record_latency(symbol, duration_ms)

        return {
            "signal_id": signal_id,
            "is_accepted": is_passed,
            "status_code": status_code,
            "quantity": qty,
            "risk_amount": risk_amt,
            "risk_grade": grade if is_passed else "F",
            "risk_state": state
        }

    def record_trade_outcome(self, session_date: datetime.date, outcome: str):
        """Processes trade results to update daily stats and manage hard stops on consecutive losses."""
        state = RiskRecoveryManager.recover_risk_state(session_date)
        
        if outcome == "HIT_SL":
            state["consecutive_losses"] += 1
            state["signals_hit_sl"] += 1
            if state["consecutive_losses"] >= Config.HARD_STOP_LOSSES:
                state["hard_stop_active"] = True
        elif outcome in ("HIT_T1", "HIT_T2"):
            # Success outcome resets consecutive losses
            state["consecutive_losses"] = 0
            if outcome == "HIT_T1":
                state["signals_hit_t1"] += 1
            else:
                state["signals_hit_t2"] += 1
                
        # Save updated stats
        RiskPersistence.save_risk_state(
            session_date=session_date,
            daily_risk_used=state["daily_risk_used"],
            consecutive_losses=state["consecutive_losses"],
            hard_stop_active=state["hard_stop_active"],
            total_signals=state["total_signals"],
            signals_hit_sl=state["signals_hit_sl"],
            signals_hit_t1=state["signals_hit_t1"],
            signals_hit_t2=state["signals_hit_t2"]
        )
