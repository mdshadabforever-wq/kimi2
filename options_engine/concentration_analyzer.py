from decimal import Decimal

class ConcentrationAnalyzer:
    @staticmethod
    def analyze_concentration(chain: list[dict]) -> dict:
        """Finds the highest Call/Put OI strikes and calculates top-3 concentration ratios."""
        ce_chain = [c for c in chain if c["option_type"] == "CE"]
        pe_chain = [c for c in chain if c["option_type"] == "PE"]

        # Sort CE and PE contracts by Open Interest descending
        ce_sorted = sorted(ce_chain, key=lambda x: x["oi"], reverse=True)
        pe_sorted = sorted(pe_chain, key=lambda x: x["oi"], reverse=True)

        highest_call_oi_strike = Decimal(str(ce_sorted[0]["strike"])) if ce_sorted else Decimal("0")
        highest_put_oi_strike = Decimal(str(pe_sorted[0]["strike"])) if pe_sorted else Decimal("0")

        total_ce_oi = sum(c["oi"] for c in ce_chain)
        total_pe_oi = sum(c["oi"] for c in pe_chain)

        # Top 3 CE strikes
        top_3_ce_oi = sum(c["oi"] for c in ce_sorted[:3])
        # Top 3 PE strikes
        top_3_pe_oi = sum(c["oi"] for c in pe_sorted[:3])

        ce_concentration = float(top_3_ce_oi) / float(total_ce_oi) if total_ce_oi > 0 else 0.0
        pe_concentration = float(top_3_pe_oi) / float(total_pe_oi) if total_pe_oi > 0 else 0.0

        return {
            "highest_call_oi_strike": highest_call_oi_strike,
            "highest_put_oi_strike": highest_put_oi_strike,
            "ce_concentration": round(ce_concentration, 4),
            "pe_concentration": round(pe_concentration, 4)
        }
