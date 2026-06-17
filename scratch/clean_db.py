import sys
import os

# Add parent directory to path so database.py can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database

def clean_database():
    print("Connecting to database and truncating tables...")
    query = """
    TRUNCATE market_data, trend_states, smc_structures, order_block_memory, 
             options_data, regime_history, fii_dii_tracker, active_alerts, 
             signals, risk_state CASCADE;
    """
    try:
        database.execute_query(query)
        print("Database tables truncated successfully.")
    except Exception as e:
        print(f"Error during truncate: {e}")

if __name__ == "__main__":
    clean_database()
