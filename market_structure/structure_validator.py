class StructureValidator:
    @staticmethod
    def validate_cross_timeframe(structures_5m: list[dict], structures_15m: list[dict], direction: str) -> tuple[bool, str]:
        """Enforces the mandatory cross-timeframe validation rule:
          - Minimum 2 valid confirmations total
          - At least 1 structure must be from the 5m chart
          - At least 1 structure must be from the 15m chart
          - Confirmations must align in direction ('BULLISH' for LONG setups, 'BEARISH' for SHORT setups)
        """
        # Filter confirmations that align with the desired direction
        valid_5m = [s for s in structures_5m if s["direction"] == direction]
        valid_15m = [s for s in structures_15m if s["direction"] == direction]
        
        total_confirmations = len(valid_5m) + len(valid_15m)
        
        is_valid = len(valid_5m) >= 1 and len(valid_15m) >= 1 and total_confirmations >= 2
        status = "PASS" if is_valid else "FAIL"
        
        return is_valid, status
