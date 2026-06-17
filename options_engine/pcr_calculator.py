class PCRCalculator:
    @staticmethod
    def calculate_pcr(chain: list[dict]) -> dict:
        """Calculates Put-Call Ratio (PCR) on Open Interest and Volume."""
        total_call_oi = 0
        total_put_oi = 0
        total_call_vol = 0
        total_put_vol = 0

        for contract in chain:
            oi = contract.get("oi", 0)
            vol = contract.get("volume", 0)
            
            if contract["option_type"] == "CE":
                total_call_oi += oi
                total_call_vol += vol
            elif contract["option_type"] == "PE":
                total_put_oi += oi
                total_put_vol += vol

        pcr_oi = float(total_put_oi) / float(total_call_oi) if total_call_oi > 0 else 1.0
        pcr_volume = float(total_put_vol) / float(total_call_vol) if total_call_vol > 0 else 1.0

        return {
            "pcr_oi": round(pcr_oi, 4),
            "pcr_volume": round(pcr_volume, 4)
        }
