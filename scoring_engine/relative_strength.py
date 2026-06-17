from decimal import Decimal
import datetime
import database

class RelativeStrengthScorer:
    @staticmethod
    def calculate_score(symbol: str, as_of_time: datetime.datetime, timeframe: str = "15m") -> Decimal:
        """Compares symbol's 20-period return vs NIFTY 50 index return.
        Symbol return > Index return -> 100.0
        Symbol return == Index return -> 50.0
        Symbol return < Index return -> 0.0
        """
        # Fetch last 20 candles for symbol
        query_sym = """
            SELECT close FROM market_data
            WHERE symbol = %s AND timeframe = %s AND time <= %s
            ORDER BY time DESC LIMIT 20;
        """
        # Fetch last 20 candles for index
        query_idx = """
            SELECT close FROM market_data
            WHERE symbol = 'NIFTY 50' AND timeframe = %s AND time <= %s
            ORDER BY time DESC LIMIT 20;
        """
        try:
            rows_sym = database.execute_query(query_sym, (symbol, timeframe, as_of_time), fetch=True)
            rows_idx = database.execute_query(query_idx, (timeframe, as_of_time), fetch=True)
            
            if len(rows_sym) >= 2 and len(rows_idx) >= 2:
                # Calculate % returns: (close_latest - close_oldest) / close_oldest
                sym_latest = Decimal(str(rows_sym[0][0]))
                sym_oldest = Decimal(str(rows_sym[-1][0]))
                sym_return = (sym_latest - sym_oldest) / sym_oldest if sym_oldest > 0 else Decimal("0")
                
                idx_latest = Decimal(str(rows_idx[0][0]))
                idx_oldest = Decimal(str(rows_idx[-1][0]))
                idx_return = (idx_latest - idx_oldest) / idx_oldest if idx_oldest > 0 else Decimal("0")
                
                if sym_return > idx_return:
                    return Decimal("100.0")
                elif sym_return < idx_return:
                    return Decimal("0.0")
                else:
                    return Decimal("50.0")
            
            # Fallback if index data is missing: check absolute symbol return
            if len(rows_sym) >= 2:
                sym_latest = Decimal(str(rows_sym[0][0]))
                sym_oldest = Decimal(str(rows_sym[-1][0]))
                if sym_latest > sym_oldest:
                    return Decimal("100.0")
                elif sym_latest < sym_oldest:
                    return Decimal("0.0")
                
        except Exception as e:
            print(f"[RS SCORER] Error calculating relative strength for {symbol}: {e}")
            
        return Decimal("50.0") # Neutral fallback
