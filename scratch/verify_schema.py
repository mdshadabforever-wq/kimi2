import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import psycopg2
from config import Config

tables = [
    "market_data", "signals", "active_alerts", "risk_state",
    "regime_history", "audit_log", "system_health", "geie_events",
    "geie_master_map", "options_data", "earnings_calendar", "event_calendar",
    "fii_dii_tracker", "bulk_deal_tracker", "options_intelligence", "order_block_memory"
]

try:
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    cursor = conn.cursor()
    print("IIIS SCHEMA VERIFICATION REPORT\n" + "="*40)
    for table in tables:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            ORDER BY ordinal_position;
        """, (table,))
        cols = cursor.fetchall()
        print(f"\nTable: {table} ({len(cols)} columns)")
        print("-"*30)
        for col in cols:
            print(f"  - {col[0]}: {col[1]} (Nullable: {col[2]})")
    conn.close()
except Exception as e:
    print(f"Error during schema verification: {e}")
