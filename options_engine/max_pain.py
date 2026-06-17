from decimal import Decimal

class MaxPainCalculator:
    @staticmethod
    def calculate_max_pain(chain: list[dict]) -> Decimal:
        """Calculates the Max Pain strike level for the option chain.
        Max Pain is the strike that minimizes total buyer loss.
        """
        if not chain:
            return Decimal("0")

        # Extract all unique strikes
        strikes = sorted(list(set(c["strike"] for c in chain)))
        
        # Organize chain by strike and type
        ce_oi = {}
        pe_oi = {}
        for c in chain:
            strike = c["strike"]
            oi = c["oi"]
            if c["option_type"] == "CE":
                ce_oi[strike] = ce_oi.get(strike, 0) + oi
            elif c["option_type"] == "PE":
                pe_oi[strike] = pe_oi.get(strike, 0) + oi

        min_pain = None
        max_pain_strike = Decimal("0")

        for s in strikes:
            total_pain = Decimal("0")
            for k in strikes:
                # CE pain: option buyer makes money if K > s
                if k > s:
                    total_pain += (k - s) * Decimal(str(ce_oi.get(k, 0)))
                # PE pain: option buyer makes money if s > K
                if s > k:
                    total_pain += (s - k) * Decimal(str(pe_oi.get(k, 0)))
            
            if min_pain is None or total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = s

        return max_pain_strike
