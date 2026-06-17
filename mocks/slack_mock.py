import sys
from interfaces.slack import SlackInterface


class SlackMock(SlackInterface):
    """Mock Slack implementation for testing."""

    def __init__(self):
        self.simulate_error = False
        self.consecutive_failures = 0
        self.sent_messages = []

    def send_alert(self, message: str) -> bool:
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated Slack Error")
        self.consecutive_failures = 0
        self.sent_messages.append(("ALERT", message))
        enc = sys.stdout.encoding or "utf-8"
        safe = message.encode(enc, errors="replace").decode(enc)
        print(f"[Slack Mock ALERT] {safe}")
        return True

    def send_admin_warning(self, message: str) -> bool:
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated Slack Error")
        self.consecutive_failures = 0
        self.sent_messages.append(("WARNING", message))
        enc = sys.stdout.encoding or "utf-8"
        safe = message.encode(enc, errors="replace").decode(enc)
        print(f"[Slack Mock WARNING] {safe}")
        return True

    def clear(self):
        self.sent_messages.clear()
        self.consecutive_failures = 0
