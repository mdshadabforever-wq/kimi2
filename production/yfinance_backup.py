import datetime
import sys
from decimal import Decimal
from typing import Dict, Any, List, Optional
import yfinance as yf

import database
from audit import log_audit

class YahooFinanceBackup:
    """Yahoo Finance Backup Layer.
    Provides backup data retrieval and historical close price reconciliation.
    Should never be used as a primary market feed.
    """

    @classmethod
    def fetch_historical_backup(cls, symbol: str, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Downloads daily candles from Yahoo Finance for a symbol."""
        # Convert Indian symbols (e.g. RELIANCE -> RELIANCE.NS)
        ticker = symbol.upper()
        if not ticker.endswith(".NS") and ticker not in ("^NSEI", "INDIAVIX"):
            ticker = f"{ticker}.NS"
        if ticker == "^NSEI":
            ticker = "^NSEI" # Nifty 50 Index
            
        print(f"[YFINANCE BACKUP] Downloading historical backup for ticker {ticker} ({start_date} to {end_date})...")
        try:
            df = yf.download(
                tickers=ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d",
                progress=False
            )
            
            # Flatten columns if MultiIndex (common in newer yfinance versions)
            if hasattr(df.columns, 'levels') or (len(df.columns) > 0 and isinstance(df.columns[0], tuple)):
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                
            records = []
            for ts, row in df.iterrows():
                # Extract close, open, high, low, volume
                # Handles pandas Series or scalar float formats
                records.append({
                    "time": ts.to_pydatetime(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                })
            print(f"[YFINANCE BACKUP] Retrieved {len(records)} daily records from Yahoo Finance.")

            return records
        except Exception as e:
            print(f"[YFINANCE BACKUP] Failed to fetch data: {e}", file=sys.stderr)
            return []

    @classmethod
    def reconcile_market_data(cls, symbol: str, check_date: datetime.date) -> bool:
        """Compares DB market_data close price against Yahoo Finance close price.
        Logs warning audits on discrepancies > 0.5% as per specifications.
        """
        # 1. Fetch close price from DB
        query = "SELECT close FROM market_data WHERE symbol = %s AND time::date = %s AND timeframe = 'Daily';"
        db_res = database.execute_query(query, (symbol, check_date), fetch=True)
        if not db_res or db_res[0][0] is None:
            print(f"[YFINANCE RECONCILE] Primary market data missing in DB for {symbol} on {check_date}. Cannot reconcile.")
            return False
            
        db_close = float(db_res[0][0])
        
        # 2. Fetch close price from Yahoo
        y_records = cls.fetch_historical_backup(symbol, check_date, check_date + datetime.timedelta(days=1))
        if not y_records:
            print(f"[YFINANCE RECONCILE] Yahoo Finance backup data missing for {symbol} on {check_date}. Cannot reconcile.")
            return False
            
        y_close = y_records[0]["close"]
        
        # 3. Calculate deviation
        deviation = abs(db_close - y_close) / db_close
        is_matched = deviation <= 0.005 # 0.5% threshold
        
        if not is_matched:
            msg = f"PRICE DEVIATION WARNING: close price discrepancy on {symbol} for date {check_date}. DB close: {db_close:.2f}, Yahoo close: {y_close:.2f} (deviation {deviation*100:.2f}%)."
            print(f"[YFINANCE RECONCILE] {msg}", file=sys.stderr)
            
            # Log mismatch audit
            log_audit(
                component="DataReconciler",
                action="RECONCILE_PRICE_MISMATCH",
                result="WARNING",
                reason=msg,
                metadata={"symbol": symbol, "date": str(check_date), "db_close": db_close, "y_close": y_close, "deviation_pct": deviation * 100}
            )
        else:
            print(f"[YFINANCE RECONCILE] Price check matches for {symbol} on {check_date}. DB: {db_close:.2f}, Yahoo: {y_close:.2f} (diff: {deviation*100:.3f}%).")
            
        return is_matched
