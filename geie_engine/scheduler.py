import datetime
from geie_engine.geie_processor import GEIEProcessor

class GEIEScheduler:
    @staticmethod
    def execute_premarket_job(timestamp: datetime.datetime) -> dict:
        """Executes the premarket job. Simulates triggering at 08:05 AM IST."""
        print(f"[GEIE SCHEDULER] Triggering premarket GEIE job at {timestamp.strftime('%Y-%m-%d 08:05:00 IST')}...")
        
        # Instantiate processor and run Premarket run
        processor = GEIEProcessor()
        # Force a refresh to simulate fresh premarket API calls
        result = processor.run_premarket(timestamp, force_refresh=True)
        
        print(f"[GEIE SCHEDULER] Premarket job finished. Status: {result['geie_status']}, Sentiment: {result['market_sentiment']}")
        return result
