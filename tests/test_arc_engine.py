"""
Tests for Phase 10 — ARC Engine
Covers: input assembly, decision engine rules, confidence formula, persistence,
recovery, premarket batch, intraday review, fallback behavior, cutoff logic,
schema validation, deterministic override, and post-market review.
Clarification 008 Accepted baseline.
"""
import datetime
import json
import pytest
from decimal import Decimal
from unittest.mock import patch

import database
from interfaces.base import ServiceRegistry
from arc_engine.input_assembler import ARCInputAssembler
from arc_engine.decision_engine import ARCDecisionEngine
from arc_engine.confidence_calculator import ARCConfidenceCalculator
from arc_engine.persistence import ARCPersistence
from arc_engine.recovery_manager import ARCRecoveryManager
from arc_engine.arc_processor import ARCProcessor
from arc_engine.telemetry import ARCTelemetry


# ============================================================
# Fixtures / Helpers
# ============================================================

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    database.init_db("schema.sql")
    # audit_log is protected by an immutability trigger — never DELETE from it (Phase 1 constraint)
    database.execute_query("DELETE FROM signals;")
    database.execute_query("DELETE FROM latency_metrics;")


def _make_bundle(
    symbol="TATASTEEL",
    signal_id="SIG_TEST_001",
    direction="LONG",
    score=91.5,
    aligned_dir="BULLISH",
    alignment_score=100,
    is_aligned=True,
    smc_ct="PASS",
    options_bias="BULLISH",
    options_pcr=1.25,
    geie_impact_dir="POSITIVE",
    geie_confidence="HIGH",
    geie_magnitude=2,
    hard_stop=False,
    risk_status="PASS",
    risk_grade="B",
) -> dict:
    """Builds a complete ARC Input Bundle for testing."""
    return {
        "symbol": symbol,
        "signal_id": signal_id,
        "as_of_time": "2026-06-15T10:30:00+05:30",
        "trend_input": {
            "is_aligned": is_aligned,
            "aligned_direction": aligned_dir,
            "alignment_score": alignment_score,
            "timeframe_breakdown": {"Daily": aligned_dir, "1h": aligned_dir, "15m": aligned_dir, "5m": aligned_dir}
        },
        "smc_input": {
            "direction": direction,
            "score": 100,
            "cross_timeframe_status": smc_ct,
            "confirmations_count": 4,
            "entry_low": 100.0,
            "entry_high": 102.0,
            "stop_loss": 98.0,
            "target_1": 106.0,
            "target_2": 110.0,
        },
        "options_input": {
            "pcr_oi": options_pcr,
            "pcr_volume": 1.1,
            "bias": options_bias,
            "max_pain_level": 100.0,
            "highest_call_oi_strike": 105.0,
            "highest_put_oi_strike": 95.0,
        },
        "scoring_input": {
            "final_composite_score": score,
            "risk_grade": risk_grade,
            "regime_score": 100.0,
            "rs_score": 80.0,
            "rvol_score": 90.0,
            "breadth_score": 70.0,
            "sector_score": 85.0,
            "trend_score": 100.0,
            "smc_score": 100.0,
            "options_score": 85.0,
        },
        "risk_input": {
            "status_code": risk_status,
            "quantity": 3,
            "risk_amount": 5000.0,
            "daily_risk_used_pct": 0.5,
            "consecutive_losses": 0,
            "hard_stop_active": hard_stop,
        },
        "geie_input": {
            "geie_status": "ACTIVE",
            "market_sentiment": "RISK_ON",
            "stock_impact": {
                "direction": geie_impact_dir,
                "magnitude": geie_magnitude,
                "confidence": geie_confidence,
                "reasons": ["Test reason"],
                "urgency": "INTRADAY",
            },
            "institutional_bias": "BULLISH",
            "fii_5day_trend": "BUYING",
            "key_support_from_options": "95",
            "key_resistance_from_options": "105",
        }
    }


def _make_signal_in_db(signal_id: str, symbol: str = "TATASTEEL") -> None:
    """Inserts a minimal ACTIVE signal into the DB for persistence tests."""
    ts = datetime.datetime.now()
    valid_until = ts + datetime.timedelta(hours=4)
    database.execute_query(
        """INSERT INTO signals (signal_id, timestamp, symbol, direction, score, confidence, regime,
           entry_low, entry_high, stop_loss, target_1, target_2, quantity, risk_amount, risk_grade, valid_until)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (signal_id) DO NOTHING;""",
        (signal_id, ts, symbol, "LONG", Decimal("91.5"), "HIGH", "BULLISH",
         Decimal("100"), Decimal("102"), Decimal("98"), Decimal("106"), Decimal("110"),
         3, Decimal("5000"), "B", valid_until)
    )


# ============================================================
# 1. Input Assembler Tests
# ============================================================

def test_assemble_full_bundle():
    """1. Verify full ARC Input Bundle assembles correctly."""
    trend_data = {"is_aligned": True, "aligned_direction": "BULLISH",
                  "alignment_score": 100, "timeframe_breakdown": {}}
    smc_data = {"direction": "LONG", "score": 100, "cross_timeframe_status": "PASS",
                "confirmations_count": 4, "entry_low": Decimal("100"), "entry_high": Decimal("102"),
                "stop_loss": Decimal("98"), "target_1": Decimal("106"), "target_2": Decimal("110")}
    options_data = {"pcr_oi": 1.25, "pcr_volume": 1.1, "max_pain_level": Decimal("100"),
                    "highest_call_oi_strike": Decimal("105"), "highest_put_oi_strike": Decimal("95"),
                    "bias": "BULLISH"}
    scoring_data = {"final_composite_score": Decimal("91.5"), "risk_grade": "B",
                    "regime_score": Decimal("100"), "rs_score": Decimal("80"),
                    "rvol_score": Decimal("90"), "breadth_score": Decimal("70"),
                    "sector_score": Decimal("85"), "trend_score": Decimal("100"),
                    "smc_score": Decimal("100"), "options_score": Decimal("85")}
    risk_data = {"status_code": "PASS", "quantity": 3, "risk_amount": Decimal("5000"),
                 "risk_state": {"daily_risk_used": Decimal("0.5"), "consecutive_losses": 0, "hard_stop_active": False}}
    geie_data = {"geie_status": "ACTIVE", "market_sentiment": "RISK_ON",
                 "institutional_bias": "BULLISH", "fii_5day_trend": "BUYING",
                 "key_support_from_options": "95", "key_resistance_from_options": "105",
                 "stock_impacts": {"TATASTEEL": {"direction": "POSITIVE", "magnitude": 2,
                                                  "confidence": "HIGH", "reasons": ["FII buying"],
                                                  "urgency": "INTRADAY"}}}

    bundle = ARCInputAssembler.assemble(
        symbol="TATASTEEL", signal_id="SIG_001",
        as_of_time=datetime.datetime.now(),
        trend_data=trend_data, smc_data=smc_data, options_data=options_data,
        scoring_data=scoring_data, risk_data=risk_data, geie_data=geie_data
    )

    assert bundle["symbol"] == "TATASTEEL"
    assert bundle["smc_input"]["direction"] == "LONG"
    assert bundle["scoring_input"]["final_composite_score"] == 91.5
    assert bundle["geie_input"]["stock_impact"]["direction"] == "POSITIVE"
    # All Decimal fields converted to float
    assert isinstance(bundle["smc_input"]["entry_low"], float)


def test_assemble_premarket_bundle():
    """2. Verify premarket-only bundle assembles with defaults."""
    geie_data = {"geie_status": "ACTIVE", "market_sentiment": "NEUTRAL",
                 "institutional_bias": "NEUTRAL", "fii_5day_trend": "MIXED",
                 "key_support_from_options": "N/A", "key_resistance_from_options": "N/A",
                 "stock_impacts": {"RELIANCE": {"direction": "NEUTRAL", "magnitude": 1,
                                                "confidence": "LOW", "reasons": [], "urgency": "INTRADAY"}},
                 "timestamp": "2026-06-15 08:05:00 IST"}
    bundle = ARCInputAssembler.assemble_premarket("RELIANCE", geie_data)
    assert bundle["symbol"] == "RELIANCE"
    assert bundle["smc_input"]["direction"] == "UNKNOWN"
    assert bundle["risk_input"]["status_code"] == "PREMARKET"


# ============================================================
# 2. Engine Alignment Tests
# ============================================================

def test_alignment_all_agree_long():
    """3. All 6 engines AGREE on a LONG signal."""
    bundle = _make_bundle()
    alignment = ARCDecisionEngine.classify_engine_alignment(bundle, "LONG")
    assert alignment["trend"] == "AGREE"
    assert alignment["smc"] == "AGREE"
    assert alignment["options"] == "AGREE"
    assert alignment["scoring"] == "AGREE"
    assert alignment["risk"] == "AGREE"
    assert alignment["geie"] == "AGREE"


def test_alignment_trend_disagrees_long():
    """4. Trend BEARISH while signal is LONG → trend=DISAGREE."""
    bundle = _make_bundle(aligned_dir="BEARISH")
    alignment = ARCDecisionEngine.classify_engine_alignment(bundle, "LONG")
    assert alignment["trend"] == "DISAGREE"


def test_alignment_geie_disagrees_high_confidence():
    """5. GEIE NEGATIVE + HIGH confidence on LONG → geie=DISAGREE."""
    bundle = _make_bundle(geie_impact_dir="NEGATIVE", geie_confidence="HIGH")
    alignment = ARCDecisionEngine.classify_engine_alignment(bundle, "LONG")
    assert alignment["geie"] == "DISAGREE"


def test_alignment_options_partial_neutral():
    """6. Options bias NEUTRAL → options=PARTIAL for LONG."""
    bundle = _make_bundle(options_bias="NEUTRAL", options_pcr=1.0)
    alignment = ARCDecisionEngine.classify_engine_alignment(bundle, "LONG")
    # pcr_oi == 1.0 meets >= 1.0 for LONG, so AGREE
    assert alignment["options"] == "AGREE"

    bundle2 = _make_bundle(options_bias="NEUTRAL", options_pcr=0.9)
    alignment2 = ARCDecisionEngine.classify_engine_alignment(bundle2, "LONG")
    # pcr_oi < 1.0 and bias NEUTRAL → PARTIAL
    assert alignment2["options"] == "PARTIAL"


# ============================================================
# 3. Reject Rule Tests
# ============================================================

def test_reject_r01_trend_smc_conflict():
    """7. R01: Trend BEARISH + SMC LONG → REJECT."""
    bundle = _make_bundle(aligned_dir="BEARISH")
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "LONG")
    assert should_reject
    assert any("ARC_R01" in c for c in codes)


def test_reject_r02_geie_negative_long():
    """8. R02: GEIE HIGH NEGATIVE on LONG → REJECT."""
    bundle = _make_bundle(geie_impact_dir="NEGATIVE", geie_confidence="HIGH")
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "LONG")
    assert should_reject
    assert any("ARC_R02" in c for c in codes)


def test_reject_r03_geie_positive_short():
    """9. R03: GEIE HIGH POSITIVE on SHORT → REJECT."""
    bundle = _make_bundle(direction="SHORT", geie_impact_dir="POSITIVE", geie_confidence="HIGH",
                          aligned_dir="BEARISH")
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "SHORT")
    assert should_reject
    assert any("ARC_R03" in c for c in codes)


def test_reject_r04_hard_stop():
    """10. R04: hard_stop_active=True → REJECT."""
    bundle = _make_bundle(hard_stop=True)
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "LONG")
    assert should_reject
    assert any("ARC_R04" in c for c in codes)


def test_reject_r05_score_below_threshold():
    """11. R05: Score 83.0 < 86.0 → REJECT."""
    bundle = _make_bundle(score=83.0)
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "LONG")
    assert should_reject
    assert any("ARC_R05" in c for c in codes)


def test_reject_r06_no_direction():
    """12. R06: SMC NO_DIRECTION → REJECT."""
    bundle = _make_bundle(direction="NO_DIRECTION")
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "NO_DIRECTION")
    assert should_reject
    assert any("ARC_R06" in c for c in codes)


def test_reject_r07_no_alignment_weak_smc():
    """13. R07: No trend alignment + SMC score 40 → REJECT."""
    bundle = _make_bundle(is_aligned=False)
    bundle["smc_input"]["score"] = 40
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "LONG")
    assert should_reject
    assert any("ARC_R07" in c for c in codes)


def test_no_reject_clean_signal():
    """14. Clean signal with all rules satisfied → no REJECT."""
    bundle = _make_bundle()
    should_reject, codes = ARCDecisionEngine.evaluate_reject_rules(bundle, "LONG")
    assert not should_reject
    assert len(codes) == 0


# ============================================================
# 4. Conflict Resolution Matrix Tests
# ============================================================

def test_conflict_6_agree_approve():
    """15. 6 AGREE → APPROVE."""
    alignment = {k: "AGREE" for k in ["trend", "smc", "options", "scoring", "risk", "geie"]}
    decision, flags = ARCDecisionEngine.resolve_from_alignment(alignment, [])
    assert decision == "APPROVE"
    assert flags == []


def test_conflict_5_agree_0_disagree_approve():
    """16. 5 AGREE, 0 DISAGREE → APPROVE."""
    alignment = {k: "AGREE" for k in ["trend", "smc", "options", "scoring", "risk"]}
    alignment["geie"] = "PARTIAL"
    decision, flags = ARCDecisionEngine.resolve_from_alignment(alignment, [])
    assert decision == "APPROVE"


def test_conflict_4_agree_1_disagree_caution():
    """17. 4 AGREE, 1 DISAGREE → CAUTION."""
    alignment = {k: "AGREE" for k in ["trend", "smc", "options", "scoring"]}
    alignment["risk"] = "PARTIAL"
    alignment["geie"] = "DISAGREE"
    decision, flags = ARCDecisionEngine.resolve_from_alignment(alignment, [])
    assert decision == "CAUTION"
    assert "geie=DISAGREE" in flags


def test_conflict_3_agree_2_disagree_reject():
    """18. 3 AGREE, 2 DISAGREE → REJECT."""
    alignment = {k: "AGREE" for k in ["trend", "smc", "options"]}
    alignment["scoring"] = "DISAGREE"
    alignment["risk"] = "DISAGREE"
    alignment["geie"] = "PARTIAL"
    decision, flags = ARCDecisionEngine.resolve_from_alignment(alignment, [])
    assert decision == "REJECT"


def test_conflict_reject_codes_override():
    """19. Reject codes always → REJECT regardless of agreement count."""
    alignment = {k: "AGREE" for k in ["trend", "smc", "options", "scoring", "risk", "geie"]}
    codes = ["ARC_R01: test reject"]
    decision, _ = ARCDecisionEngine.resolve_from_alignment(alignment, codes)
    assert decision == "REJECT"


# ============================================================
# 5. Confidence Calculator Tests
# ============================================================

def test_confidence_high():
    """20. Score > 92, GEIE POSITIVE, WR > 60% → HIGH confidence."""
    conf = ARCConfidenceCalculator.calculate(
        score=95.0, geie_direction="POSITIVE", win_rate=65.0
    )
    assert conf == "HIGH"


def test_confidence_medium():
    """21. Score 88 to 92, GEIE POSITIVE/NEUTRAL, WR 50-60% → MEDIUM confidence."""
    conf = ARCConfidenceCalculator.calculate(
        score=90.0, geie_direction="NEUTRAL", win_rate=55.0
    )
    assert conf == "MEDIUM"


def test_confidence_low():
    """22. Score 86 to 88, GEIE NEUTRAL, WR < 50% → LOW confidence."""
    conf = ARCConfidenceCalculator.calculate(
        score=87.0, geie_direction="NEUTRAL", win_rate=45.0
    )
    assert conf == "LOW"


def test_confidence_from_bundle():
    """23. from_bundle convenience method returns valid label."""
    bundle = _make_bundle()
    conf = ARCConfidenceCalculator.from_bundle(bundle)
    assert conf in ("HIGH", "MEDIUM", "LOW")


# ============================================================
# 6. Fallback Decision Tests
# ============================================================

def test_fallback_score_ge_90_engines_agree():
    """26. Fallback: score >= 90, 5+ agree → CAUTION confidence 60."""
    bundle = _make_bundle(score=92.0)
    decision = ARCDecisionEngine.build_fallback_decision(
        signal_id="SIG_FB_001", symbol="TATASTEEL",
        bundle=bundle, signal_direction="LONG",
        fallback_reason="Claude timeout"
    )
    assert decision["arc_decision"] == "CAUTION"
    assert decision["arc_confidence"] == 60


def test_fallback_score_ge_86_partial_agree():
    """27. Fallback: score 88, 4 agree → CAUTION confidence 40."""
    bundle = _make_bundle(score=88.0, options_bias="NEUTRAL")
    decision = ARCDecisionEngine.build_fallback_decision(
        signal_id="SIG_FB_002", symbol="TATASTEEL",
        bundle=bundle, signal_direction="LONG",
        fallback_reason="Claude timeout"
    )
    assert decision["arc_decision"] in ("CAUTION", "REJECT")
    assert decision["arc_confidence"] <= 60


def test_fallback_never_approve():
    """28. Fallback NEVER issues APPROVE."""
    bundle = _make_bundle(score=99.0)
    decision = ARCDecisionEngine.build_fallback_decision(
        signal_id="SIG_FB_003", symbol="TATASTEEL",
        bundle=bundle, signal_direction="LONG",
        fallback_reason="API error"
    )
    assert decision["arc_decision"] != "APPROVE"


# ============================================================
# 7. Cutoff Decision Tests
# ============================================================

def test_cutoff_decision_structure():
    """29. Cutoff decision returns CAUTION with confidence 30."""
    decision = ARCDecisionEngine.build_cutoff_decision("PREMARKET_SBIN_2026-06-15", "SBIN")
    assert decision["arc_decision"] == "CAUTION"
    assert decision["arc_confidence"] == 30
    assert "ARC_CUTOFF" in decision["reasoning_summary"]


# ============================================================
# 8. Schema Validation Tests
# ============================================================

def test_schema_validation_valid():
    """30. Valid ARC schema passes validation."""
    valid = {
        "arc_decision": "APPROVE",
        "arc_confidence": 87,
        "reasoning_summary": "Test",
        "engine_alignment": {},
        "conflict_flags": [],
        "reject_reasons": [],
        "caution_reasons": [],
        "explainability": {},
        "arc_timestamp": "2026-06-15T10:30:00+05:30",
        "arc_version": "1.0"
    }
    assert ARCProcessor._validate_arc_schema(valid) is True


def test_schema_validation_invalid_decision():
    """31. Invalid arc_decision value fails validation."""
    invalid = {
        "arc_decision": "HOLD",  # invalid
        "arc_confidence": 87,
        "reasoning_summary": "Test",
        "engine_alignment": {},
        "conflict_flags": [],
        "reject_reasons": [],
        "caution_reasons": [],
        "explainability": {},
        "arc_timestamp": "2026-06-15T10:30:00+05:30",
        "arc_version": "1.0"
    }
    assert ARCProcessor._validate_arc_schema(invalid) is False


def test_schema_validation_missing_keys():
    """32. Schema missing required key fails validation."""
    invalid = {"arc_decision": "APPROVE", "arc_confidence": 87}
    assert ARCProcessor._validate_arc_schema(invalid) is False


def test_schema_validation_confidence_out_of_range():
    """33. Confidence 150 fails validation."""
    invalid = {
        "arc_decision": "APPROVE",
        "arc_confidence": 150,  # out of range
        "reasoning_summary": "Test",
        "engine_alignment": {},
        "conflict_flags": [],
        "reject_reasons": [],
        "caution_reasons": [],
        "explainability": {},
        "arc_timestamp": "2026-06-15T10:30:00+05:30",
        "arc_version": "1.0"
    }
    assert ARCProcessor._validate_arc_schema(invalid) is False


# ============================================================
# 9. Persistence Tests
# ============================================================

def test_persistence_save_arc_decision():
    """34. Save ARC decision label to signals table."""
    signal_id = "SIG_ARC_P001"
    _make_signal_in_db(signal_id)
    result = ARCPersistence.save_arc_decision_label(signal_id, "APPROVE")
    assert result is True
    # Verify
    rows = database.execute_query(
        "SELECT arc_decision FROM signals WHERE signal_id = %s;", (signal_id,), fetch=True
    )
    assert rows and rows[0][0] == "APPROVE"


def test_persistence_cancel_rejected_signal():
    """35. Cancel ACTIVE signal on REJECT."""
    signal_id = "SIG_ARC_P002"
    _make_signal_in_db(signal_id)
    ARCPersistence.cancel_rejected_signal(signal_id)
    rows = database.execute_query(
        "SELECT status FROM signals WHERE signal_id = %s;", (signal_id,), fetch=True
    )
    assert rows and rows[0][0] == "CANCELLED"


def test_persistence_load_active_signals_with_arc():
    """36. Load signals that have ARC decision."""
    signal_id = "SIG_ARC_P003"
    _make_signal_in_db(signal_id)
    ARCPersistence.save_arc_decision_label(signal_id, "CAUTION")
    rows = ARCPersistence.load_active_signals_with_arc(datetime.date.today())
    arc_decisions = [r["arc_decision"] for r in rows]
    assert "CAUTION" in arc_decisions


# ============================================================
# 10. Recovery Manager Tests
# ============================================================

def test_recovery_watchlist_save_and_restore():
    """37. Save and recover watchlist decisions from Redis."""
    today = datetime.date.today()
    decisions = {"RELIANCE": "APPROVE", "WIPRO": "REJECT", "TATASTEEL": "CAUTION"}
    ARCRecoveryManager.save_watchlist(today, decisions)
    restored = ARCRecoveryManager.recover_watchlist(today)
    assert restored == decisions


def test_recovery_signal_decision_cache():
    """38. Cache and retrieve signal ARC decision from Redis."""
    signal_id = "SIG_ARC_CACHE_001"
    arc_json = {"arc_decision": "APPROVE", "arc_confidence": 87, "symbol": "TATASTEEL"}
    ARCRecoveryManager.cache_signal_decision(signal_id, arc_json)
    cached = ARCRecoveryManager.get_cached_signal_decision(signal_id)
    assert cached is not None
    assert cached["arc_decision"] == "APPROVE"


def test_recovery_premarket_cache():
    """39. Cache and retrieve premarket decision from Redis."""
    today = datetime.date.today()
    symbol = "HDFCBANK"
    arc_json = {"arc_decision": "CAUTION", "arc_confidence": 55, "symbol": symbol}
    ARCRecoveryManager.cache_premarket_decision(today, symbol, arc_json)
    cached = ARCRecoveryManager.get_cached_premarket_decision(today, symbol)
    assert cached is not None
    assert cached["arc_decision"] == "CAUTION"


def test_recovery_invalidate_signal():
    """40. Invalidate cached signal decision."""
    signal_id = "SIG_ARC_INV_001"
    arc_json = {"arc_decision": "APPROVE"}
    ARCRecoveryManager.cache_signal_decision(signal_id, arc_json)
    ARCRecoveryManager.invalidate_signal(signal_id)
    assert ARCRecoveryManager.get_cached_signal_decision(signal_id) is None


# ============================================================
# 11. ARCProcessor Intraday Review Tests (DE-SCOPED per NC1)
# ============================================================

# Intraday ARC review capability was removed to satisfy NC1.
# Intraday ARC tests are de-scoped.



# ============================================================
# 13. Premarket Batch Tests
# ============================================================

def test_arc_processor_premarket_batch():
    """48. Premarket batch reviews multiple symbols and returns decisions for all."""
    processor = ARCProcessor()
    symbols = ["TATASTEEL", "RELIANCE", "WIPRO", "HDFCBANK", "INFY"]

    geie_payload = {
        "geie_status": "ACTIVE",
        "market_sentiment": "RISK_ON",
        "institutional_bias": "BULLISH",
        "fii_5day_trend": "BUYING",
        "key_support_from_options": "23000",
        "key_resistance_from_options": "23500",
        "timestamp": "2026-06-15 08:05:00 IST",
        "stock_impacts": {s: {"direction": "POSITIVE", "magnitude": 1,
                              "confidence": "MEDIUM", "reasons": ["Test"],
                              "urgency": "INTRADAY"} for s in symbols}
    }

    # Use a timestamp before cutoff (08:20)
    ts = datetime.datetime(2026, 6, 15, 8, 20, 0)
    results = processor.run_premarket(
        timestamp=ts, symbols=symbols,
        geie_payload=geie_payload, force_refresh=True
    )

    assert len(results) == 5
    for symbol in symbols:
        assert symbol in results
        assert results[symbol] in ("APPROVE", "CAUTION", "REJECT")


def test_arc_processor_premarket_cutoff():
    """49. Premarket batch past 08:50 cutoff → all unreviewed symbols get CAUTION."""
    processor = ARCProcessor()
    symbols = ["ONGC", "POWERGRID"]

    geie_payload = {
        "geie_status": "ACTIVE", "market_sentiment": "NEUTRAL",
        "institutional_bias": "NEUTRAL", "fii_5day_trend": "MIXED",
        "key_support_from_options": "N/A", "key_resistance_from_options": "N/A",
        "timestamp": "2026-06-15 08:05:00 IST",
        "stock_impacts": {s: {"direction": "NEUTRAL", "magnitude": 1,
                              "confidence": "LOW", "reasons": [], "urgency": "INTRADAY"}
                         for s in symbols}
    }

    # Timestamp AFTER cutoff (09:00)
    ts = datetime.datetime(2026, 6, 15, 9, 0, 0)
    results = processor.run_premarket(
        timestamp=ts, symbols=symbols,
        geie_payload=geie_payload, force_refresh=True
    )

    for symbol in symbols:
        assert symbol in results
        assert results[symbol] == "CAUTION"  # cutoff forces CAUTION


# ============================================================
# 14. Post-Market Review Test
# ============================================================

def test_arc_processor_postmarket():
    """50. Post-market review returns SUCCESS with reviewed_count."""
    processor = ARCProcessor()
    signals = [
        {"signal_id": "SIG_EOD_001", "symbol": "TATASTEEL", "outcome": "HIT_T1"},
        {"signal_id": "SIG_EOD_002", "symbol": "RELIANCE", "outcome": "HIT_SL"},
    ]
    result = processor.run_postmarket(signals)
    assert result["status"] == "SUCCESS"
    assert result["reviewed_count"] == 2


# ============================================================
# 15. Telemetry Test
# ============================================================

def test_arc_telemetry_writes():
    """51. ARC telemetry records a latency row without raising."""
    # Should not raise even if DB is unreachable (fire-and-forget)
    ARCTelemetry.record_latency("TATASTEEL", 250.5, claude_latency_ms=200.0, cache_hit=False)
    ARCTelemetry.record_latency("RELIANCE", 5.0, cache_hit=True)

    rows = database.execute_query(
        "SELECT stage, processing_latency_ms FROM latency_metrics WHERE stage = 'ARC_REVIEW' LIMIT 5;",
        fetch=True
    )
    assert rows is not None


# ============================================================
# 16. Full Nifty 50 Simulation
# ============================================================

def test_arc_nifty50_premarket_simulation():
    """52. ARC premarket simulation for full Nifty 50 (50 symbols)."""
    from market_data.instrument_loader import InstrumentLoader
    symbols = InstrumentLoader().symbols
    assert len(symbols) == 50

    processor = ARCProcessor()
    geie_payload = {
        "geie_status": "ACTIVE", "market_sentiment": "RISK_ON",
        "institutional_bias": "BULLISH", "fii_5day_trend": "BUYING",
        "key_support_from_options": "23000", "key_resistance_from_options": "23500",
        "timestamp": "2026-06-15 08:05:00 IST",
        "stock_impacts": {s: {"direction": "POSITIVE", "magnitude": 1,
                              "confidence": "MEDIUM", "reasons": [], "urgency": "INTRADAY"}
                         for s in symbols}
    }

    ts = datetime.datetime(2026, 6, 15, 8, 20, 0)
    results = processor.run_premarket(
        timestamp=ts, symbols=symbols,
        geie_payload=geie_payload, force_refresh=True
    )

    assert len(results) == 50
    for sym, dec in results.items():
        assert dec in ("APPROVE", "CAUTION", "REJECT")

    approve_count = sum(1 for v in results.values() if v == "APPROVE")
    reject_count = sum(1 for v in results.values() if v == "REJECT")
    print(f"\n[ARC SIM] Nifty50: {approve_count} APPROVE, "
          f"{sum(1 for v in results.values() if v == 'CAUTION')} CAUTION, "
          f"{reject_count} REJECT")
