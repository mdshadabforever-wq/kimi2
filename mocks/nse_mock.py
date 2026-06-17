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

    def fetch_block_deals(self) -> List[Dict[str, Any]]:
        self._handle_failures()
        now = datetime.datetime.now()
        return [
            {
                "timestamp": now - datetime.timedelta(minutes=10),
                "symbol": "RELIANCE",
                "deal_type": "SELL",
                "quantity": 500000,
                "price": 2400.00,
                "value_crores": 120.00,
                "client_name": "ICICI PRUDENTIAL MUTUAL FUND",
                "deal_category": "BLOCK"
            }
        ]

    def fetch_bhavcopy(self, download_date: datetime.date) -> List[Dict[str, Any]]:
        self._handle_failures()
        return [
            {
                "symbol": "RELIANCE",
                "open": 2400.00,
                "high": 2420.00,
                "low": 2390.00,
                "close": 2410.00,
                "volume": 5000000,
                "time": datetime.datetime.combine(download_date, datetime.time(15, 30))
            }
        ]

    def fetch_corporate_actions(self) -> List[Dict[str, Any]]:
        self._handle_failures()
        return [
            {
                "event_name": "Dividend - Rs 10 per share",
                "event_date": datetime.date.today(),
                "event_time": datetime.time(9, 15),
                "impact_level": "HIGH",
                "description": "RELIANCE Dividend payout session."
            }
        ]

DefinitionClass = NSEMock

