import sys
import os
import codecs
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import psycopg2
import asyncio
import datetime
from config import Config
from interfaces.base import ServiceRegistry
import database
import redis_client
import health_monitor
import ghost_mode
from bootstrap import register_services

async def collect():
    register_services()
    database.set_db_outage(False)
    redis_client.set_redis_outage(False)
    
    # Reset Ghost Mode if active
    if ghost_mode.is_ghost_mode_active():
        ghost_mode.resume_system()
        
    upstox = ServiceRegistry.get("upstox")
    upstox.websocket_connected = True
    upstox.simulate_websocket_disconnect = False
    upstox.simulate_data_gap = False
    upstox.last_tick_time = datetime.datetime.now()
        
    conn = database.get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            # 1. Check Extensions
            print("1. DATABASE EXTENSIONS")
            print("-" * 30)
            cur.execute("SELECT extname FROM pg_extension;")
            exts = [row[0] for row in cur.fetchall()]
            print(f"Enabled Extensions: {exts}")
            print(f"TimescaleDB enabled: {'timescaledb' in exts}")
            
            # 2. Check Hypertables
            print("\n2. HYPERTABLE VERIFICATION")
            print("-" * 30)
            try:
                cur.execute("SELECT hypertable_schema, hypertable_name FROM timescaledb_information.hypertables;")
                hypertables = cur.fetchall()
                print(f"Hypertables found: {hypertables}")
            except Exception as e:
                print(f"Error checking hypertables: {e}")
                
            # 3. Check Audit Log Protection Triggers
            print("\n3. AUDIT LOG PROTECTION VERIFICATION")
            print("-" * 30)
            # Insert a dummy row
            cur.execute("""
                INSERT INTO audit_log (component, action, result, reason)
                VALUES ('SafetyUnit', 'TEST_PROTECTION', 'SUCCESS', 'Probing triggers')
                RETURNING id;
            """)
            row_id = cur.fetchone()[0]
            print(f"Inserted dummy audit log row ID: {row_id}")
            
            # Try UPDATE
            try:
                cur.execute("UPDATE audit_log SET result = 'MALICIOUS' WHERE id = %s;", (row_id,))
                print("UPDATE succeeded (TRIGGER FAILURE!)")
            except Exception as e:
                print(f"UPDATE Attempt Result: BLOCKED\nTrigger Error Message: {str(e).strip()}")
                
            # Try DELETE
            try:
                cur.execute("DELETE FROM audit_log WHERE id = %s;", (row_id,))
                print("DELETE succeeded (TRIGGER FAILURE!)")
            except Exception as e:
                print(f"DELETE Attempt Result: BLOCKED\nTrigger Error Message: {str(e).strip()}")
                
            # 4. Check all 16 tables
            print("\n4. TABLES LIST IN DATABASE")
            print("-" * 30)
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            print(f"Total tables: {len(tables)}")
            for i, tbl in enumerate(tables, 1):
                print(f" {i:02d}. {tbl}")

        # 5. Run Health Check status check
        print("\n5. HEALTH MONITOR COMPONENT STATUS")
        print("-" * 30)
        components = ["upstox", "perplexity", "gemini", "claude", "telegram", "postgres", "redis"]
        for comp in components:
            status, duration, err = await health_monitor.check_component(comp)
            print(f"  - {comp.upper():<12} : Status={status:<4} (Latency: {duration}ms) {f'Error: {err}' if err else ''}")

        # 6. Simulate failure & check Ghost Mode
        print("\n6. GHOST MODE SIMULATION")
        print("-" * 30)
        # Clear sent warnings
        telegram = ServiceRegistry.get("telegram")
        telegram.clear()
        
        # Trigger failure: 4 consecutive health failures on Redis
        redis_client.set_redis_outage(True)
        print("Simulating Redis Outage (failures_tracker counts)...")
        for i in range(4):
            await health_monitor.run_single_health_cycle()
            
        print(f"Ghost Mode state active: {ghost_mode.is_ghost_mode_active()}")
        
        # Check audit log entry
        cur = conn.cursor()
        cur.execute("SELECT id, component, action, result, reason FROM audit_log ORDER BY id DESC LIMIT 1;")
        audit_row = cur.fetchone()
        print(f"Latest Audit Log Row: ID={audit_row[0]}, Component={audit_row[1]}, Action={audit_row[2]}, Result={audit_row[3]}, Reason={audit_row[4]}")
        
        # Check telegram warning message
        print(f"Telegram warnings count: {len(telegram.sent_messages)}")
        if telegram.sent_messages:
            # Safe print encoding
            print(f"Telegram message content:\n---\n{telegram.sent_messages[0][1]}\n---")
            
        # Test manual resume
        print("Testing manual resume...")
        redis_client.set_redis_outage(False)
        res = ghost_mode.resume_system()
        print(f"Resume result: {res}")
        print(f"Ghost Mode state after resume: {ghost_mode.is_ghost_mode_active()}")
        if len(telegram.sent_messages) > 1:
            print(f"Telegram resume content: {telegram.sent_messages[1][1]}")

    finally:
        database.release_connection(conn)

if __name__ == "__main__":
    asyncio.run(collect())
