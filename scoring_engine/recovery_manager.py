import datetime
from decimal import Decimal
import database

class ScoringRecoveryManager:
    @staticmethod
    def recover_latest_score(symbol: str) -> dict:
        """Loads the most recent score audit from database for restart recovery."""
        query = """
            SELECT time, regime_score, rs_score, rvol_score, breadth_score, sector_score, 
                   trend_score, smc_score, options_score, final_composite_score
            FROM score_audits
            WHERE symbol = %s
            ORDER BY time DESC LIMIT 1;
        """
        try:
            res = database.execute_query(query, (symbol,), fetch=True)
            if res:
                row = res[0]
                return {
                    "time": row[0],
                    "symbol": symbol,
                    "regime_score": Decimal(str(row[1])),
                    "rs_score": Decimal(str(row[2])),
                    "rvol_score": Decimal(str(row[3])),
                    "breadth_score": Decimal(str(row[4])),
                    "sector_score": Decimal(str(row[5])),
                    "trend_score": Decimal(str(row[6])),
                    "smc_score": Decimal(str(row[7])),
                    "options_score": Decimal(str(row[8])),
                    "final_composite_score": Decimal(str(row[9])),
                    "status": "RECOVERED"
                }
        except Exception as e:
            print(f"[SCORING RECOVERY] Error recovering latest score for {symbol}: {e}")
            
        return {
            "status": "NEW"
        }
