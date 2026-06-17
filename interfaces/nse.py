from abc import ABC, abstractmethod
from typing import List, Dict, Any

class NSEInterface(ABC):

    @abstractmethod
    def fetch_fii_dii_data(self) -> Dict[str, Any]:
        """Scrapes FII/DII daily transaction values from official NSE website."""
        pass

    @abstractmethod
    def fetch_bulk_deals(self) -> List[Dict[str, Any]]:
        """Scrapes intraday bulk deals from official NSE website."""
        pass
