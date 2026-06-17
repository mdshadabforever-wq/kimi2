import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

from interfaces.base import ServiceRegistry
from audit import log_audit
import redis_client

from arc_engine.input_assembler import ARCInputAssembler
from arc_engine.decision_engine import ARCDecisionEngine
from arc_engine.confidence_calculator import ARCConfidenceCalculator
from arc_engine.persistence import ARCPersistence
from arc_engine.recovery_manager import ARCRecoveryManager
from arc_engine.telemetry import ARCTelemetry


# 08:50 AM IST cutoff as time object
_PREMARKET_CUTOFF_TIME = datetime.time(8, 50, 0)
_MAX_PARALLEL_WORKERS = 5


class ARCProcessor:
    """Main ARC Engine orchestrator.
    Handles premarket batch review (08:20–08:50 AM, max 5 parallel workers)
    and intraday per-signal review via Claude.
    Clarification 008, Sections 16 and 17.
    """

    def __init__(self):
        self.session_date: datetime.date = None
        # symbol -> arc_decision label (APPROVE/CAUTION/REJECT)
        self.watchlist_decisions: Dict[str, str] = {}
        # signal_id -> arc_decision label
        self.signal_decisions: Dict[str, str] = {}

    # -----------------------------------------------------------------------
    # Restart Recovery
    # -----------------------------------------------------------------------

    def recover(self, session_date: datetime.date) -> None:
        """Restores in-memory state from Redis and DB on restart.
        Clarification 008, Section 13.1.
        """
        self.session_date = session_date
        # 1. Restore watchlist from Redis
        self.watchlist_decisions = ARCRecoveryManager.recover_watchlist(session_date)
        # 2. Restore signal decisions from DB (as fallback if Redis missing)
        if not self.signal_decisions:
            self.signal_decisions = ARCRecoveryManager.recover_signal_decisions(session_date)
        print(f"[ARC PROCESSOR] Recovery complete. "
              f"Watchlist: {len(self.watchlist_decisions)} symbols, "
              f"Signals: {len(self.signal_decisions)} decisions restored.")

    # -----------------------------------------------------------------------
    # Premarket Batch Review (Clarification 008, Section 16)
    # -----------------------------------------------------------------------

    def run_premarket(
        self,
        timestamp: datetime.datetime,
        symbols: List[str],
        geie_payload: Dict[str, Any],
        scoring_map: Dict[str, Any] = None,
        trend_map: Dict[str, Any] = None,
        force_refresh: bool = False,
    ) -> Dict[str, str]:
        """Runs pre-market ARC review for the full symbol watchlist.

        Args:
            timestamp: The current time (used to check 08:50 cutoff).
            symbols: List of Nifty 50 symbols.
            geie_payload: Full GEIE payload from GEIEProcessor.run_premarket().
            scoring_map: Optional dict of symbol → scoring_data.
            trend_map: Optional dict of symbol → trend_data.
            force_refresh: If True, bypass Redis cache.

        Returns:
            Dict of symbol → ARC decision label (APPROVE/CAUTION/REJECT).
        """
        scoring_map = scoring_map or {}
        trend_map = trend_map or {}
        self.session_date = timestamp.date()
        session_date = self.session_date

        # Check cutoff immediately
        current_time = timestamp.time()
        cutoff_time = _PREMARKET_CUTOFF_TIME

        results: Dict[str, str] = {}
        to_review: List[str] = []

        # Separate symbols into cached vs needs-review
        for symbol in symbols:
            if not force_refresh:
                cached = ARCRecoveryManager.get_cached_premarket_decision(session_date, symbol)
                if cached:
                    results[symbol] = cached.get("arc_decision", "CAUTION")
                    continue
            to_review.append(symbol)

        print(f"[ARC PROCESSOR] Premarket: {len(results)} cached, {len(to_review)} to review. "
              f"Cutoff check: current={current_time}, cutoff={cutoff_time}")

        # Apply cutoff immediately if already past 08:50
        if current_time >= cutoff_time:
            for symbol in to_review:
                cutoff_dec = ARCDecisionEngine.build_cutoff_decision(
                    signal_id=f"PREMARKET_{symbol}_{session_date}",
                    symbol=symbol
                )
                results[symbol] = cutoff_dec["arc_decision"]
                ARCRecoveryManager.cache_premarket_decision(session_date, symbol, cutoff_dec)
                self._log_arc_decision(symbol, f"PREMARKET_{symbol}_{session_date}", cutoff_dec, "PREMARKET_CUTOFF")
            self.watchlist_decisions.update(results)
            ARCRecoveryManager.save_watchlist(session_date, results)
            return results

        # Bounded concurrent review (max 5 workers)
        with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_WORKERS) as executor:
            future_to_symbol = {}
            for symbol in to_review:
                # Rate limit: 0.2s sleep between submissions
                time.sleep(0.2)

                # Check cutoff before each submission
                now = datetime.datetime.now().time()
                if now >= cutoff_time:
                    # Apply cutoff to remaining symbols
                    cutoff_dec = ARCDecisionEngine.build_cutoff_decision(
                        signal_id=f"PREMARKET_{symbol}_{session_date}",
                        symbol=symbol
                    )
                    results[symbol] = cutoff_dec["arc_decision"]
                    ARCRecoveryManager.cache_premarket_decision(session_date, symbol, cutoff_dec)
                    self._log_arc_decision(symbol, f"PREMARKET_{symbol}_{session_date}", cutoff_dec, "PREMARKET_CUTOFF")
                    continue

                bundle = ARCInputAssembler.assemble_premarket(
                    symbol=symbol,
                    geie_data=geie_payload,
                    scoring_data=scoring_map.get(symbol, {}),
                    trend_data=trend_map.get(symbol, {}),
                )
                future = executor.submit(self._review_single_symbol_premarket, symbol, bundle, session_date)
                future_to_symbol[future] = symbol

            # Collect results as futures complete
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    decision_json = future.result()
                    results[symbol] = decision_json.get("arc_decision", "CAUTION")
                except Exception as e:
                    print(f"[ARC PROCESSOR] Premarket review failed for {symbol}: {e}")
                    fallback = ARCDecisionEngine.build_fallback_decision(
                        signal_id=f"PREMARKET_{symbol}_{session_date}",
                        symbol=symbol,
                        bundle={},
                        signal_direction="LONG",
                        fallback_reason=f"Worker exception: {str(e)[:100]}"
                    )
                    results[symbol] = fallback["arc_decision"]

        # Apply cutoff to any symbol still missing from results
        for symbol in to_review:
            if symbol not in results:
                cutoff_dec = ARCDecisionEngine.build_cutoff_decision(
                    signal_id=f"PREMARKET_{symbol}_{session_date}",
                    symbol=symbol
                )
                results[symbol] = cutoff_dec["arc_decision"]

        self.watchlist_decisions.update(results)
        ARCRecoveryManager.save_watchlist(session_date, results)

        # Summary audit
        approve_c = sum(1 for v in results.values() if v == "APPROVE")
        caution_c = sum(1 for v in results.values() if v == "CAUTION")
        reject_c = sum(1 for v in results.values() if v == "REJECT")
        log_audit(
            component="ARC_ENGINE",
            action="PREMARKET_BATCH_COMPLETE",
            result="SUCCESS",
            reason=f"Premarket review complete: {approve_c} APPROVE / {caution_c} CAUTION / {reject_c} REJECT",
            metadata={"session_date": str(session_date), "total_symbols": len(symbols),
                      "approve": approve_c, "caution": caution_c, "reject": reject_c}
        )
        return results

    def _review_single_symbol_premarket(
        self,
        symbol: str,
        bundle: Dict[str, Any],
        session_date: datetime.date
    ) -> Dict[str, Any]:
        """Reviews a single symbol during premarket batch. Returns ARC decision JSON."""
        start_time = time.perf_counter()
        signal_id = f"PREMARKET_{symbol}_{session_date}"

        decision_json = self._call_claude_with_fallback(
            signal_id=signal_id,
            symbol=symbol,
            bundle=bundle,
            signal_direction="LONG",  # Premarket defaults to LONG evaluation (worst-case)
        )

        ARCRecoveryManager.cache_premarket_decision(session_date, symbol, decision_json)
        self._log_arc_decision(symbol, signal_id, decision_json, "PREMARKET_REVIEW")

        total_ms = (time.perf_counter() - start_time) * 1000
        ARCTelemetry.record_latency(symbol, total_ms)
        return decision_json



    # -----------------------------------------------------------------------
    # Core Claude Call with Fallback (Clarification 008, Section 15)
    # -----------------------------------------------------------------------

    def _call_claude_with_fallback(
        self,
        signal_id: str,
        symbol: str,
        bundle: Dict[str, Any],
        signal_direction: str,
    ) -> Dict[str, Any]:
        """Calls Claude via ServiceRegistry. Applies 1-retry then fallback logic.
        Clarification 008, Section 15.
        """
        claude = ServiceRegistry.get("claude")
        last_error = None

        for attempt in range(2):  # 1 initial call + 1 retry
            try:
                start_claude = time.perf_counter()
                response = claude.review_symbol(signal_id, bundle)

                claude_ms = (time.perf_counter() - start_claude) * 1000

                # Validate response schema
                if not self._validate_arc_schema(response):
                    raise ValueError(f"Invalid ARC decision schema: {str(response)[:200]}")

                # Cross-validate with deterministic rules (ARC can't approve what rules reject)
                should_reject, reject_codes = ARCDecisionEngine.evaluate_reject_rules(
                    bundle=bundle,
                    signal_direction=signal_direction
                )
                if should_reject and response.get("arc_decision") == "APPROVE":
                    # Override: deterministic rules override Claude
                    response["arc_decision"] = "REJECT"
                    response["reject_reasons"] = reject_codes
                    response["reasoning_summary"] = f"ARC_OVERRIDE: Deterministic rules reject. {reject_codes[0]}"

                return response

            except Exception as e:
                last_error = str(e)
                print(f"[ARC PROCESSOR] Claude call failed (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    time.sleep(0.5)  # Brief pause before retry

        # Both attempts failed — apply fallback
        log_audit(
            component="ARC_ENGINE",
            action="API_FALLBACK",
            result="WARNING",
            reason=f"Claude unavailable after 2 attempts for {symbol}: {last_error[:200]}",
            metadata={"signal_id": signal_id, "symbol": symbol}
        )
        return ARCDecisionEngine.build_fallback_decision(
            signal_id=signal_id,
            symbol=symbol,
            bundle=bundle,
            signal_direction=signal_direction,
            fallback_reason=f"Claude unavailable: {last_error[:100] if last_error else 'unknown error'}"
        )

    # -----------------------------------------------------------------------
    # Audit Logging (Clarification 008, Section 11)
    # -----------------------------------------------------------------------

    def _log_arc_decision(
        self,
        symbol: str,
        signal_id: str,
        decision_json: Dict[str, Any],
        action: str
    ) -> None:
        """Logs full ARC decision JSON to immutable audit_log.
        Schema decision: full JSON in audit_log.metadata.
        """
        try:
            log_audit(
                component="ARC_ENGINE",
                action=action,
                result=decision_json.get("arc_decision", "UNKNOWN"),
                reason=decision_json.get("reasoning_summary", ""),
                metadata={
                    "signal_id": signal_id,
                    "symbol": symbol,
                    "arc_confidence": decision_json.get("arc_confidence", 0),
                    "arc_decision": decision_json.get("arc_decision"),
                    "engine_alignment": decision_json.get("engine_alignment", {}),
                    "conflict_flags": decision_json.get("conflict_flags", []),
                    "reject_reasons": decision_json.get("reject_reasons", []),
                    "arc_version": decision_json.get("arc_version", "1.0"),
                    "full_json": decision_json  # Full ARC JSON stored here per schema decision
                }
            )
        except Exception as e:
            print(f"[ARC PROCESSOR] Failed to log audit for {signal_id}: {e}")

    # -----------------------------------------------------------------------
    # Schema Validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_arc_schema(response: Any) -> bool:
        """Validates that Claude's response matches the mandatory ARC Decision Schema.
        Clarification 008, Section 4.
        """
        if not isinstance(response, dict):
            return False
        required_keys = [
            "arc_decision", "arc_confidence", "reasoning_summary",
            "engine_alignment", "conflict_flags", "reject_reasons",
            "caution_reasons", "explainability", "arc_timestamp", "arc_version"
        ]
        if not all(k in response for k in required_keys):
            return False
        if response["arc_decision"] not in ("APPROVE", "CAUTION", "REJECT"):
            return False
        if not isinstance(response["arc_confidence"], int):
            return False
        if not (0 <= response["arc_confidence"] <= 100):
            return False
        return True

    # -----------------------------------------------------------------------
    # Post-Market Review (Clarification 008, Section 17 / interface contract)
    # -----------------------------------------------------------------------

    def run_postmarket(self, session_signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Runs post-market review of executed signals at 04:00 PM.
        Output is internal analytics — not delivered to operator.
        Clarification 008, Q3 (resolved).
        """
        try:
            claude = ServiceRegistry.get("claude")
            result = claude.review_signals_postmarket(session_signals)
            log_audit(
                component="ARC_ENGINE",
                action="POSTMARKET_REVIEW",
                result="SUCCESS",
                reason=f"Postmarket review completed. Reviewed {result.get('reviewed_count', 0)} signals.",
                metadata=result
            )
            return result
        except Exception as e:
            log_audit(
                component="ARC_ENGINE",
                action="POSTMARKET_REVIEW",
                result="FAILED",
                reason=f"Postmarket review failed: {str(e)}"
            )
            return {"status": "FAILED", "reviewed_count": 0, "error": str(e)}
