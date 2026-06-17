"""
Production Slack Incoming Webhook implementation.
Sends messages to a Slack channel via Incoming Webhook URL.
Uses urllib only — no extra dependencies required.
"""

import urllib.request
import urllib.error
import json
import sys
from interfaces.slack import SlackInterface


class SlackProduction(SlackInterface):
    """
    Real Slack implementation using Incoming Webhooks.
    Each message posts to the configured #channel directly.
    Slack markdown: *bold*, _italic_, `code`, ```block```
    """

    TIMEOUT = 5  # seconds — same as Telegram

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.consecutive_failures = 0

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _send(self, text: str) -> bool:
        """POST payload to Slack Incoming Webhook. Returns True on success."""
        payload = {"text": text}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                if body.strip() == "ok":
                    self.consecutive_failures = 0
                    return True
                else:
                    self.consecutive_failures += 1
                    print(f"[Slack PRODUCTION] Unexpected response: {body}", file=sys.stderr)
                    return False
        except urllib.error.HTTPError as e:
            self.consecutive_failures += 1
            print(f"[Slack PRODUCTION] HTTP {e.code}: {e.reason}", file=sys.stderr)
            raise
        except urllib.error.URLError as e:
            self.consecutive_failures += 1
            print(f"[Slack PRODUCTION] Network error: {e.reason}", file=sys.stderr)
            raise
        except Exception as e:
            self.consecutive_failures += 1
            print(f"[Slack PRODUCTION] Unexpected error: {e}", file=sys.stderr)
            raise

    @staticmethod
    def _telegram_to_slack(message: str) -> str:
        """Convert Telegram HTML tags to Slack mrkdwn format."""
        return (
            message
            .replace("<b>", "*").replace("</b>", "*")
            .replace("<i>", "_").replace("</i>", "_")
            .replace("<code>", "`").replace("</code>", "`")
            .replace("<pre>", "```\n").replace("</pre>", "\n```")
        )

    # ------------------------------------------------------------------
    # SlackInterface implementation
    # ------------------------------------------------------------------

    def send_alert(self, message: str) -> bool:
        """Send a signal alert to Slack channel."""
        print(f"[Slack PRODUCTION ALERT] Dispatching to Slack channel...")
        try:
            result = self._send(self._telegram_to_slack(message))
            if result:
                print("[Slack PRODUCTION ALERT] OK Sent successfully.")
            return result
        except Exception as e:
            print(f"[Slack PRODUCTION ALERT] FAILED: {e}")
            return False

    def send_admin_warning(self, message: str) -> bool:
        """Send an admin warning to Slack channel."""
        print(f"[Slack PRODUCTION WARNING] Dispatching to Slack channel...")
        try:
            result = self._send(self._telegram_to_slack(message))
            if result:
                print("[Slack PRODUCTION WARNING] OK Sent successfully.")
            return result
        except Exception as e:
            print(f"[Slack PRODUCTION WARNING] FAILED: {e}")
            return False
