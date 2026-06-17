class BuildupDetector:
    @staticmethod
    def detect_buildup(current_ltp: float, prev_ltp: float, current_oi: int, prev_oi: int) -> str:
        """Determines the buildup classification for a single contract."""
        delta_price = float(current_ltp) - float(prev_ltp)
        delta_oi = int(current_oi) - int(prev_oi)

        if delta_price > 0 and delta_oi > 0:
            return "LONG BUILDUP"
        elif delta_price < 0 and delta_oi > 0:
            return "SHORT BUILDUP"
        elif delta_price < 0 and delta_oi < 0:
            return "LONG UNWINDING"
        elif delta_price > 0 and delta_oi < 0:
            return "SHORT COVERING"
        else:
            return "NEUTRAL"

    @staticmethod
    def analyze_chain_buildups(current_chain: list[dict], prev_chain: list[dict]) -> dict:
        """Compares current and previous chains to count buildup statistics."""
        # Create lookup for previous chain
        prev_lookup = {(c["strike"], c["option_type"]): c for c in prev_chain}
        
        counts = {
            "CE": {"LONG BUILDUP": 0, "SHORT BUILDUP": 0, "LONG UNWINDING": 0, "SHORT COVERING": 0, "NEUTRAL": 0},
            "PE": {"LONG BUILDUP": 0, "SHORT BUILDUP": 0, "LONG UNWINDING": 0, "SHORT COVERING": 0, "NEUTRAL": 0}
        }

        for curr in current_chain:
            key = (curr["strike"], curr["option_type"])
            prev = prev_lookup.get(key)
            
            if prev:
                state = BuildupDetector.detect_buildup(
                    curr["ltp"], prev["ltp"], curr["oi"], prev["oi"]
                )
            else:
                # If no previous, check if we can use the 'oi_change' column
                # Since we don't have previous ltp, we can't determine price direction, so default to NEUTRAL
                state = "NEUTRAL"
                
            opt_type = curr["option_type"]
            counts[opt_type][state] += 1

        return counts
