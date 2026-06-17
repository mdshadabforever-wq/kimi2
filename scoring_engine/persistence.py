import datetime
from decimal import Decimal
import database

class ScoringPersistence:
    @staticmethod
    def save_audit(
        time: datetime.datetime,
        symbol: str,
        regime: Decimal,
        rs: Decimal,
        rvol: Decimal,
        breadth: Decimal,
        sector: Decimal,
        trend: Decimal,
        smc: Decimal,
        options: Decimal,
        final_score: Decimal
    ):
        """Saves a score audit record to the score_audits table."""
        query = """
            INSERT INTO score_audits (
                time, symbol, regime_score, rs_score, rvol_score, breadth_score, 
                sector_score, trend_score, smc_score, options_score, final_composite_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, symbol)
            DO UPDATE SET
                regime_score = EXCLUDED.regime_score,
                rs_score = EXCLUDED.rs_score,
                rvol_score = EXCLUDED.rvol_score,
                breadth_score = EXCLUDED.breadth_score,
                sector_score = EXCLUDED.sector_score,
                trend_score = EXCLUDED.trend_score,
                smc_score = EXCLUDED.smc_score,
                options_score = EXCLUDED.options_score,
                final_composite_score = EXCLUDED.final_composite_score;
        """
        try:
            database.execute_query(query, (
                time, symbol, regime, rs, rvol, breadth,
                sector, trend, smc, options, final_score
            ))
        except Exception as e:
            print(f"[SCORING PERSISTENCE] Error saving score audit for {symbol}: {e}")

    @staticmethod
    def load_audit(symbol: str, time: datetime.datetime) -> dict:
        """Loads a specific score audit record historically."""
        query = """
            SELECT regime_score, rs_score, rvol_score, breadth_score, sector_score, 
                   trend_score, smc_score, options_score, final_composite_score
            FROM score_audits
            WHERE symbol = %s AND time = %s;
        """
        try:
            res = database.execute_query(query, (symbol, time), fetch=True)
            if res:
                row = res[0]
                return {
                    "time": time,
                    "symbol": symbol,
                    "regime_score": Decimal(str(row[0])),
                    "rs_score": Decimal(str(row[1])),
                    "rvol_score": Decimal(str(row[2])),
                    "breadth_score": Decimal(str(row[3])),
                    "sector_score": Decimal(str(row[4])),
                    "trend_score": Decimal(str(row[5])),
                    "smc_score": Decimal(str(row[6])),
                    "options_score": Decimal(str(row[7])),
                    "final_composite_score": Decimal(str(row[8]))
                }
        except Exception as e:
            print(f"[SCORING PERSISTENCE] Error loading score audit for {symbol}: {e}")
        return None
