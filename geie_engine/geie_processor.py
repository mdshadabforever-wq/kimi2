import datetime
import json
import time
from decimal import Decimal
from interfaces.base import ServiceRegistry
import redis_client
from audit import log_audit
from geie_engine.persistence import GEIEPersistence
from geie_engine.master_map_loader import GEIEMasterMapLoader
from geie_engine.telemetry import GEIETelemetry
from market_data.instrument_loader import InstrumentLoader

class GEIEProcessor:
    def __init__(self):
        self.redis_key = "geie:daily_event"
        
    def run_premarket(self, timestamp: datetime.datetime, force_refresh: bool = False) -> dict:
        """Runs premarket GEIE analysis at 08:05 AM using Perplexity and Gemini APIs."""
        start_time = time.perf_counter()
        
        # Check if already cached in Redis and force_refresh is False
        if not force_refresh:
            cached_data = redis_client.get_val(self.redis_key)
            if cached_data:
                try:
                    payload = json.loads(cached_data)
                    # Audit cache hit
                    log_audit(
                        component="GEIE_ENGINE",
                        action="PREMARKET_RUN",
                        result="SUCCESS",
                        reason="Loaded GEIE results from Redis cache"
                    )
                    return payload
                except Exception:
                    pass
                    
        # Seed master map if empty
        mapping = GEIEMasterMapLoader.load_triggers()
        if not mapping:
            GEIEMasterMapLoader.seed_master_map()
            mapping = GEIEMasterMapLoader.load_triggers()
            
        try:
            # 1. Fetch news via Perplexity
            perplexity = ServiceRegistry.get("perplexity")
            global_news = perplexity.fetch_global_news()
            india_news = perplexity.fetch_india_news()
            # 2. Analyze news impact via Gemini
            gemini = ServiceRegistry.get("gemini")
            payload = gemini.analyze_news_impact(global_news, india_news)
            
            # 4. Enforce mandatory keys and fields
            payload["event_id"] = f"GEIE-{timestamp.strftime('%Y-%m-%d')}-001"
            payload["timestamp"] = timestamp.strftime('%Y-%m-%d %H:%M:%S IST')
            payload["geie_status"] = "ACTIVE"
            
            # 5. Populate missing symbols from NIFTY 50 as NEUTRAL to ensure complete mapping
            all_symbols = InstrumentLoader().symbols
            stock_impacts = payload.get("stock_impacts", {})
            for sym in all_symbols:
                if sym not in stock_impacts:
                    stock_impacts[sym] = {
                        "direction": "NEUTRAL",
                        "magnitude": 1,
                        "reasons": ["Neutral market background"],
                        "confidence": "LOW",
                        "urgency": "INTRADAY"
                    }
            payload["stock_impacts"] = stock_impacts
            
            # 6. Save to database geie_events table
            GEIEPersistence.save_event(
                event_id=payload["event_id"],
                timestamp=timestamp,
                market_sentiment=payload["market_sentiment"],
                fii_5day_trend=payload["fii_5day_trend"],
                institutional_bias=payload["institutional_bias"],
                key_support=payload["key_support_from_options"],
                key_resistance=payload["key_resistance_from_options"],
                top_beneficiaries=payload["top_beneficiaries"],
                top_losers=payload["top_losers"],
                status=payload["geie_status"],
                raw_output=payload
            )
            
            # 7. Cache in Redis (valid for 24 hours)
            redis_client.set_val(self.redis_key, json.dumps(payload, default=str), ex=86400)
            
            # Record telemetry
            duration_ms = (time.perf_counter() - start_time) * 1000
            GEIETelemetry.record_latency("GLOBAL", duration_ms)
            
            # Log success
            log_audit(
                component="GEIE_ENGINE",
                action="PREMARKET_RUN",
                result="SUCCESS",
                reason="Premarket GEIE analysis run completed successfully"
            )
            return payload
            
        except Exception as e:
            # Failure Policy: fallback to Redis snapshot if valid (less than 60 min old)
            log_audit(
                component="GEIE_ENGINE",
                action="PREMARKET_RUN",
                result="FAILED",
                reason=f"Premarket run failed: {str(e)}"
            )
            
            cached_data = redis_client.get_val(self.redis_key)
            if cached_data:
                try:
                    payload = json.loads(cached_data)
                    cached_ts_str = payload.get("timestamp", "")
                    if cached_ts_str:
                        # Extract cached time and verify within 60 minutes
                        cached_dt = datetime.datetime.strptime(cached_ts_str.split(" IST")[0], "%Y-%m-%d %H:%M:%S")
                        age_seconds = (timestamp - cached_dt).total_seconds()
                        if age_seconds <= 3600.0:
                            # Re-cache with remaining TTL
                            log_audit(
                                component="GEIE_ENGINE",
                                action="API_FALLBACK",
                                result="WARNING",
                                reason=f"Gemini/Perplexity failed. Reusing valid cached payload (age: {age_seconds:.1f}s)"
                            )
                            return payload
                except Exception as ex:
                    print(f"[GEIE PROCESSOR] Error checking cache age: {ex}")
                    
            # If expired or missing, default all stock directions to NEUTRAL
            log_audit(
                component="GEIE_ENGINE",
                action="API_FALLBACK",
                result="WARNING",
                reason="Gemini/Perplexity failed and no valid cache found. Defaulting all symbols to NEUTRAL."
            )
            
            fallback_payload = self.generate_unavailable_fallback(timestamp)
            # Cache the fallback payload for 60 minutes
            redis_client.set_val(self.redis_key, json.dumps(fallback_payload, default=str), ex=3600)
            return fallback_payload
            
    def generate_unavailable_fallback(self, timestamp: datetime.datetime) -> dict:
        """Generates a default fallback dict with UNAVAILABLE status and NEUTRAL stock impacts."""
        all_symbols = InstrumentLoader().symbols
        stock_impacts = {}
        for sym in all_symbols:
            stock_impacts[sym] = {
                "direction": "NEUTRAL",
                "magnitude": 1,
                "reasons": ["GEIE Outage fallback"],
                "confidence": "LOW",
                "urgency": "INTRADAY"
            }
            
        return {
            "event_id": f"GEIE-{timestamp.strftime('%Y-%m-%d')}-001",
            "timestamp": timestamp.strftime('%Y-%m-%d %H:%M:%S IST'),
            "market_sentiment": "NEUTRAL",
            "stock_impacts": stock_impacts,
            "fii_5day_trend": "MIXED",
            "institutional_bias": "NEUTRAL",
            "key_support_from_options": "N/A",
            "key_resistance_from_options": "N/A",
            "top_beneficiaries": [],
            "top_losers": [],
            "geie_status": "UNAVAILABLE"
        }
        
    def propagate_triggers(self, triggers: list) -> dict:
        """Evaluates stock impacts using correlation triggers from database master map."""
        mapping = GEIEMasterMapLoader.load_triggers()
        if not mapping:
            GEIEMasterMapLoader.seed_master_map()
            mapping = GEIEMasterMapLoader.load_triggers()
            
        all_symbols = InstrumentLoader().symbols
        stock_impacts = {}
        
        for sym in all_symbols:
            sym_map = mapping.get(sym, {"positive": [], "negative": [], "neutral": []})
            
            # Check overlap
            pos_overlap = set(sym_map["positive"]).intersection(triggers)
            neg_overlap = set(sym_map["negative"]).intersection(triggers)
            
            if pos_overlap:
                direction = "POSITIVE"
                reasons = [f"Triggered by positive correlation: {', '.join(pos_overlap)}"]
                confidence = "HIGH"
                magnitude = 2
            elif neg_overlap:
                direction = "NEGATIVE"
                reasons = [f"Triggered by negative correlation: {', '.join(neg_overlap)}"]
                confidence = "HIGH"
                magnitude = 2
            else:
                direction = "NEUTRAL"
                reasons = ["No matching triggers in news"]
                confidence = "LOW"
                magnitude = 1
                
            stock_impacts[sym] = {
                "direction": direction,
                "magnitude": magnitude,
                "reasons": reasons,
                "confidence": confidence,
                "urgency": "INTRADAY"
            }
            
        return stock_impacts
        
    @staticmethod
    def calculate_market_sentiment(news_bias: float, fii_trend_bias: float, options_bias: float) -> str:
        """Formulates market sentiment based on news, FII flow, and options open interest bias."""
        w1, w2, w3 = 0.40, 0.40, 0.20
        score = w1 * news_bias + w2 * fii_trend_bias + w3 * options_bias
        
        if score >= 0.25:
            return "RISK_ON"
        elif score <= -0.25:
            return "RISK_OFF"
        else:
            return "NEUTRAL"
