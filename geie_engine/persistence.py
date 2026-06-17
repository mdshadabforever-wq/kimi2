import datetime
import json
from decimal import Decimal
import database

class GEIEPersistence:
    @staticmethod
    def save_event(
        event_id: str,
        timestamp: datetime.datetime,
        market_sentiment: str,
        fii_5day_trend: str,
        institutional_bias: str,
        key_support: str,
        key_resistance: str,
        top_beneficiaries: list,
        top_losers: list,
        status: str,
        raw_output: dict
    ):
        """Saves a GEIE event and its details into the database."""
        query = """
            INSERT INTO geie_events (
                event_id, timestamp, event_name, impact_direction, confidence, 
                urgency, beneficiaries, losers, neutral, raw_output
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING;
        """
        
        # Format beneficiaries and losers as JSONB lists
        beneficiaries_json = json.dumps(top_beneficiaries)
        losers_json = json.dumps(top_losers)
        neutral_json = json.dumps([]) # Optional details
        raw_output_json = json.dumps(raw_output, default=str)
        
        try:
            database.execute_query(query, (
                event_id,
                timestamp,
                "PREMARKET_RUN",
                market_sentiment,
                "HIGH", # Confidence
                "INTRADAY", # Urgency
                beneficiaries_json,
                losers_json,
                neutral_json,
                raw_output_json
            ))
        except Exception as e:
            print(f"[GEIE PERSISTENCE] Error saving event {event_id}: {e}")

    @staticmethod
    def load_latest_event() -> dict:
        """Loads the latest GEIE event from database."""
        query = """
            SELECT event_id, timestamp, impact_direction, beneficiaries, losers, raw_output
            FROM geie_events
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        def parse_jsonb(val):
            if not val:
                return [] if isinstance(val, list) else {}
            if isinstance(val, str):
                return json.loads(val)
            return val

        try:
            res = database.execute_query(query, fetch=True)
            if res:
                row = res[0]
                return {
                    "event_id": row[0],
                    "timestamp": row[1],
                    "market_sentiment": row[2],
                    "top_beneficiaries": parse_jsonb(row[3]),
                    "top_losers": parse_jsonb(row[4]),
                    "raw_output": parse_jsonb(row[5])
                }
        except Exception as e:
            print(f"[GEIE PERSISTENCE] Error loading latest event: {e}")
        return None
