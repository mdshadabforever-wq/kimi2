from abc import ABC, abstractmethod
from typing import List, Dict, Any
import datetime

class NSEInterface(ABC):

    @abstractmethod
    def fetch_fii_dii_data(self) -> Dict[str, Any]:
        """Scrapes FII/DII daily transaction values from official NSE website."""
        pass

    @abstractmethod
    def fetch_bulk_deals(self) -> List[Dict[str, Any]]:
        """Scrapes intraday bulk deals from official NSE website."""
        pass

    @abstractmethod
    def fetch_block_deals(self) -> List[Dict[str, Any]]:
        """Scrapes block deals from official NSE website."""
        pass

    @abstractmethod
    def fetch_bhavcopy(self, download_date: datetime.date) -> List[Dict[str, Any]]:
        """Downloads and parses the equity bhavcopy for a specific date."""
        pass

    @abstractmethod
    def fetch_corporate_actions(self) -> List[Dict[str, Any]]:
        """Downloads corporate actions from the official NSE site."""
        pass

