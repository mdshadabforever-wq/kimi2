from decimal import Decimal
from config import Config

class GateValidator:
    @staticmethod
    def validate_gates(
        symbol: str, 
        target_risk_pct: Decimal, 
        current_state: dict, 
        has_duplicate: bool,
        market_context: dict = None
    ) -> tuple[bool, str]:
        """Runs all risk verification gates.
        
        Returns:
            A tuple of (is_passed, status_code).
        """
        # Daily risk engine limits
        if current_state.get("hard_stop_active", False):
            return False, "BLOCK_HARD_STOP"

        if current_state.get("consecutive_losses", 0) >= Config.HARD_STOP_LOSSES:
            current_state["hard_stop_active"] = True
            return False, "BLOCK_CONSECUTIVE_LOSSES"

        daily_used = Decimal(str(current_state.get("daily_risk_used", "0.0")))
        max_daily_pct = Decimal(str(Config.MAX_DAILY_RISK_PCT))
        if daily_used + target_risk_pct > max_daily_pct:
            return False, "BLOCK_DAILY_RISK_LIMIT"

        if has_duplicate:
            return False, "BLOCK_DUPLICATE_SIGNAL"

        # Step 10: Sequential Risk Gates
        if market_context:
            # GATE 1 — LIQUIDITY
            # Min ADTV ₹50 Crore
            adtv = Decimal(str(market_context.get("adtv", 500000000)))
            if adtv < Decimal("500000000"):
                return False, "BLOCK_LIQUIDITY_ADTV"
            # Max spread 0.20%
            spread_pct = Decimal(str(market_context.get("spread_pct", 0.001)))
            if spread_pct > Decimal("0.0020"):
                return False, "BLOCK_LIQUIDITY_SPREAD"
            # Min session RVOL 1.0
            rvol = Decimal(str(market_context.get("rvol", 1.0)))
            if rvol < Decimal("1.0"):
                return False, "BLOCK_LIQUIDITY_RVOL"

            # GATE 2 — SMC VALIDATION
            smc_confirmed = market_context.get("smc_confirmed", True)
            if not smc_confirmed:
                return False, "BLOCK_SMC_VALIDATION"

            # GATE 3 — CORRELATION
            # Max 2 alerts same sector per 30 min
            sector_alerts_last_30m = int(market_context.get("sector_alerts_last_30m", 0))
            if sector_alerts_last_30m >= 2:
                return False, "BLOCK_CORRELATION_SECTOR"
            # Max 4 active alerts total
            total_active_alerts = int(market_context.get("total_active_alerts", 0))
            if total_active_alerts >= 4:
                return False, "BLOCK_CORRELATION_TOTAL"

            # GATE 4 — EARNINGS
            earnings_within_24h = market_context.get("earnings_within_24h", False)
            if earnings_within_24h:
                return False, "BLOCK_EARNINGS_RISK"

            # GATE 5 — EVENT RISK
            minutes_to_next = float(market_context.get("minutes_to_next_macro_event", 9999))
            minutes_since_last = float(market_context.get("minutes_since_last_macro_event", 9999))
            if minutes_to_next <= 15.0 or minutes_since_last <= 15.0:
                return False, "BLOCK_EVENT_RISK"

            # GATE 6 — CHOPPY FILTER
            nifty_adx = float(market_context.get("nifty_adx", 25.0))
            nifty_ad_ratio = float(market_context.get("nifty_ad_ratio", 1.5))
            nifty_inside_atr_30m = market_context.get("nifty_inside_atr_30m", False)
            if nifty_adx < 20.0 and (0.9 <= nifty_ad_ratio <= 1.1) and nifty_inside_atr_30m:
                return False, "BLOCK_CHOPPY_MARKET"

            # GATE 7 — CIRCUIT BREAKER
            nifty_15m_move_pct = float(market_context.get("nifty_15m_move_pct", 0.0))
            if nifty_15m_move_pct > 1.5:
                return False, "BLOCK_CIRCUIT_BREAKER"

            # GATE 8 — VOLATILITY REGIME
            nifty_atr_vs_30day_ratio = float(market_context.get("nifty_atr_vs_30day_ratio", 1.0))
            if nifty_atr_vs_30day_ratio > 1.5:
                return False, "BLOCK_ATR_VOLATILITY"

        return True, "PASS"

