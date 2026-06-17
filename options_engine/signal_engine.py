import datetime
import time
from decimal import Decimal
import database
from options_engine.option_chain_loader import OptionChainLoader
from options_engine.pcr_calculator import PCRCalculator
from options_engine.max_pain import MaxPainCalculator
from options_engine.concentration_analyzer import ConcentrationAnalyzer
from options_engine.buildup_detector import BuildupDetector
from options_engine.persistence import OptionsPersistence
from options_engine.telemetry import OptionsTelemetry

class OptionsSignalEngine:
    def __init__(self):
        # Cache of the last processed chain per symbol
        # Key: symbol, Value: list of option chain dicts
        self.last_chains = {}

    def process_option_update(self, symbol: str, expiry: datetime.date, as_of_time: datetime.datetime) -> dict:
        """Processes the option chain for a symbol at a given timestamp.
        Calculates PCR, Max Pain, Buildup, and concentration, determines bias,
        persists results to the database, logs latency, and returns the result.
        """
        start_time = time.perf_counter()

        # 1. Load the current option chain
        current_chain = OptionChainLoader.load_chain(symbol, expiry, as_of_time)
        if not current_chain:
            return self._empty_result(symbol)

        # 2. Get the previous chain (from memory or query database for the previous timestamp)
        prev_chain = self.last_chains.get(symbol)
        if not prev_chain:
            prev_chain = self._load_previous_chain_from_db(symbol, expiry, as_of_time)

        # Update cache
        self.last_chains[symbol] = current_chain

        # 3. Calculate Put-Call Ratio
        pcr_metrics = PCRCalculator.calculate_pcr(current_chain)

        # 4. Calculate Max Pain
        max_pain_val = MaxPainCalculator.calculate_max_pain(current_chain)

        # 5. Analyze OI Concentration
        concentration = ConcentrationAnalyzer.analyze_concentration(current_chain)

        # 6. Analyze Buildups
        buildup_counts = BuildupDetector.analyze_chain_buildups(current_chain, prev_chain or [])

        # 7. Determine options bias
        bias = self._determine_bias(pcr_metrics["pcr_oi"], concentration, buildup_counts)

        # 8. Save options intelligence to DB (date, symbol)
        as_of_date = as_of_time.date()
        OptionsPersistence.save_intelligence(
            date=as_of_date,
            symbol=symbol,
            max_pain=max_pain_val,
            highest_put_strike=concentration["highest_put_oi_strike"],
            highest_call_strike=concentration["highest_call_oi_strike"]
        )

        # 9. Record latency telemetry
        duration_ms = (time.perf_counter() - start_time) * 1000
        OptionsTelemetry.record_latency(symbol, duration_ms)

        return {
            "symbol": symbol,
            "time": as_of_time,
            "pcr_oi": pcr_metrics["pcr_oi"],
            "pcr_volume": pcr_metrics["pcr_volume"],
            "max_pain_level": max_pain_val,
            "highest_call_oi_strike": concentration["highest_call_oi_strike"],
            "highest_put_oi_strike": concentration["highest_put_oi_strike"],
            "ce_concentration": concentration["ce_concentration"],
            "pe_concentration": concentration["pe_concentration"],
            "buildup_stats": buildup_counts,
            "bias": bias
        }

    def _load_previous_chain_from_db(self, symbol: str, expiry: datetime.date, current_time: datetime.datetime) -> list[dict]:
        """Queries the database to find the option chain from the previous timestamp."""
        query = """
            SELECT DISTINCT time FROM options_data
            WHERE symbol = %s AND expiry = %s AND time < %s
            ORDER BY time DESC LIMIT 1;
        """
        try:
            res = database.execute_query(query, (symbol, expiry, current_time), fetch=True)
            if res:
                prev_time = res[0][0]
                return OptionChainLoader.load_chain(symbol, expiry, prev_time)
        except Exception:
            pass
        return []

    def _determine_bias(self, pcr_oi: float, concentration: dict, buildup_counts: dict) -> str:
        """Determines the aggregate options bias (BULLISH/BEARISH/NEUTRAL) by scoring component metrics."""
        score = 0

        # PCR Scoring
        if pcr_oi > 1.3:
            score += 1
        elif pcr_oi < 0.7:
            score -= 1

        # Concentration Scoring
        hp = concentration["highest_put_oi_strike"]
        hc = concentration["highest_call_oi_strike"]
        if hp > 0 and hc > 0:
            if hp > hc:
                score += 1
            elif hc > hp:
                score -= 1

        # Buildup Scoring
        ce_bullish = buildup_counts["CE"]["LONG BUILDUP"] + buildup_counts["CE"]["SHORT COVERING"]
        ce_bearish = buildup_counts["CE"]["SHORT BUILDUP"] + buildup_counts["CE"]["LONG UNWINDING"]
        pe_bullish = buildup_counts["PE"]["SHORT COVERING"] + buildup_counts["PE"]["LONG BUILDUP"]
        pe_bearish = buildup_counts["PE"]["LONG UNWINDING"] + buildup_counts["PE"]["SHORT BUILDUP"]

        total_bullish = ce_bullish + pe_bullish
        total_bearish = ce_bearish + pe_bearish

        if total_bullish > total_bearish:
            score += 1
        elif total_bearish > total_bullish:
            score -= 1

        if score > 0:
            return "BULLISH"
        elif score < 0:
            return "BEARISH"
        return "NEUTRAL"

    def _empty_result(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "time": None,
            "pcr_oi": 1.0,
            "pcr_volume": 1.0,
            "max_pain_level": Decimal("0"),
            "highest_call_oi_strike": Decimal("0"),
            "highest_put_oi_strike": Decimal("0"),
            "ce_concentration": 0.0,
            "pe_concentration": 0.0,
            "buildup_stats": {
                "CE": {"LONG BUILDUP": 0, "SHORT BUILDUP": 0, "LONG UNWINDING": 0, "SHORT COVERING": 0, "NEUTRAL": 0},
                "PE": {"LONG BUILDUP": 0, "SHORT BUILDUP": 0, "LONG UNWINDING": 0, "SHORT COVERING": 0, "NEUTRAL": 0}
            },
            "bias": "NEUTRAL"
        }
