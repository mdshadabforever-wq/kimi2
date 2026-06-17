import time
from interfaces.perplexity import PerplexityInterface

class PerplexityMock(PerplexityInterface):
    def __init__(self):
        self.simulate_error = False
        self.simulate_timeout = False
        self.consecutive_failures = 0

    def _handle_failures(self):
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated Perplexity API Error")
        if self.simulate_timeout:
            self.consecutive_failures += 1
            # Simulate a timeout by raising a TimeoutError
            raise TimeoutError("Simulated Perplexity API Timeout")
        self.consecutive_failures = 0

    def fetch_global_news(self) -> str:
        self._handle_failures()
        return "Global Market News: US indices rise, commodity markets stable."

    def fetch_india_news(self) -> str:
        self._handle_failures()
        return "India Market News: Nifty trades near highs, RBI policy expectations neutral."
