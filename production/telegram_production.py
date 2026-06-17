"""
Production Telegram interface implementation.
Sends messages to the real Telegram Bot API using urllib (stdlib only — no extra deps).
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import sys
from interfaces.telegram import TelegramInterface


class TelegramProduction(TelegramInterface):
    """
    Real Telegram Bot implementation.
    Uses the Telegram Bot API sendMessage endpoint via HTTPS.
    """

    API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
    TIMEOUT = 5  # seconds

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.consecutive_failures = 0

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _send(self, message: str) -> bool:
        """POST message to Telegram Bot API. Returns True on success."""
        url = self.API_BASE.format(token=self.bot_token)

        # Telegram API payload
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("ok"):
                    self.consecutive_failures = 0
                    return True
                else:
                    self.consecutive_failures += 1
                    print(
                        f"[Telegram PRODUCTION] API error: {body.get('description', 'Unknown')}",
                        file=sys.stderr,
                    )
                    return False
        except urllib.error.HTTPError as e:
            self.consecutive_failures += 1
            print(f"[Telegram PRODUCTION] HTTP {e.code}: {e.reason}", file=sys.stderr)
            raise
        except urllib.error.URLError as e:
            self.consecutive_failures += 1
            print(f"[Telegram PRODUCTION] Network error: {e.reason}", file=sys.stderr)
            raise
        except Exception as e:
            self.consecutive_failures += 1
            print(f"[Telegram PRODUCTION] Unexpected error: {e}", file=sys.stderr)
            raise

    # ------------------------------------------------------------------
    # TelegramInterface implementation
    # ------------------------------------------------------------------

    def send_alert(self, message: str) -> bool:
        """Send a normal market signal alert."""
        print(f"[Telegram PRODUCTION ALERT] Dispatching to chat {self.chat_id}...")
        try:
            result = self._send(message)
            if result:
                print("[Telegram PRODUCTION ALERT] OK Sent successfully.")
            return result
        except Exception as e:
            print(f"[Telegram PRODUCTION ALERT] FAILED: {e}")
            return False

    def send_admin_warning(self, message: str) -> bool:
        """Send an admin-level warning (Ghost Mode, risk breach, etc.)."""
        print(f"[Telegram PRODUCTION WARNING] Dispatching to chat {self.chat_id}...")
        try:
            result = self._send(message)
            if result:
                print("[Telegram PRODUCTION WARNING] OK Sent successfully.")
            return result
        except Exception as e:
            print(f"[Telegram PRODUCTION WARNING] FAILED: {e}")
            return False
