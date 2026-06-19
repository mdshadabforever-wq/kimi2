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
        """POST payload to Slack. Supports Incoming Webhooks and OAuth Bot Tokens (xoxb-)."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        
        # Check if webhook_url is actually an OAuth Bot Token
        if self.webhook_url.startswith("xoxb-"):
            # Post to chat.postMessage API using Bot Token
            url = "https://slack.com/api/chat.postMessage"
            payload = {
                "channel": "#trading", # Default target channel
                "text": text
            }
            headers["Authorization"] = f"Bearer {self.webhook_url}"
        else:
            url = self.webhook_url
            payload = {"text": text}

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                
                is_success = False
                if body.strip() == "ok":
                    is_success = True
                else:
                    try:
                        resp_json = json.loads(body)
                        if resp_json.get("ok") is True:
                            is_success = True
                    except Exception:
                        pass
                        
                if is_success:
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
