class DirectionMapper:
    @staticmethod
    def map_direction(structures_5m: list[dict], structures_15m: list[dict]) -> str:
        """Determines the mapped signal direction based on the frozen IIIS v4.6 rules:
          - LONG: At least one Bullish Break (BOS/CHOCH) AND one Bullish Zone (OB/FVG)
          - SHORT: At least one Bearish Break (BOS/CHOCH) AND one Bearish Zone (OB/FVG)
          - Mixed or insufficient: NO_DIRECTION
        """
        all_structures = structures_5m + structures_15m
        
        # Bullish components
        has_bull_break = any(s["structure_type"] in ["BOS", "CHOCH"] and s["direction"] == "BULLISH" for s in all_structures)
        has_bull_zone = any(s["structure_type"] in ["OB", "FVG"] and s["direction"] == "BULLISH" for s in all_structures)
        
        # Bearish components
        has_bear_break = any(s["structure_type"] in ["BOS", "CHOCH"] and s["direction"] == "BEARISH" for s in all_structures)
        has_bear_zone = any(s["structure_type"] in ["OB", "FVG"] and s["direction"] == "BEARISH" for s in all_structures)
        
        is_long = has_bull_break and has_bull_zone
        is_short = has_bear_break and has_bear_zone
        
        # If both bullish and bearish components are present, it is mixed
        has_any_bull = has_bull_break or has_bull_zone
        has_any_bear = has_bear_break or has_bear_zone
        if has_any_bull and has_any_bear:
            return "NO_DIRECTION"
            
        if is_long:
            return "LONG"
        elif is_short:
            return "SHORT"
            
        return "NO_DIRECTION"
