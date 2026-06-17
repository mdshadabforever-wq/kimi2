import os
from interfaces.base import ServiceRegistry
from config import Config

def register_services():
    """Initializes and registers dependencies based on configuration (Mock or Real).

    Telegram and Slack use real implementations when their credentials are present
    (even in MOCK_MODE). Both dispatch alerts in parallel.
    All other services remain mocked.
    """
    if Config.MOCK_MODE:
        from mocks.upstox_mock import UpstoxMock
        from mocks.perplexity_mock import PerplexityMock
        from mocks.gemini_mock import GeminiMock
        from mocks.claude_mock import ClaudeMock
        from mocks.telegram_mock import TelegramMock
        from mocks.slack_mock import SlackMock
        from mocks.nse_mock import NSEMock

        # Register always-mocked services
        ServiceRegistry.register("upstox", UpstoxMock())
        ServiceRegistry.register("perplexity", PerplexityMock())
        ServiceRegistry.register("gemini", GeminiMock())
        ServiceRegistry.register("claude", ClaudeMock())
        ServiceRegistry.register("nse", NSEMock())

        # Telegram: real if credentials present, else mock
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
        if bot_token and chat_id:
            from production.telegram_production import TelegramProduction
            ServiceRegistry.register("telegram", TelegramProduction(bot_token=bot_token, chat_id=chat_id))
            print(f"[Bootstrap] REAL Telegram registered (chat_id={chat_id}).")
        else:
            ServiceRegistry.register("telegram", TelegramMock())
            print("[Bootstrap] Telegram Mock registered (no credentials).")

        # Slack: real if webhook URL present, else mock
        slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        if slack_webhook:
            from production.slack_production import SlackProduction
            ServiceRegistry.register("slack", SlackProduction(webhook_url=slack_webhook))
            print("[Bootstrap] REAL Slack registered (Incoming Webhook).")
        else:
            ServiceRegistry.register("slack", SlackMock())
            print("[Bootstrap] Slack Mock registered (no webhook URL).")

        print("Services registered successfully in ServiceRegistry.")
    else:
        raise NotImplementedError("Production APIs not implemented in Phase 1. Use MOCK_MODE=True.")
