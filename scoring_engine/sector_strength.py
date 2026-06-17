from decimal import Decimal
import datetime
import database

# Simple static symbol to sector mapping for NIFTY 50
SECTOR_MAP = {
    "RELIANCE": "ENERGY", "ONGC": "ENERGY", "BPCL": "ENERGY", "COALINDIA": "ENERGY", "NTPC": "ENERGY", "POWERGRID": "ENERGY",
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT", "LTIM": "IT",
    "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING", "AXISBANK": "BANKING", "KOTAKBANK": "BANKING", "INDUSINDBK": "BANKING",
    "TATASTEEL": "METALS", "JINDALSTEL": "METALS", "HINDALCO": "METALS", "JSWSTEEL": "METALS",
    "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG", "TATACONSUM": "FMCG",
    "BHARTIARTL": "TELECOM",
    "L&T": "INFRASTRUCTURE", "LT": "INFRASTRUCTURE"
}

class SectorStrengthScorer:
    @staticmethod
    def calculate_score(symbol: str, as_of_time: datetime.datetime, timeframe: str = "15m") -> Decimal:
        """Calculates sector return compared to NIFTY 50 index return.
        Sector Average Return > Index Return -> 100.0
        Sector Average Return == Index Return -> 50.0
        Sector Average Return < Index Return -> 0.0
        """
        sector = SECTOR_MAP.get(symbol.upper(), "OTHER")
        if sector == "OTHER":
            return Decimal("50.0") # Default neutral score

        # Find other symbols in the same sector
        sector_symbols = [k for k, v in SECTOR_MAP.items() if v == sector]
        
        # Calculate sector average return
        returns = []
        try:
            for s in sector_symbols:
                query = """
                    SELECT close FROM market_data
                    WHERE symbol = %s AND timeframe = %s AND time <= %s
                    ORDER BY time DESC LIMIT 2;
                """
                rows = database.execute_query(query, (s, timeframe, as_of_time), fetch=True)
                if len(rows) >= 2:
                    ret = (Decimal(str(rows[0][0])) - Decimal(str(rows[1][0]))) / Decimal(str(rows[1][0]))
                    returns.append(ret)
            
            # Fetch index return
            query_idx = """
                SELECT close FROM market_data
                WHERE symbol = 'NIFTY 50' AND timeframe = %s AND time <= %s
                ORDER BY time DESC LIMIT 2;
            """
            rows_idx = database.execute_query(query_idx, (timeframe, as_of_time), fetch=True)
            
            if returns and len(rows_idx) >= 2:
                avg_sector_return = sum(returns) / len(returns)
                idx_return = (Decimal(str(rows_idx[0][0])) - Decimal(str(rows_idx[1][0]))) / Decimal(str(rows_idx[1][0]))
                
                if avg_sector_return > idx_return:
                    return Decimal("100.0")
                elif avg_sector_return < idx_return:
                    return Decimal("0.0")
                else:
                    return Decimal("50.0")
        except Exception as e:
            print(f"[SECTOR SCORER] Error calculating sector return for {symbol}: {e}")
            
        return Decimal("50.0") # Fallback to neutral
