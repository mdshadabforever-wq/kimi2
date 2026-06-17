import pytest
import psycopg2
import database
from config import Config

# Set testing flag
import os
os.environ["IIIS_TESTING"] = "True"

def test_database_connection():
    """Verify that we can establish a connection and ping the database."""
    conn = database.get_connection()
    assert conn is not None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            res = cur.fetchone()
            assert res[0] == 1
    finally:
        database.release_connection(conn)

def test_database_schema_initialization():
    """Verify that all 16 tables are created and present in the database."""
    database.init_db("schema.sql")
    
    # List of all 16 tables required by spec
    expected_tables = [
        "market_data", "signals", "active_alerts", "risk_state",
        "regime_history", "audit_log", "system_health", "geie_events",
        "geie_master_map", "options_data", "earnings_calendar", "event_calendar",
        "fii_dii_tracker", "bulk_deal_tracker", "options_intelligence", "order_block_memory"
    ]
    
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            for table in expected_tables:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    );
                """, (table,))
                exists = cur.fetchone()[0]
                assert exists, f"Table '{table}' is missing from the database!"
    finally:
        database.release_connection(conn)

def test_audit_log_protection_trigger():
    """Verify database-level protection preventing UPDATE and DELETE on audit_log."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            # 1. Insert a log row
            cur.execute("""
                INSERT INTO audit_log (component, action, result, reason)
                VALUES ('Test', 'TEST_INSERT', 'SUCCESS', 'Verification run')
                RETURNING id;
            """)
            log_id = cur.fetchone()[0]
            conn.commit()
            
            # 2. Try to UPDATE and verify exception is thrown
            with pytest.raises(psycopg2.Error) as excinfo:
                cur.execute("UPDATE audit_log SET result = 'FAILED' WHERE id = %s;", (log_id,))
                conn.commit()
            assert "Updates and deletes are strictly prohibited" in str(excinfo.value)
            
            # 3. Try to DELETE and verify exception is thrown
            with pytest.raises(psycopg2.Error) as excinfo:
                cur.execute("DELETE FROM audit_log WHERE id = %s;", (log_id,))
                conn.commit()
            assert "Updates and deletes are strictly prohibited" in str(excinfo.value)
            
    finally:
        database.release_connection(conn)

def test_db_outage_simulation():
    """Verify database outage simulation logic."""
    database.set_db_outage(True)
    with pytest.raises(psycopg2.OperationalError) as excinfo:
        database.get_connection()
    assert "Simulated database outage" in str(excinfo.value)
    
    # Restore
    database.set_db_outage(False)
    conn = database.get_connection()
    assert conn is not None
    database.release_connection(conn)
