import math
from decimal import Decimal
from config import Config

class PositionSizer:
    @staticmethod
    def calculate_size(
        entry_low: Decimal, 
        entry_high: Decimal, 
        stop_loss: Decimal, 
        direction: str, 
        capital: float = None, 
        risk_pct: float = None,
        india_vix: float = 14.0,
        enable_cap: bool = False
    ) -> dict:
        """Calculates trade quantity and risk amount based on config settings, stop loss distance, and VIX.
        
        Args:
            entry_low: The low boundary of the entry zone.
            entry_high: The high boundary of the entry zone.
            stop_loss: The stop loss price.
            direction: LONG or SHORT.
            capital: Optional override of capital size.
            risk_pct: Optional override of risk percentage.
            india_vix: The current India VIX index value.
            enable_cap: Whether to apply the maximum 10% position value cap.
            
        Returns:
            A dictionary containing:
              - quantity: calculated quantity (int)
              - risk_amount: target risk amount in currency (Decimal)
              - entry_avg: average entry price (Decimal)
        """
        cap = capital if capital is not None else Config.CAPITAL
        rp = risk_pct if risk_pct is not None else Config.RISK_PCT

        # Calculate target risk amount
        target_risk = Decimal(str(cap)) * Decimal(str(rp)) / Decimal("100.0")

        # Average entry price
        entry_avg = (Decimal(str(entry_low)) + Decimal(str(entry_high))) / Decimal("2.0")

        # Calculate price distance
        price_diff = Decimal(str(entry_avg)) - Decimal(str(stop_loss))
        if direction.upper() == "SHORT":
            price_diff = Decimal(str(stop_loss)) - Decimal(str(entry_avg))

        # Guard against zero or negative distance
        if price_diff <= 0:
            return {
                "quantity": 0,
                "risk_amount": Decimal("0.0"),
                "entry_avg": entry_avg
            }

        # Apply minimum stop distance of 0.1% of entry price
        min_stop_distance = entry_avg * Decimal("0.001")
        if price_diff < min_stop_distance:
            price_diff = min_stop_distance

        # Determine VIX Adjustment
        vix_factor = Decimal("1.0")
        if india_vix > 20.0:
            vix_factor = Decimal("0.5")
        elif india_vix >= 15.0:
            vix_factor = Decimal("0.75")

        # Calculate raw quantity
        qty = math.floor((target_risk / price_diff) * vix_factor)

        # Apply Maximum position cap (10% of capital) if enabled
        if enable_cap:
            max_position_value = Decimal(str(cap)) * Decimal("0.10")
            if qty * entry_avg > max_position_value:
                qty = math.floor(max_position_value / entry_avg)

        if qty < 0:
            qty = 0

        # Risk amount actually taken
        actual_risk = Decimal(str(qty)) * price_diff

        return {
            "quantity": qty,
            "risk_amount": Decimal(str(round(actual_risk, 2))),
            "entry_avg": Decimal(str(round(entry_avg, 4)))
        }

