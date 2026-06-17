import datetime
from typing import List, Dict, Any
from interfaces.nse import NSEInterface

class NSEMock(NSEInterface):
    def __init__(self):
        self.simulate_error = False
        self.simulate_timeout = False
        self.consecutive_failures = 0

    def _handle_failures(self):
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated NSE Scraping Error")
        if self.simulate_timeout:
            self.consecutive_failures += 1
            raise TimeoutError("Simulated NSE Scraping Timeout")
        self.consecutive_failures = 0

    def fetch_fii_dii_data(self) -> Dict[str, Any]:
        self._handle_failures()
        return {
            "date": datetime.date.today(),
            "fii_action": "BUYER",
            "fii_amount_crores": 1250.50,
            "dii_action": "BUYER",
            "dii_amount_crores": 320.10,
            "combined_bias": "BULLISH",
            "consecutive_fii_buy_days": 4,
            "consecutive_fii_sell_days": 0
        }

    def fetch_bulk_deals(self) -> List[Dict[str, Any]]:
        self._handle_failures()
        now = datetime.datetime.now()
        return [
            {
                "timestamp": now - datetime.timedelta(minutes=7),
                "symbol": "TATASTEEL",
                "deal_type": "BUY",
                "quantity": 2000000,
                "price": 150.10,
                "value_crores": 30.02,
                "client_name": "SOCIETE GENERALE",
                "deal_category": "BULK"
            }
        ]
DefinitionClass = NSEMock
