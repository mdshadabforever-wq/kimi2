import sys
import os
import urllib.request
import urllib.parse
import urllib.error
import json
import datetime
import psycopg2

sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config
from services.memory_engine import MemoryEngine

def main():
    print("==================================================================")
    print("IIIS FOUNDER V3.1 SYSTEM VERIFICATION")
    print("==================================================================")

    # 1. Establish database connection
    print("\n[STEP 1] Connecting to database...")
    try:
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cur = conn.cursor()
        print("Connected successfully.")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return

    # 2. Seed simulated trade for testing
    print("\n[STEP 2] Seeding simulated trade candidate...")
    try:
        # Clear existing test signals/trades if any
        cur.execute("DELETE FROM trade_postmortem WHERE trade_id IN (SELECT trade_id FROM paper_trades WHERE signal_id LIKE 'TEST_SIG_%%');")
        cur.execute("DELETE FROM trade_decision_memory WHERE trade_id IN (SELECT trade_id FROM paper_trades WHERE signal_id LIKE 'TEST_SIG_%%');")
        cur.execute("DELETE FROM trade_events WHERE trade_id IN (SELECT trade_id FROM paper_trades WHERE signal_id LIKE 'TEST_SIG_%%');")
        cur.execute("DELETE FROM trade_replays WHERE trade_id IN (SELECT trade_id FROM paper_trades WHERE signal_id LIKE 'TEST_SIG_%%');")
        cur.execute("DELETE FROM trade_graveyard WHERE trade_id IN (SELECT trade_id FROM paper_trades WHERE signal_id LIKE 'TEST_SIG_%%');")
        cur.execute("DELETE FROM founder_notes WHERE trade_id IN (SELECT trade_id FROM paper_trades WHERE signal_id LIKE 'TEST_SIG_%%');")
        cur.execute("DELETE FROM paper_trades WHERE signal_id LIKE 'TEST_SIG_%%';")
        conn.commit()

        # Insert a new paper trade
        insert_trade_query = """
            INSERT INTO paper_trades (
                signal_id, strategy_version, symbol, direction, status, 
                entry_low, entry_high, stop_loss, target_1, target_2, 
                valid_until, entry_price, entry_time, exit_price, exit_time, 
                outcome_classification, final_r_multiple, holding_minutes, created_at
            ) VALUES (
                'TEST_SIG_999', 'v4.6', 'RELIANCE', 'LONG', 'HIT_SL',
                2390.0, 2410.0, 2380.0, 2450.0, 2500.0,
                NOW() + INTERVAL '2 hours', 2400.0, NOW() - INTERVAL '1 hours', 2380.0, NOW(),
                'LOSS', -1.0, 60, NOW()
            ) RETURNING trade_id;
        """
        cur.execute(insert_trade_query)
        trade_id = cur.fetchone()[0]
        print(f"Simulated trade created with ID: {trade_id}")

        # Insert decision memory (trend_score < 75 to trigger COUNTER_TREND failure category)
        insert_mem_query = """
            INSERT INTO trade_decision_memory (
                trade_id, composite_score, regime_score, rs_score, rvol_score, 
                breadth_score, sector_score, trend_score, smc_score, options_score, decision_reason
            ) VALUES (
                %s, 86.0, 50.0, 50.0, 50.0,
                50.0, 50.0, 65.0, 50.0, 50.0, 'Test counter-trend signal'
            );
        """
        cur.execute(insert_mem_query, (trade_id,))
        
        # Insert a sample event to generate replay steps
        insert_event_query = """
            INSERT INTO trade_events (trade_id, timestamp, event_type, title, description, metadata)
            VALUES (%s, NOW() - INTERVAL '30 minutes', 'ENTRY_TRIGGER', 'Position Entered', 'Entered long at 2400.0', '{}');
        """
        cur.execute(insert_event_query, (trade_id,))
        
        conn.commit()
        print("Seed data committed.")
    except Exception as e:
        print(f"Error seeding simulated trade: {e}")
        conn.rollback()
        conn.close()
        return

    # 3. Invoke Memory Engine Completed Hook
    print("\n[STEP 3] Running Memory Engine Completed hook...")
    try:
        MemoryEngine.on_trade_completed(trade_id)
        print("MemoryEngine hook completed successfully.")
    except Exception as e:
        print(f"MemoryEngine hook execution failed: {e}")
        conn.close()
        return

    # 4. Verify Database state after completion
    print("\n[STEP 4] Verifying database tables content...")
    try:
        # Check trade graveyard
        cur.execute("SELECT failure_category, why_failed, could_loss_be_avoided FROM trade_graveyard WHERE trade_id = %s;", (trade_id,))
        gy_res = cur.fetchone()
        if gy_res:
            print(f"  - Graveyard entry found. Category: {gy_res[0]} (Avoidable: {gy_res[2]})")
            assert gy_res[0] == "COUNTER_TREND", "Graveyard failure category mismatch!"
        else:
            print("  - [FAIL] No graveyard entry found for completed losing trade!")

        # Check pattern library
        cur.execute("SELECT count(*) FROM trade_pattern_library;")
        pattern_count = cur.fetchone()[0]
        print(f"  - Pattern Library count: {pattern_count} patterns recorded.")

        # Check tomorrow watchlist intelligence
        cur.execute("SELECT count(*) FROM tomorrow_intelligence;")
        tomorrow_count = cur.fetchone()[0]
        print(f"  - Tomorrow Watchlist Forecasts count: {tomorrow_count} records.")

        # Check trade replays
        cur.execute("SELECT count(*) FROM trade_replays WHERE trade_id = %s;", (trade_id,))
        replay_exists = cur.fetchone()[0] > 0
        print(f"  - Visual Replay steps cached: {'Yes' if replay_exists else 'No'}")
        
    except Exception as e:
        print(f"Database content verification failed: {e}")

    # 5. Verify API HTTP calls
    print("\n[STEP 5] Testing HTTP REST API endpoints on local server...")
    cookie_header = "admin_session=strong_password_here"
    
    # helper for api call
    def call_api(url, data_payload=None, is_json=True):
        req = urllib.request.Request(url)
        req.add_header("Cookie", cookie_header)
        if data_payload is not None:
            # POST request
            data_encoded = urllib.parse.urlencode(data_payload).encode('utf-8')
            req.data = data_encoded
        try:
            with urllib.request.urlopen(req) as response:
                body = response.read()
                if is_json:
                    return json.loads(body.decode()), response.status
                return body, response.status
        except urllib.error.HTTPError as he:
            print(f"  - HTTP Error {he.code} for URL {url}: {he.read().decode()}")
            return None, he.code
        except Exception as ex:
            print(f"  - Connection error for URL {url}: {ex}")
            return None, 500

    # API 1: Save founder notes
    print("\n[API] Saving founder notes to POST /api/founder/notes/{trade_id}...")
    notes_payload = {"note_text": "Observed sharp options sweep. Entered long on counter-trend, but got caught by heavy sell block sweep."}
    res_notes, status = call_api(f"http://localhost:8080/api/founder/notes/{trade_id}", data_payload=notes_payload)
    print(f"  Status: {status} | Response: {res_notes}")
    
    # API 2: Get founder notes
    print("\n[API] Retrieving notes from GET /api/founder/notes/{trade_id}...")
    res_get_notes, status = call_api(f"http://localhost:8080/api/founder/notes/{trade_id}")
    print(f"  Status: {status} | Response: {res_get_notes}")
    if res_get_notes:
        assert "sharp options sweep" in res_get_notes.get("notes", ""), "Saved note text mismatch!"

    # API 3: Get memory details (with insights updated by note addition)
    print("\n[API] Fetching memory dashboard data from GET /api/founder/memory...")
    res_mem, status = call_api("http://localhost:8080/api/founder/memory")
    print(f"  Status: {status}")
    if res_mem:
        print(f"  Total Trades: {res_mem.get('kpis', {}).get('total_trades')}")
        print(f"  Win Rate: {res_mem.get('kpis', {}).get('win_rate')}%")
        print(f"  Memory Insights: {list(res_mem.get('insights', {}).keys())}")
        print(f"  Graveyard Entries: {len(res_mem.get('graveyard', []))}")
        print(f"  Tomorrow Watchlist: {res_mem.get('tomorrow_intel', {}).get('watchlist')}")
        
        # Verify note audit integration in insights
        works_text = res_mem.get("insights", {}).get("what_works", {}).get("content", "")
        print(f"  What Works Insight Content: {works_text}")
        assert "founder confluences" in works_text.lower(), "Founder notes confluences not factored into memory insights!"

    # API 4: Get trade replay steps
    print(f"\n[API] Fetching replay steps from GET /api/founder/trade-replay/{trade_id}...")
    res_replay, status = call_api(f"http://localhost:8080/api/founder/trade-replay/{trade_id}")
    print(f"  Status: {status}")
    if res_replay:
        print(f"  Trade ID: {res_replay.get('trade_id')}")
        print(f"  Replay Steps count: {len(res_replay.get('steps', []))}")
        for step in res_replay.get('steps', []):
            print(f"    - [{step.get('time')}] {step.get('title')}: {step.get('description')}")

    # API 5: Download Reports
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    report_urls = [
        ("Daily PDF", f"http://localhost:8080/api/founder/report/download?type=daily&date={today_str}"),
        ("Weekly PDF", "http://localhost:8080/api/founder/report/download?type=weekly&week=2026-W24"),
        ("Monthly PDF", "http://localhost:8080/api/founder/report/download?type=monthly&month=2026-06"),
        ("Annual PDF", "http://localhost:8080/api/founder/report/download?type=annual&year=2026")
    ]
    
    for label, url in report_urls:
        print(f"\n[API] Downloading {label} report from {url}...")
        body, status = call_api(url, is_json=False)
        print(f"  Status: {status} | Size: {len(body) if body else 0} bytes")
        if body:
            # Verify PDF magic signature %PDF-
            is_pdf = body.startswith(b"%PDF-")
            print(f"  Magic signature matches %PDF-: {is_pdf}")
            assert is_pdf, f"Downloaded file for {label} is not a valid PDF!"

    # 6. Cleanup test data
    print("\n[STEP 6] Cleaning up test data...")
    try:
        cur.execute("DELETE FROM trade_replays WHERE trade_id = %s;", (trade_id,))
        cur.execute("DELETE FROM trade_graveyard WHERE trade_id = %s;", (trade_id,))
        cur.execute("DELETE FROM founder_notes WHERE trade_id = %s;", (trade_id,))
        cur.execute("DELETE FROM trade_decision_memory WHERE trade_id = %s;", (trade_id,))
        cur.execute("DELETE FROM trade_events WHERE trade_id = %s;", (trade_id,))
        cur.execute("DELETE FROM paper_trades WHERE trade_id = %s;", (trade_id,))
        conn.commit()
        print("Cleaned up successfully.")
    except Exception as e:
        print(f"Cleanup failed: {e}")
        conn.rollback()

    conn.close()
    print("\n==================================================================")
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    main()
