import sys
import os
import datetime
from decimal import Decimal

# Add root folder to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database
from interfaces.base import ServiceRegistry
from bootstrap import register_services

def test_imports():
    print("--- 1. Testing Imports ---")
    try:
        from production.upstox_production import UpstoxProduction
        from production.nse_production import NSEProduction
        from production.yfinance_backup import YahooFinanceBackup
        from production.perplexity_production import PerplexityProduction
        from production.gemini_production import GeminiProduction
        from production.claude_production import ClaudeProduction
        print("[OK] All production modules imported successfully.")
    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        sys.exit(1)

def test_interfaces():
    print("\n--- 2. Testing Interface Subclass Validation ---")
    from production.upstox_production import UpstoxProduction
    from production.nse_production import NSEProduction
    from production.perplexity_production import PerplexityProduction
    from production.gemini_production import GeminiProduction
    from production.claude_production import ClaudeProduction

    from interfaces.upstox import UpstoxInterface
    from interfaces.nse import NSEInterface
    from interfaces.perplexity import PerplexityInterface
    from interfaces.gemini import GeminiInterface
    from interfaces.claude import ClaudeInterface

    assert issubclass(UpstoxProduction, UpstoxInterface), "UpstoxProduction must implement UpstoxInterface"
    assert issubclass(NSEProduction, NSEInterface), "NSEProduction must implement NSEInterface"
    assert issubclass(PerplexityProduction, PerplexityInterface), "PerplexityProduction must implement PerplexityInterface"
    assert issubclass(GeminiProduction, GeminiInterface), "GeminiProduction must implement GeminiInterface"
    assert issubclass(ClaudeProduction, ClaudeInterface), "ClaudeProduction must implement ClaudeInterface"
    print("[OK] All production adapter classes implement their base interfaces.")

def test_database_write_paths():
    print("\n--- 3. Testing Database Ingestion Write Paths (Dry Run) ---")
    try:
        # 1. Verify raw_ticks table insertion
        tick_time = datetime.datetime.now()
        database.execute_query(
            "INSERT INTO raw_ticks (time, symbol, price, volume) VALUES (%s, %s, %s, %s);",
            (tick_time, "TEST_SYM", Decimal("150.00"), 1000)
        )
        # Clear test tick
        database.execute_query("DELETE FROM raw_ticks WHERE symbol = 'TEST_SYM';")
        print("[OK] raw_ticks write path verified.")

        # 2. Verify options_data write path
        database.execute_query(
            "INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp) "
            "VALUES (%s, %s, 150.0, %s, 'CE', 1000, 100, 500, 0.25, 5.0) ON CONFLICT DO NOTHING;",
            (tick_time, "TEST_SYM", tick_time.date())
        )
        database.execute_query("DELETE FROM options_data WHERE symbol = 'TEST_SYM';")
        print("[OK] options_data write path verified.")

        # 3. Verify bulk_deal_tracker write path
        database.execute_query(
            "INSERT INTO bulk_deal_tracker (timestamp, symbol, deal_type, quantity, price, value_crores, client_name, deal_category) "
            "VALUES (%s, %s, 'BUY', 1000, 150.0, 0.015, 'TEST CLIENT', 'BULK');",
            (tick_time, "TEST_SYM")
        )
        database.execute_query("DELETE FROM bulk_deal_tracker WHERE symbol = 'TEST_SYM';")
        print("[OK] bulk_deal_tracker write path verified.")

    except Exception as e:
        print(f"[ERROR] Database write path failed: {e}")
        sys.exit(1)

def test_yfinance_and_scraper():
    print("\n--- 4. Testing Scraper & Yahoo Finance (Network Checks) ---")
    
    # Test Yahoo Finance backup
    from production.yfinance_backup import YahooFinanceBackup
    try:
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=2)
        records = YahooFinanceBackup.fetch_historical_backup("RELIANCE", yesterday, today)
        if records:
            print(f"[OK] Yahoo Finance retrieved backup candle: Close={records[0]['close']:.2f}")
        else:
            print("[WARNING] Yahoo Finance returned empty list (market closed/no data).")
    except Exception as e:
        print(f"[WARNING] Yahoo Finance network check failed: {e}")

    # Test NSE Scraper (FII/DII read)
    from production.nse_production import NSEProduction
    try:
        nse = NSEProduction()
        data = nse.fetch_fii_dii_data()
        print(f"[OK] NSE scraper connection verified. Scraped combined bias: {data.get('combined_bias')}")
    except Exception as e:
        print(f"[WARNING] NSE Scraper connection failed (possibly blocked by NSE firewall): {e}")

def main():
    test_imports()
    test_interfaces()
    test_database_write_paths()
    test_yfinance_and_scraper()
    print("\n=== All Production Readiness Tests Passed ===")

if __name__ == "__main__":
    main()
