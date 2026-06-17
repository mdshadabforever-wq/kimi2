import os
from interfaces.base import ServiceRegistry
from config import Config

def register_services():
    """Initializes and registers dependencies based on configuration (Mock or Real).
    Wires production adapters if credentials are present, falling back to mocks otherwise.
    Allows easy activation of real APIs via configuration values only.
    """
    # 1. Retrieve environment keys
    upstox_key = os.getenv("UPSTOX_API_KEY")
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    claude_key = os.getenv("CLAUDE_API_KEY")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

    is_testing = os.getenv("IIIS_TESTING") == "True"

    # 2. Determine and Register Upstox Service
    if not is_testing and (not Config.MOCK_MODE or (upstox_key and "mock" not in upstox_key.lower())):
        from production.upstox_production import UpstoxProduction
        ServiceRegistry.register("upstox", UpstoxProduction())
        print("[Bootstrap] Registered PRODUCTION Upstox Adapter.")
    else:
        from mocks.upstox_mock import UpstoxMock
        ServiceRegistry.register("upstox", UpstoxMock())
        print("[Bootstrap] Registered MOCK Upstox Adapter.")

    # 3. Determine and Register Perplexity Service
    if not is_testing and (not Config.MOCK_MODE or (perplexity_key and "mock" not in perplexity_key.lower())):
        from production.perplexity_production import PerplexityProduction
        ServiceRegistry.register("perplexity", PerplexityProduction())
        print("[Bootstrap] Registered PRODUCTION Perplexity Adapter.")
    else:
        from mocks.perplexity_mock import PerplexityMock
        ServiceRegistry.register("perplexity", PerplexityMock())
        print("[Bootstrap] Registered MOCK Perplexity Adapter.")

    # 4. Determine and Register Gemini Service
    if not is_testing and (not Config.MOCK_MODE or (gemini_key and "mock" not in gemini_key.lower())):
        from production.gemini_production import GeminiProduction
        ServiceRegistry.register("gemini", GeminiProduction())
        print("[Bootstrap] Registered PRODUCTION Gemini Adapter.")
    else:
        from mocks.gemini_mock import GeminiMock
        ServiceRegistry.register("gemini", GeminiMock())
        print("[Bootstrap] Registered MOCK Gemini Adapter.")

    # 5. Determine and Register Claude Service
    if not is_testing and (not Config.MOCK_MODE or (claude_key and "mock" not in claude_key.lower())):
        from production.claude_production import ClaudeProduction
        ServiceRegistry.register("claude", ClaudeProduction())
        print("[Bootstrap] Registered PRODUCTION Claude Adapter.")
    else:
        from mocks.claude_mock import ClaudeMock
        ServiceRegistry.register("claude", ClaudeMock())
        print("[Bootstrap] Registered MOCK Claude Adapter.")

    # 6. Determine and Register NSE Service
    if not is_testing and not Config.MOCK_MODE:
        from production.nse_production import NSEProduction
        ServiceRegistry.register("nse", NSEProduction())
        print("[Bootstrap] Registered PRODUCTION NSE Scraper/Loader.")
    else:
        from mocks.nse_mock import NSEMock
        ServiceRegistry.register("nse", NSEMock())
        print("[Bootstrap] Registered MOCK NSE Scraper/Loader.")

    # 7. Determine and Register Telegram Service
    if not is_testing and telegram_token and telegram_chat and "mock" not in telegram_token.lower():
        from production.telegram_production import TelegramProduction
        ServiceRegistry.register("telegram", TelegramProduction(bot_token=telegram_token, chat_id=telegram_chat))
        print(f"[Bootstrap] Registered PRODUCTION Telegram bot (chat_id={telegram_chat}).")
    else:
        from mocks.telegram_mock import TelegramMock
        ServiceRegistry.register("telegram", TelegramMock())
        print("[Bootstrap] Registered MOCK Telegram bot.")

    # 8. Determine and Register Slack Service
    if not is_testing and slack_webhook and "mock" not in slack_webhook.lower():
        from production.slack_production import SlackProduction
        ServiceRegistry.register("slack", SlackProduction(webhook_url=slack_webhook))
        print("[Bootstrap] Registered PRODUCTION Slack Webhook.")
    else:
        from mocks.slack_mock import SlackMock
        ServiceRegistry.register("slack", SlackMock())
        print("[Bootstrap] Registered MOCK Slack Webhook.")

    print("[Bootstrap] All services bootstrapped successfully in ServiceRegistry.")
