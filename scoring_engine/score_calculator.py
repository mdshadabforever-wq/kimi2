import datetime
import time
from decimal import Decimal
from scoring_engine.market_regime import MarketRegimeScorer
from scoring_engine.relative_strength import RelativeStrengthScorer
from scoring_engine.relative_volume import RelativeVolumeScorer
from scoring_engine.breadth_engine import MarketBreadthScorer
from scoring_engine.sector_strength import SectorStrengthScorer
from scoring_engine.persistence import ScoringPersistence
from scoring_engine.telemetry import ScoringTelemetry

class CompositeScoreCalculator:
    @staticmethod
    def calculate_composite_score(
        symbol: str,
        as_of_time: datetime.datetime,
        trend_score: Decimal,
        smc_score: Decimal,
        options_score: Decimal,
        timeframe: str = "15m"
    ) -> dict:
        """Calculates the weighted Composite Score and records audit entries and telemetry."""
        start_time = time.perf_counter()

        # 1. Calculate component sub-scores
        regime = MarketRegimeScorer.calculate_score(symbol, as_of_time)
        rs = RelativeStrengthScorer.calculate_score(symbol, as_of_time, timeframe)
        rvol = RelativeVolumeScorer.calculate_score(symbol, as_of_time, timeframe)
        breadth = MarketBreadthScorer.calculate_score(as_of_time, timeframe)
        sector = SectorStrengthScorer.calculate_score(symbol, as_of_time, timeframe)

        # Ensure Decimal formatting
        trend = Decimal(str(trend_score))
        smc = Decimal(str(smc_score))
        options = Decimal(str(options_score))

        # 2. Apply Weight Allocations
        # Regime: 25%, RS: 20%, RVOL: 15%, Breadth: 10%, Options: 10%, Sector: 10%, SMC Quality: 10%
        final_score = (
            regime * Decimal("25.0") +
            rs * Decimal("20.0") +
            rvol * Decimal("15.0") +
            breadth * Decimal("10.0") +
            sector * Decimal("10.0") +
            smc * Decimal("10.0") +
            options * Decimal("10.0")
        ) / Decimal("100.0")
        
        final_score = Decimal(str(round(final_score, 2)))

        # 3. Save Score Audit Entry
        ScoringPersistence.save_audit(
            time=as_of_time,
            symbol=symbol,
            regime=regime,
            rs=rs,
            rvol=rvol,
            breadth=breadth,
            sector=sector,
            trend=trend,
            smc=smc,
            options=options,
            final_score=final_score
        )

        # 4. Record Latency Telemetry
        duration_ms = (time.perf_counter() - start_time) * 1000
        ScoringTelemetry.record_latency(symbol, duration_ms)

        # 5. Threshold Validation Rule: >= 86.0 passes (strictly > 85.0)
        is_accepted = final_score >= Decimal("86.0")

        return {
            "symbol": symbol,
            "time": as_of_time,
            "regime_score": regime,
            "rs_score": rs,
            "rvol_score": rvol,
            "breadth_score": breadth,
            "sector_score": sector,
            "trend_score": trend,
            "smc_score": smc,
            "options_score": options,
            "final_composite_score": final_score,
            "is_accepted": is_accepted
        }
