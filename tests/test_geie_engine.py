import datetime
import pytest
from unittest.mock import patch
from interfaces.base import ServiceRegistry
import redis_client
import database
from bootstrap import register_services
from geie_engine.geie_processor import GEIEProcessor
from geie_engine.master_map_loader import GEIEMasterMapLoader
from geie_engine.persistence import GEIEPersistence
from mocks.gemini_mock import GeminiMock
from mocks.perplexity_mock import PerplexityMock

@pytest.fixture(scope="module", autouse=True)
def setup_services_and_db():
    database.init_db("schema.sql")
    # Clean tables
    database.execute_query("DELETE FROM geie_events;")
    database.execute_query("DELETE FROM geie_master_map;")
    database.execute_query("DELETE FROM latency_metrics;")
    
    # Initialize dependency registry
    register_services()

def test_geie_processor_premarket_success():
    """Test successful premarket run using mock APIs."""
    processor = GEIEProcessor()
    t = datetime.datetime(2026, 6, 15, 8, 5, 0)
    
    # Ensure redis clean
    redis_client.delete_val(processor.redis_key)
    
    payload = processor.run_premarket(t, force_refresh=True)
    assert payload["geie_status"] == "ACTIVE"
    assert payload["market_sentiment"] == "RISK_ON"
    assert "TATASTEEL" in payload["stock_impacts"]
    assert payload["stock_impacts"]["TATASTEEL"]["direction"] == "POSITIVE"
    
    # Verify cached in Redis
    cached = redis_client.get_val(processor.redis_key)
    assert cached is not None
    
    # Verify saved in Database
    db_event = GEIEPersistence.load_latest_event()
    assert db_event is not None
    assert db_event["event_id"] == payload["event_id"]

def test_market_sentiment_calculation():
    """Test market sentiment formula logic."""
    # Score = 0.40 * news + 0.40 * fii + 0.20 * options
    # Risk On: Score >= 0.25
    assert GEIEProcessor.calculate_market_sentiment(1.0, 1.0, 1.0) == "RISK_ON"
    # Risk Off: Score <= -0.25
    assert GEIEProcessor.calculate_market_sentiment(-1.0, -1.0, -1.0) == "RISK_OFF"
    # Neutral: Score between -0.25 and 0.25
    assert GEIEProcessor.calculate_market_sentiment(0.0, 0.0, 0.0) == "NEUTRAL"
    assert GEIEProcessor.calculate_market_sentiment(0.5, -0.5, 0.0) == "NEUTRAL" # 0.4*0.5 - 0.4*0.5 + 0 = 0

def test_correlation_trigger_propagation():
    """Test correlation map keyword trigger propagation."""
    processor = GEIEProcessor()
    GEIEMasterMapLoader.seed_master_map()
    
    # Trigger keyword: steel_price_up
    impacts = processor.propagate_triggers(["steel_price_up"])
    
    # TATASTEEL has steel_price_up as positive trigger
    assert impacts["TATASTEEL"]["direction"] == "POSITIVE"
    assert impacts["TATASTEEL"]["confidence"] == "HIGH"
    
    # JSWSTEEL has steel_price_up as positive trigger
    assert impacts["JSWSTEEL"]["direction"] == "POSITIVE"
    
    # HDFCBANK has no overlap
    assert impacts["HDFCBANK"]["direction"] == "NEUTRAL"
    
    # Trigger keyword: rate_hike (negative for banking)
    impacts_rate_hike = processor.propagate_triggers(["rate_hike"])
    assert impacts_rate_hike["HDFCBANK"]["direction"] == "NEGATIVE"
    assert impacts_rate_hike["TATASTEEL"]["direction"] == "NEUTRAL"

def test_gemini_api_failure_recovery_with_cache():
    """Test fallback to valid Redis snapshot on Gemini API failure."""
    processor = GEIEProcessor()
    t = datetime.datetime(2026, 6, 15, 8, 10, 0)
    
    # Seed valid payload in Redis (5 min old)
    seeded_payload = {
        "event_id": "GEIE-2026-06-15-001",
        "timestamp": "2026-06-15 08:05:00 IST",
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
    import json
    redis_client.set_val(processor.redis_key, json.dumps(seeded_payload), ex=3600)
    
    # Mock Gemini fail
    gemini_mock = ServiceRegistry.get("gemini")
    gemini_mock.simulate_error = True
    
    try:
        # Should catch failure and fallback to Redis cache
        payload = processor.run_premarket(t, force_refresh=True)
        assert payload["geie_status"] == "ACTIVE"
        assert payload["market_sentiment"] == "RISK_ON"
        assert payload["stock_impacts"]["TATASTEEL"]["direction"] == "POSITIVE"
    finally:
        gemini_mock.simulate_error = False

def test_dual_api_failure_recovery():
    """Test fallback to default UNAVAILABLE payload when both APIs fail and cache is missing/expired."""
    processor = GEIEProcessor()
    t = datetime.datetime(2026, 6, 15, 9, 30, 0)
    
    # Delete cache to simulate expired/missing cache
    redis_client.delete_val(processor.redis_key)
    
    perplexity_mock = ServiceRegistry.get("perplexity")
    gemini_mock = ServiceRegistry.get("gemini")
    
    # Simulate errors
    perplexity_mock.simulate_error = True
    gemini_mock.simulate_error = True
    
    try:
        payload = processor.run_premarket(t, force_refresh=True)
        # Should return default payload
        assert payload["geie_status"] == "UNAVAILABLE"
        assert payload["market_sentiment"] == "NEUTRAL"
        assert payload["stock_impacts"]["TATASTEEL"]["direction"] == "NEUTRAL"
        assert payload["stock_impacts"]["HDFCBANK"]["direction"] == "NEUTRAL"
    finally:
        perplexity_mock.simulate_error = False
        gemini_mock.simulate_error = False
