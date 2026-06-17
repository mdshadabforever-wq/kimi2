from interfaces.telegram import TelegramInterface

class TelegramMock(TelegramInterface):
    def __init__(self):
        self.simulate_error = False
        self.simulate_timeout = False
        self.consecutive_failures = 0
        self.sent_messages = []

    def _handle_failures(self):
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated Telegram API Error")
        if self.simulate_timeout:
            self.consecutive_failures += 1
            raise TimeoutError("Simulated Telegram API Timeout")
        self.consecutive_failures = 0

    def send_alert(self, message: str) -> bool:
        self._handle_failures()
        self.sent_messages.append(("ALERT", message))
        import sys
        enc = sys.stdout.encoding or "utf-8"
        safe_msg = message.encode(enc, errors="replace").decode(enc)
        print(f"[Telegram Mock ALERT] {safe_msg}")
        return True

    def send_admin_warning(self, message: str) -> bool:
        self._handle_failures()
        self.sent_messages.append(("WARNING", message))
        import sys
        enc = sys.stdout.encoding or "utf-8"
        safe_msg = message.encode(enc, errors="replace").decode(enc)
        print(f"[Telegram Mock WARNING] {safe_msg}")
        return True

    def clear(self):
        self.sent_messages.clear()
        self.consecutive_failures = 0
