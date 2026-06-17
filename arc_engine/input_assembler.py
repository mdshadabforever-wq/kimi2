from decimal import Decimal
from typing import Dict, Any


class ARCInputAssembler:
    """Assembles the ARC Input Bundle from all upstream engine outputs.
    This is the canonical data structure passed to Claude for review.
    Defined by Clarification 008, Section 2.
    """

    @staticmethod
    def assemble(
        symbol: str,
        signal_id: str,
        as_of_time,
        trend_data: Dict[str, Any],
        smc_data: Dict[str, Any],
        options_data: Dict[str, Any],
        scoring_data: Dict[str, Any],
        risk_data: Dict[str, Any],
        geie_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assembles the full ARC Input Bundle for a single symbol signal.

        Args:
            symbol: Nifty 50 symbol.
            signal_id: Unique signal identifier.
            as_of_time: Datetime of the signal.
            trend_data: Output from TrendEngine.process_tick() or latest DB state.
            smc_data: Output from SMCEngine.generate_setup().
            options_data: Output from OptionsSignalEngine.process_option_update().
            scoring_data: Output from CompositeScoreCalculator.calculate_composite_score().
            risk_data: Risk state dict from RiskEngine.process_signal().
            geie_data: Per-symbol GEIE impact from GEIEProcessor.run_premarket().

        Returns:
            ARC Input Bundle dict ready for Claude prompt construction.
        """
        # Normalize Decimal fields to float for JSON serialization
        def to_float(val):
            if isinstance(val, Decimal):
                return float(val)
            return val

        # Extract trend fields
        trend_input = {
            "is_aligned": trend_data.get("is_aligned", False),
            "aligned_direction": trend_data.get("aligned_direction", "NEUTRAL"),
            "alignment_score": trend_data.get("alignment_score", 0),
            "timeframe_breakdown": trend_data.get("timeframe_breakdown", {
                "Daily": "NEUTRAL", "1h": "NEUTRAL", "15m": "NEUTRAL", "5m": "NEUTRAL"
            })
        }

        # Extract SMC fields
        smc_input = {
            "direction": smc_data.get("direction", "NO_DIRECTION"),
            "score": to_float(smc_data.get("score", 0)),
            "cross_timeframe_status": smc_data.get("cross_timeframe_status", "FAIL"),
            "confirmations_count": smc_data.get("confirmations_count", 0),
            "entry_low": to_float(smc_data.get("entry_low", 0)),
            "entry_high": to_float(smc_data.get("entry_high", 0)),
            "stop_loss": to_float(smc_data.get("stop_loss", 0)),
            "target_1": to_float(smc_data.get("target_1", 0)),
            "target_2": to_float(smc_data.get("target_2", 0)),
        }

        # Extract options fields
        options_input = {
            "pcr_oi": to_float(options_data.get("pcr_oi", 1.0)),
            "pcr_volume": to_float(options_data.get("pcr_volume", 1.0)),
            "max_pain_level": to_float(options_data.get("max_pain_level", 0)),
            "highest_call_oi_strike": to_float(options_data.get("highest_call_oi_strike", 0)),
            "highest_put_oi_strike": to_float(options_data.get("highest_put_oi_strike", 0)),
            "bias": options_data.get("bias", "NEUTRAL"),
        }

        # Extract scoring fields
        scoring_input = {
            "final_composite_score": to_float(scoring_data.get("final_composite_score", 0)),
            "risk_grade": scoring_data.get("risk_grade", "F"),
            "regime_score": to_float(scoring_data.get("regime_score", 50)),
            "rs_score": to_float(scoring_data.get("rs_score", 50)),
            "rvol_score": to_float(scoring_data.get("rvol_score", 50)),
            "breadth_score": to_float(scoring_data.get("breadth_score", 50)),
            "sector_score": to_float(scoring_data.get("sector_score", 50)),
            "trend_score": to_float(scoring_data.get("trend_score", 50)),
            "smc_score": to_float(scoring_data.get("smc_score", 50)),
            "options_score": to_float(scoring_data.get("options_score", 50)),
        }

        # Extract risk fields
        risk_input = {
            "status_code": risk_data.get("status_code", "UNKNOWN"),
            "quantity": risk_data.get("quantity", 0),
            "risk_amount": to_float(risk_data.get("risk_amount", 0)),
            "daily_risk_used_pct": to_float(
                risk_data.get("risk_state", {}).get("daily_risk_used", 0)
            ),
            "consecutive_losses": risk_data.get("risk_state", {}).get("consecutive_losses", 0),
            "hard_stop_active": risk_data.get("risk_state", {}).get("hard_stop_active", False),
        }

        # Extract per-symbol GEIE fields
        stock_impact = geie_data.get("stock_impacts", {}).get(symbol, {})
        geie_input = {
            "geie_status": geie_data.get("geie_status", "UNAVAILABLE"),
            "market_sentiment": geie_data.get("market_sentiment", "NEUTRAL"),
            "stock_impact": {
                "direction": stock_impact.get("direction", "NEUTRAL"),
                "magnitude": stock_impact.get("magnitude", 1),
                "confidence": stock_impact.get("confidence", "LOW"),
                "reasons": stock_impact.get("reasons", []),
                "urgency": stock_impact.get("urgency", "INTRADAY"),
            },
            "institutional_bias": geie_data.get("institutional_bias", "NEUTRAL"),
            "fii_5day_trend": geie_data.get("fii_5day_trend", "MIXED"),
            "key_support_from_options": geie_data.get("key_support_from_options", "N/A"),
            "key_resistance_from_options": geie_data.get("key_resistance_from_options", "N/A"),
        }

        return {
            "symbol": symbol,
            "signal_id": signal_id,
            "as_of_time": str(as_of_time),
            "trend_input": trend_input,
            "smc_input": smc_input,
            "options_input": options_input,
            "scoring_input": scoring_input,
            "risk_input": risk_input,
            "geie_input": geie_input,
        }

    @staticmethod
    def assemble_premarket(
        symbol: str,
        geie_data: Dict[str, Any],
        scoring_data: Dict[str, Any] = None,
        trend_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Assembles a lightweight pre-market bundle using only GEIE + scoring context.
        Used during the 08:20 AM batch review where live SMC/Options data is not yet available.
        """
        scoring_data = scoring_data or {}
        trend_data = trend_data or {}

        stock_impact = geie_data.get("stock_impacts", {}).get(symbol, {})

        return {
            "symbol": symbol,
            "signal_id": f"PREMARKET_{symbol}_{str(geie_data.get('timestamp', ''))[:10]}",
            "as_of_time": str(geie_data.get("timestamp", "")),
            "trend_input": {
                "is_aligned": trend_data.get("is_aligned", False),
                "aligned_direction": trend_data.get("aligned_direction", "NEUTRAL"),
                "alignment_score": trend_data.get("alignment_score", 0),
                "timeframe_breakdown": trend_data.get("timeframe_breakdown", {})
            },
            "smc_input": {"direction": "UNKNOWN", "score": 0, "cross_timeframe_status": "N/A",
                          "confirmations_count": 0},
            "options_input": {"pcr_oi": 1.0, "pcr_volume": 1.0, "bias": "NEUTRAL",
                              "max_pain_level": 0, "highest_call_oi_strike": 0,
                              "highest_put_oi_strike": 0},
            "scoring_input": {
                "final_composite_score": float(scoring_data.get("final_composite_score", 0)),
                "risk_grade": scoring_data.get("risk_grade", "F"),
                "regime_score": float(scoring_data.get("regime_score", 50)),
                "rs_score": float(scoring_data.get("rs_score", 50)),
                "rvol_score": float(scoring_data.get("rvol_score", 50)),
                "breadth_score": float(scoring_data.get("breadth_score", 50)),
                "sector_score": float(scoring_data.get("sector_score", 50)),
                "trend_score": float(scoring_data.get("trend_score", 50)),
                "smc_score": float(scoring_data.get("smc_score", 0)),
                "options_score": float(scoring_data.get("options_score", 50)),
            },
            "risk_input": {
                "status_code": "PREMARKET",
                "quantity": 0, "risk_amount": 0,
                "daily_risk_used_pct": 0, "consecutive_losses": 0, "hard_stop_active": False
            },
            "geie_input": {
                "geie_status": geie_data.get("geie_status", "UNAVAILABLE"),
                "market_sentiment": geie_data.get("market_sentiment", "NEUTRAL"),
                "stock_impact": {
                    "direction": stock_impact.get("direction", "NEUTRAL"),
                    "magnitude": stock_impact.get("magnitude", 1),
                    "confidence": stock_impact.get("confidence", "LOW"),
                    "reasons": stock_impact.get("reasons", []),
                    "urgency": stock_impact.get("urgency", "INTRADAY"),
                },
                "institutional_bias": geie_data.get("institutional_bias", "NEUTRAL"),
                "fii_5day_trend": geie_data.get("fii_5day_trend", "MIXED"),
                "key_support_from_options": geie_data.get("key_support_from_options", "N/A"),
                "key_resistance_from_options": geie_data.get("key_resistance_from_options", "N/A"),
            }
        }
