import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Upstox API
    UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
    UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
    UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8000/callback")

    # AI APIs
    PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "iiis")
    DB_USER = os.getenv("DB_USER", "iiis_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "strong_password_here")

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    # Risk Settings
    CAPITAL = float(os.getenv("CAPITAL", "1000000"))
    RISK_PCT = float(os.getenv("RISK_PCT", "0.5"))
    MAX_DAILY_RISK_PCT = float(os.getenv("MAX_DAILY_RISK_PCT", "2.0"))
    HARD_STOP_LOSSES = int(os.getenv("HARD_STOP_LOSSES", "3"))

    # System
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    MOCK_MODE = os.getenv("MOCK_MODE", "True").lower() in ("true", "1", "yes")

    @classmethod
    def validate(cls):
        """Validates that all mandatory fields are present and structurally correct."""
        missing = []
        
        # Verify required keys
        required_keys = [
            "UPSTOX_API_KEY", "UPSTOX_API_SECRET",
            "PERPLEXITY_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY",
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_ADMIN_CHAT_ID",
            "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"
        ]
        for key in required_keys:
            if not getattr(cls, key):
                missing.append(key)

        if missing:
            print(f"CRITICAL: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)

        # Validate numeric ranges
        if not (0.0 < cls.RISK_PCT <= 10.0):
            raise ValueError("RISK_PCT must be between 0 and 10%")
        if not (0.0 < cls.MAX_DAILY_RISK_PCT <= 50.0):
            raise ValueError("MAX_DAILY_RISK_PCT must be between 0 and 50%")
        if cls.CAPITAL <= 0:
            raise ValueError("CAPITAL must be a positive number")
        if cls.HARD_STOP_LOSSES <= 0:
            raise ValueError("HARD_STOP_LOSSES must be a positive integer")

# Automatically validate on load
if os.getenv("IIIS_TESTING") != "True":
    Config.validate()
ClassConfig = Config
