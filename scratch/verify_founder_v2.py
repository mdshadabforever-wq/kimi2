import sys
import os
import urllib.request
import urllib.error
import json
import datetime
import psycopg2

sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import Config

def main():
    print("==================================================================")
    print("IIIS FOUNDER V2.0 SYSTEM VERIFICATION")
    print("==================================================================")

    # 1. Verify New Database Tables
    print("\n[STEP 1] Verifying schema and column types for new tables...")
    new_tables = [
        "trade_story_sections", "trade_postmortem", "trade_market_context",
        "trade_candle_statistics", "trade_decision_memory"
    ]
    
    try:
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cur = conn.cursor()
        for tbl in new_tables:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position;
            """, (tbl,))
            cols = cur.fetchall()
            print(f"Table '{tbl}': {len(cols)} columns found.")
            for col in cols:
                print(f"  - {col[0]}: {col[1]} (Nullable: {col[2]})")
                
        # Get row counts
        print("\n[STEP 2] Querying row counts for new tables...")
        for tbl in new_tables:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            count = cur.fetchone()[0]
            print(f"  - {tbl}: {count} rows")
            
        # Get latest trade ID to test trade-story
        cur.execute("SELECT trade_id FROM paper_trades ORDER BY trade_id DESC LIMIT 1;")
        res = cur.fetchone()
        latest_trade_id = res[0] if res else None
        print(f"Latest trade ID in database: {latest_trade_id}")
        
        conn.close()
    except Exception as e:
        print(f"Database verification error: {e}")
        return

    # 2. Test API Endpoints via HTTP requests to port 8080
    print("\n[STEP 3] Testing REST APIs on local server http://localhost:8080...")
    cookie_header = "admin_session=strong_password_here"
    
    # Endpoint 1: /api/founder/today
    url_today = "http://localhost:8080/api/founder/today"
    req_today = urllib.request.Request(url_today)
    req_today.add_header("Cookie", cookie_header)
    
    try:
        with urllib.request.urlopen(req_today) as response:
            data = json.loads(response.read().decode())
            print("\n[API RESPONSE] /api/founder/today:")
            print(f"  Status: 200 OK")
            print(f"  Date: {data.get('date')}")
            print(f"  Regime: {data.get('regime')} (Score: {data.get('regime_score')})")
            print(f"  GEIE Sentiment: {data.get('geie_sentiment')}")
            print(f"  Narrative: {data.get('narrative')[:150]}...")
            print(f"  Timeline Events Count: {len(data.get('timeline', []))}")
            print(f"  Trades Cards Count: {len(data.get('trades', []))}")
    except Exception as e:
        print(f"Error calling /api/founder/today: {e}")

    # Endpoint 2: /api/founder/day-replay
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    url_replay = f"http://localhost:8080/api/founder/day-replay?date={today_str}"
    req_replay = urllib.request.Request(url_replay)
    req_replay.add_header("Cookie", cookie_header)
    
    try:
        with urllib.request.urlopen(req_replay) as response:
            data = json.loads(response.read().decode())
            print(f"\n[API RESPONSE] /api/founder/day-replay?date={today_str}:")
            print(f"  Status: 200 OK")
            print(f"  Morning Regime: {data.get('morning', {}).get('regime_name')}")
            print(f"  Mid-Day Trades: {len(data.get('mid_day', {}).get('trades', []))}")
            print(f"  Mid-Day News: {len(data.get('mid_day', {}).get('news', []))}")
            print(f"  Afternoon Resolutions: {len(data.get('afternoon', []))}")
            eod = data.get('eod', {})
            print(f"  EOD Stats: Win Rate = {eod.get('win_rate')}%, Total R = {eod.get('total_r')}R")
            print(f"  EOD Summary Paragraph: {eod.get('summary_paragraph')[:150]}...")
    except Exception as e:
        print(f"Error calling /api/founder/day-replay: {e}")

    # Endpoint 3: /api/founder/trade-story/{trade_id}
    if latest_trade_id:
        url_story = f"http://localhost:8080/api/founder/trade-story/{latest_trade_id}"
        req_story = urllib.request.Request(url_story)
        req_story.add_header("Cookie", cookie_header)
        
        try:
            with urllib.request.urlopen(req_story) as response:
                data = json.loads(response.read().decode())
                print(f"\n[API RESPONSE] /api/founder/trade-story/{latest_trade_id}:")
                print(f"  Status: 200 OK")
                print(f"  Trade: ID {data.get('trade_id')} | {data.get('symbol')} | {data.get('direction')} | Status: {data.get('status')}")
                print(f"  Outcome: {data.get('outcome')} | R: {data.get('r_multiple')}R | Duration: {data.get('duration_mins')} mins")
                print(f"  Decision Composite Score: {data.get('decision', {}).get('composite')} | Reason: {data.get('decision', {}).get('reason')}")
                print(f"  Market Context Regime: {data.get('context', {}).get('regime')}")
                print(f"  Chronological Sections Count: {len(data.get('sections', []))}")
                for sec in data.get('sections', []):
                    print(f"    - [{sec.get('time')}] {sec.get('title')}")
                print(f"  AI Postmortem Lessons Learned: {data.get('postmortem', {}).get('lessons_learned')}")
        except Exception as e:
            print(f"Error calling /api/founder/trade-story/{latest_trade_id}: {e}")
    else:
        print("\nNo trade found in DB to test trade story API.")

if __name__ == "__main__":
    main()
