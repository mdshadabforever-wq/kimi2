class OIAnalyzer:
    @staticmethod
    def analyze_oi(chain: list[dict]) -> dict:
        """Aggregates Call and Put Open Interest and its changes from the option chain."""
        total_call_oi = 0
        total_put_oi = 0
        call_oi_delta = 0
        put_oi_delta = 0

        for contract in chain:
            oi = contract.get("oi", 0)
            oi_change = contract.get("oi_change", 0)
            
            if contract["option_type"] == "CE":
                total_call_oi += oi
                call_oi_delta += oi_change
            elif contract["option_type"] == "PE":
                total_put_oi += oi
                put_oi_delta += oi_change

        return {
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "call_oi_delta": call_oi_delta,
            "put_oi_delta": put_oi_delta
        }
