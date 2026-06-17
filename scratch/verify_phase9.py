import datetime
import json
import time
from decimal import Decimal
from interfaces.base import ServiceRegistry
import redis_client
import database
from bootstrap import register_services
from geie_engine.geie_processor import GEIEProcessor
from geie_engine.master_map_loader import GEIEMasterMapLoader
from geie_engine.persistence import GEIEPersistence
from geie_engine.scheduler import GEIEScheduler

def setup_clean_db():
    database.init_db("schema.sql")
    database.execute_query("DELETE FROM geie_events;")
    database.execute_query("DELETE FROM geie_master_map;")
    database.execute_query("DELETE FROM latency_metrics;")

def run_geie_verification():
    print("=== Phase 9 GEIE Engine Verification ===")
    setup_clean_db()
    register_services()
    
    t = datetime.datetime(2026, 6, 15, 8, 5, 0)
    processor = GEIEProcessor()
    
    # Clean Redis
    redis_client.delete_val(processor.redis_key)
    
    # Seed Master Map triggers
    GEIEMasterMapLoader.seed_master_map()
    
    # --- A. GEIE JSON Output Example ---
    print("\nA. GEIE JSON Output Example")
    print("---------------------------")
    payload = processor.run_premarket(t, force_refresh=True)
    # Print the first few keys and stock impacts for readability
    subset_payload = {
        "event_id": payload["event_id"],
        "timestamp": payload["timestamp"],
        "market_sentiment": payload["market_sentiment"],
        "fii_5day_trend": payload["fii_5day_trend"],
        "institutional_bias": payload["institutional_bias"],
        "key_support_from_options": payload["key_support_from_options"],
        "key_resistance_from_options": payload["key_resistance_from_options"],
        "top_beneficiaries": payload["top_beneficiaries"],
        "top_losers": payload["top_losers"],
        "geie_status": payload["geie_status"]
    }
    print(json.dumps(subset_payload, indent=2))
    
    print("\nTATASTEEL Impact Details:")
    print(json.dumps(payload["stock_impacts"]["TATASTEEL"], indent=2))
    
    # --- B. Market Sentiment Calculation ---
    print("\nB. Market Sentiment Calculation Examples")
    print("---------------------------------------")
    print(f"  Inputs (1.0, 1.0, 1.0)   -> Sentiment: {GEIEProcessor.calculate_market_sentiment(1.0, 1.0, 1.0)} (Expected: RISK_ON)")
    print(f"  Inputs (-1.0, -1.0, -1.0) -> Sentiment: {GEIEProcessor.calculate_market_sentiment(-1.0, -1.0, -1.0)} (Expected: RISK_OFF)")
    print(f"  Inputs (0.0, 0.0, 0.0)   -> Sentiment: {GEIEProcessor.calculate_market_sentiment(0.0, 0.0, 0.0)} (Expected: NEUTRAL)")
    
    # --- C & D. Stock Impact Examples ---
    print("\nC & D. Stock Impact Direction Examples")
    print("-------------------------------------")
    print(f"  TATASTEEL Direction: {payload['stock_impacts']['TATASTEEL']['direction']} (Reasons: {payload['stock_impacts']['TATASTEEL']['reasons']})")
    print(f"  INFY Direction     : {payload['stock_impacts']['INFY']['direction']} (Reasons: {payload['stock_impacts']['INFY']['reasons']})")
    
    # --- E. Correlation Propagation Example ---
    print("\nE. Correlation Propagation Example")
    print("----------------------------------")
    # Propagate trigger: steel_price_up
    corr_steel = processor.propagate_triggers(["steel_price_up"])
    print("  Trigger 'steel_price_up':")
    print(f"    TATASTEEL Impact: Direction={corr_steel['TATASTEEL']['direction']}, Reasons={corr_steel['TATASTEEL']['reasons']}")
    print(f"    JSWSTEEL Impact : Direction={corr_steel['JSWSTEEL']['direction']}, Reasons={corr_steel['JSWSTEEL']['reasons']}")
    print(f"    HDFCBANK Impact : Direction={corr_steel['HDFCBANK']['direction']}, Reasons={corr_steel['HDFCBANK']['reasons']}")
    
    # Propagate trigger: rate_hike (negative for banking)
    corr_banking = processor.propagate_triggers(["rate_hike"])
    print("\n  Trigger 'rate_hike':")
    print(f"    HDFCBANK Impact : Direction={corr_banking['HDFCBANK']['direction']}, Reasons={corr_banking['HDFCBANK']['reasons']}")
    print(f"    TATASTEEL Impact: Direction={corr_banking['TATASTEEL']['direction']}, Reasons={corr_banking['TATASTEEL']['reasons']}")

    # --- F. Redis Cache Hit/Miss Verification ---
    print("\nF. Redis Cache Hit/Miss Verification")
    print("------------------------------------")
    # Miss
    redis_client.delete_val(processor.redis_key)
    start_miss = time.perf_counter()
    p_miss = processor.run_premarket(t, force_refresh=False)
    elapsed_miss_ms = (time.perf_counter() - start_miss) * 1000
    print(f"  Cache Miss Run: Time={elapsed_miss_ms:.2f}ms, Status={p_miss['geie_status']}")
    
    # Hit
    start_hit = time.perf_counter()
    p_hit = processor.run_premarket(t, force_refresh=False)
    elapsed_hit_ms = (time.perf_counter() - start_hit) * 1000
    print(f"  Cache Hit Run : Time={elapsed_hit_ms:.2f}ms, Status={p_hit['geie_status']}")

    # --- G & H. Gemini/Perplexity Failure Fallback Verification ---
    print("\nG & H. Gemini/Perplexity Failure Fallback")
    print("----------------------------------------")
    # Seed active cache in Redis
    seeded_payload = {
        "event_id": "GEIE-2026-06-15-001",
        "timestamp": t.strftime('%Y-%m-%d %H:%M:%S IST'),
        "market_sentiment": "RISK_ON",
        "stock_impacts": {
            "TATASTEEL": {"direction": "POSITIVE", "magnitude": 2, "reasons": ["China Cuts"], "confidence": "HIGH", "urgency": "INTRADAY"}
        },
        "fii_5day_trend": "BUYING",
        "institutional_bias": "BULLISH",
        "key_support_from_options": "23400",
        "key_resistance_from_options": "23700",
        "top_beneficiaries": ["TATASTEEL"],
        "top_losers": [],
        "geie_status": "ACTIVE"
    }
    redis_client.set_val(processor.redis_key, json.dumps(seeded_payload), ex=3600)
    
    # Force Gemini Fail
    gemini_mock = ServiceRegistry.get("gemini")
    gemini_mock.simulate_error = True
    
    p_gemini_fallback = processor.run_premarket(t + datetime.timedelta(minutes=5), force_refresh=True)
    print(f"  Gemini API Failure -> Cache Fallback: Status={p_gemini_fallback['geie_status']}, Sentiment={p_gemini_fallback['market_sentiment']} (Expected: ACTIVE / RISK_ON)")
    gemini_mock.simulate_error = False
    
    # Force Perplexity Fail
    perplexity_mock = ServiceRegistry.get("perplexity")
    perplexity_mock.simulate_error = True
    p_perplexity_fallback = processor.run_premarket(t + datetime.timedelta(minutes=10), force_refresh=True)
    print(f"  Perplexity API Failure -> Cache Fallback: Status={p_perplexity_fallback['geie_status']}, Sentiment={p_perplexity_fallback['market_sentiment']} (Expected: ACTIVE / RISK_ON)")
    perplexity_mock.simulate_error = False

    # --- I. Dual Failure Behavior Verification ---
    print("\nI. Dual Failure Behavior Verification (No Cache)")
    print("-----------------------------------------------")
    # Clean Redis to simulate expired/missing cache
    redis_client.delete_val(processor.redis_key)
    
    gemini_mock.simulate_error = True
    perplexity_mock.simulate_error = True
    
    p_dual_fail = processor.run_premarket(t, force_refresh=True)
    print(f"  Dual API Outage -> Fallback Payload: Status={p_dual_fail['geie_status']}, Sentiment={p_dual_fail['market_sentiment']} (Expected: UNAVAILABLE / NEUTRAL)")
    print(f"  TATASTEEL Direction (Outage)       : {p_dual_fail['stock_impacts']['TATASTEEL']['direction']} (Expected: NEUTRAL)")
    
    # --- J. Recovery after API Restoration ---
    print("\nJ. Recovery after API Restoration")
    print("---------------------------------")
    # Disable error simulation
    gemini_mock.simulate_error = False
    perplexity_mock.simulate_error = False
    
    p_restored = processor.run_premarket(t, force_refresh=True)
    print(f"  APIs Restored -> Daily Result: Status={p_restored['geie_status']}, Sentiment={p_restored['market_sentiment']} (Expected: ACTIVE / RISK_ON)")

    # --- K. Premarket Scheduler Execution ---
    print("\nK. Premarket Scheduler Execution")
    print("--------------------------------")
    GEIEScheduler.execute_premarket_job(t)

    # --- L. Multi-Symbol Processing Benchmark ---
    print("\nL. Multi-Symbol Processing Benchmark")
    print("------------------------------------")
    # Benchmark processing speed
    start_bench = time.perf_counter()
    # Runs analysis and handles mapping for all 50 symbols
    p_bench = processor.run_premarket(t, force_refresh=True)
    elapsed_bench_ms = (time.perf_counter() - start_bench) * 1000
    avg_latency = elapsed_bench_ms / 50
    print(f"  Processed premarket news mapping for all 50 symbols.")
    print(f"  Total Duration   : {elapsed_bench_ms:.2f}ms")
    print(f"  Average Latency  : {avg_latency:.2f}ms per symbol")

    # --- M. Telemetry and Latency Metrics ---
    print("\nM. Telemetry and Latency Metrics")
    print("--------------------------------")
    res_telemetry = database.execute_query("SELECT count(*) FROM latency_metrics WHERE stage = 'GEIE_ENGINE';", fetch=True)
    print(f"  Telemetry rows recorded in Database: {res_telemetry[0][0]}")

    # --- N. Database Persistence Verification ---
    print("\nN. Database Persistence Verification")
    print("------------------------------------")
    db_event = GEIEPersistence.load_latest_event()
    if db_event:
        print(f"  Latest Saved Event ID   : {db_event['event_id']}")
        print(f"  Latest Saved Timestamp  : {db_event['timestamp']}")
        print(f"  Latest Saved Sentiment  : {db_event['market_sentiment']}")
        print(f"  Latest Saved Beneficiary: {db_event['top_beneficiaries']}")
    else:
        print("  Error: No saved event found in database.")

if __name__ == "__main__":
    run_geie_verification()
