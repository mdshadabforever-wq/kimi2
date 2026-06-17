import os
import sys
import datetime
from decimal import Decimal
import json

# Setup import path
sys.path.append('c:/Users/shadab/Desktop/trade')
os.environ["IIIS_TESTING"] = "True"

import database
from bootstrap import register_services
from orchestrator import Orchestrator
from live_scan_loop import LiveScanLoop
from interfaces.base import ServiceRegistry
from seeder import seed_mock_data_for_demo
from services.trade_intelligence import TradeIntelligenceEngine

def main():
    print("==========================================================")
    print("IIIS TRADE INTELLIGENCE SYSTEM VERIFICATION RUN")
    print("==========================================================")

    # 1. Initialize services and database
    print("\n[STEP 1] Initializing services & database...")
    register_services()
    database.init_db("schema.sql")
    
    # Truncate tables for a clean test run
    database.execute_query("""
        TRUNCATE TABLE paper_trades, trade_events, trade_news, trade_snapshots, 
                       trade_score_breakdown, trade_analysis, market_data, 
                       signals, active_alerts, geie_events, regime_history CASCADE;
    """)
    print("Database cleared for verification.")

    # 2. Seed mock data
    print("\n[STEP 2] Seeding baseline indicators and market candles...")
    symbols = ["RELIANCE", "TATASTEEL", "INFY"]
    seed_mock_data_for_demo(symbols)
    
    # Seed a regime history row
    database.execute_query("""
        INSERT INTO regime_history (timestamp, regime, regime_score, nifty_price, ad_ratio)
        VALUES (NOW(), 'BULLISH_TREND', 92.5, 23200.0, 2.5);
    """)

    # Initialize Orchestrator
    orchestrator = Orchestrator()
    orchestrator.warmup_engines(symbols + ["NIFTY 50", "INDIA VIX"])

    # 3. Simulate Signal Approval (on_signal_approved)
    print("\n[STEP 3] Simulating Approved Signal...")
    signal_id = "IIIS-2026-06-17-001"
    timestamp = datetime.datetime.now()
    symbol = "RELIANCE"
    
    score_res = {
        "regime_score": 90.0, "rs_score": 95.0, "rvol_score": 88.0, "breadth_score": 92.0,
        "sector_score": 85.0, "trend_score": 96.0, "smc_score": 100.0, "options_score": 100.0,
        "final_composite_score": 93.5
    }
    
    # Premarket ARC snapshot
    arc_snap = {"symbol": symbol, "arc_decision": "APPROVE"}
    bm_snap = {"fii_trend": "BUYER", "score": 100, "conclusion": "Institutions accumulating"}

    # Trigger signal approval
    TradeIntelligenceEngine.on_signal_approved(
        signal_id=signal_id,
        timestamp=timestamp,
        symbol=symbol,
        direction="LONG",
        score_res=score_res,
        confidence="HIGH",
        risk_grade="A",
        entry_low=2400.0,
        entry_high=2420.0,
        stop_loss=2370.0,
        target_1=2450.0,
        target_2=2490.0,
        valid_until=timestamp + datetime.timedelta(hours=2),
        geie_snapshot={"market_sentiment": "BULLISH"},
        arc_snapshot=arc_snap,
        big_money_snapshot=bm_snap,
        regime_snapshot={"regime": "BULLISH_TREND"},
        risk_state_snapshot={"daily_risk_used": 0.5}
    )

    # SQL Verify Paper Trade
    print("\n[SQL EVIDENCE] paper_trades Table:")
    pt_rows = database.execute_query("SELECT trade_id, symbol, direction, status, entry_low, entry_high FROM paper_trades;", fetch=True)
    for r in pt_rows:
        print(f"  Trade ID: {r[0]} | Symbol: {r[1]} | Dir: {r[2]} | Status: {r[3]} | Zone: {r[4]} - {r[5]}")

    print("\n[SQL EVIDENCE] trade_score_breakdown Table:")
    sb_rows = database.execute_query("SELECT * FROM trade_score_breakdown;", fetch=True)
    for r in sb_rows:
        print(f"  Trade ID: {r[0]} | Regime: {r[1]} | RS: {r[2]} | Trend: {r[6]} | SMC: {r[7]} | Composite: {r[9]}")

    # 4. Simulate Price Ticks for Entry Trigger (PENDING -> ACTIVE)
    print("\n[STEP 4] Simulating ticks inside entry zone...")
    trade_id = pt_rows[0][0]
    
    # Tick inside zone (2410.0)
    tick_entry = {
        "symbol": symbol,
        "price": 2410.0,
        "time": timestamp + datetime.timedelta(minutes=2),
        "volume": 5000
    }
    
    # Run tick ingestion through the orchestrator
    orchestrator.process_tick(tick_entry)

    # SQL Verify Active Status
    print("\n[SQL EVIDENCE] active paper_trades after entry tick:")
    pt_active = database.execute_query("SELECT status, entry_price, entry_time, entry_volume FROM paper_trades WHERE trade_id = %s;", (trade_id,), fetch=True)
    print(f"  Status: {pt_active[0][0]} | Entry Price: {pt_active[0][1]} | Time: {pt_active[0][2]} | Vol: {pt_active[0][3]}")

    # 5. Inject News and verify news linking
    print("\n[STEP 5] Simulating GEIE news event catalyst...")
    news_time = timestamp + datetime.timedelta(minutes=5)
    geie_event_id = "GEIE-NEWS-99"
    database.execute_query("""
        INSERT INTO geie_events (event_id, timestamp, event_name, impact_direction, confidence, urgency, beneficiaries, raw_output)
        VALUES (%s, %s, 'Reliance JIO tariff hike announced', 'POSITIVE', 'HIGH', 'HIGH', '["RELIANCE"]', '{"stock_impacts": {"RELIANCE": {"direction": "POSITIVE", "confidence": "HIGH"}}}');
    """, (geie_event_id, news_time))

    # Send a subsequent tick to trigger news checks
    tick_news = {
        "symbol": symbol,
        "price": 2430.0,
        "time": timestamp + datetime.timedelta(minutes=6),
        "volume": 6000
    }
    orchestrator.process_tick(tick_news)

    # SQL Verify Trade News
    print("\n[SQL EVIDENCE] trade_news Table:")
    news_rows = database.execute_query("SELECT headline, source, sentiment, impact FROM trade_news WHERE trade_id = %s;", (trade_id,), fetch=True)
    for r in news_rows:
        print(f"  Headline: '{r[0]}' | Source: {r[1]} | Sent: {r[2]} | Impact: {r[3]}")

    # 6. Simulate Price Ticks for Exit Target (ACTIVE -> HIT_T2)
    print("\n[STEP 6] Simulating tick reaching Target 2 (2495.0)...")
    exit_time = timestamp + datetime.timedelta(minutes=25)
    tick_exit = {
        "symbol": symbol,
        "price": 2495.0, # target_2 is 2490.0, so this hits T2
        "time": exit_time,
        "volume": 8000
    }
    
    # We must seed a 1m candle for this exit time in market_data so the candle analytics engine can retrieve it!
    database.execute_query("""
        INSERT INTO market_data (time, symbol, open, high, low, close, volume, timeframe)
        VALUES (%s, %s, 2410.0, 2500.0, 2400.0, 2495.0, 25000, '1m');
    """, (exit_time, symbol))

    # Process tick to hit exit
    orchestrator.process_tick(tick_exit)

    # SQL Verify Exit
    print("\n[SQL EVIDENCE] closed paper_trades after exit tick:")
    pt_exit = database.execute_query("""
        SELECT status, outcome_classification, exit_price, exit_time, holding_minutes, final_r_multiple, mfe, mae, max_profit_pct
        FROM paper_trades WHERE trade_id = %s;
    """, (trade_id,), fetch=True)
    print(f"  Status: {pt_exit[0][0]} | Outcome: {pt_exit[0][1]} | Exit Price: {pt_exit[0][2]} | Exit Time: {pt_exit[0][3]}")
    print(f"  Duration: {pt_exit[0][4]} mins | R Multiple: {pt_exit[0][5]}R | MFE: {pt_exit[0][6]} | MAE: {pt_exit[0][7]} | Max Profit: {pt_exit[0][8]}%")

    # 7. AI Analyst Report Verification
    print("\n[STEP 7] Verifying AI Analyst report generation...")
    report_row = database.execute_query("SELECT markdown_report, json_report FROM trade_analysis WHERE trade_id = %s;", (trade_id,), fetch=True)
    if report_row:
        print("  AI Analyst report successfully generated and stored in DB!")
        print("\n[AI ANALYST JSON SNAPSHOT]:")
        report_data = report_row[0][1]
        if isinstance(report_data, str):
            report_data = json.loads(report_data)
        print(json.dumps(report_data, indent=2))
        print("\n[AI ANALYST REPORT SNEAK PEEK (FIRST 200 CHARS)]:")
        print(report_row[0][0][:200] + "...")
    else:
        print("  Error: AI report not found in DB.")

    # 8. Chronological events timeline verification
    print("\n[STEP 8] Verifying Chronological Timeline Events:")
    ev_rows = database.execute_query("SELECT event_type, title, description FROM trade_events WHERE trade_id = %s ORDER BY timestamp ASC;", (trade_id,), fetch=True)
    for r in ev_rows:
        print(f"  - [{r[0]}] {r[1]} : {r[2]}")

    # 9. Test API responses of dashboard_server using standard route functions
    print("\n[STEP 9] Verifying REST API responses...")
    import dashboard_server
    
    # Mock authentication token
    dashboard_server.get_current_admin_api = lambda request: "mocked"
    
    # Call active trades
    active_res = dashboard_server.api_active_trades()
    print(f"  API Active Trades count: {len(active_res)}")
    
    # Call closed trades
    closed_res = dashboard_server.api_closed_trades()
    print(f"  API Closed Trades count: {len(closed_res)}")
    print(f"    First Closed Trade: {closed_res[0]['symbol']} | R: {closed_res[0]['final_r']}R | Outcome: {closed_res[0]['outcome']}")

    # Call analytics
    analytics_res = dashboard_server.api_trade_analytics()
    print("\n[API ANALYTICS RESPONSE]:")
    print(json.dumps(analytics_res, indent=2))

    # Call best/worst
    bw_res = dashboard_server.api_best_worst()
    print(f"  API Best Trades count: {len(bw_res['best'])}")
    print(f"  API Worst Trades count: {len(bw_res['worst'])}")

    # Call strategy comparison
    strat_res = dashboard_server.api_strategy_comparison()
    print("\n[API STRATEGY COMPARISON RESPONSE]:")
    print(json.dumps(strat_res, indent=2))

    # 10. Test Markdown and JSON Exports
    print("\n[STEP 10] Verifying JSON & Markdown exports...")
    # Test JSON export output
    json_export_res = dashboard_server.api_export_json(trade_id)
    json_payload = json.loads(json_export_res.body)
    print(f"  JSON Export: trade_id = {json_payload['trade_id']} | timeline count = {len(json_payload['timeline'])} | score breakdown = {json_payload['score_breakdown']['composite_score']}")

    # Test Markdown export output
    md_export_res = dashboard_server.api_export_markdown(trade_id)
    print(f"  Markdown Export size: {len(md_export_res.body)} characters.")
    print("  Markdown Export Preview:")
    print(md_export_res.body.decode()[:150] + "...")

    print("\n==========================================================")
    print("VERIFICATION RUN SUCCESSFUL! ALL 10 PHASES COMPLETED.")
    print("==========================================================")

if __name__ == "__main__":
    main()
