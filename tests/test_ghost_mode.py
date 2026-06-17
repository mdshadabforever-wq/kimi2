import pytest
from interfaces.base import ServiceRegistry
import redis_client
import ghost_mode
from bootstrap import register_services
from mocks.telegram_mock import TelegramMock

def test_ghost_mode_activation_and_resume():
    """Verify Ghost Mode activation: queue purge, Telegram alerts, and manual reset.

    Forces TelegramMock to be registered for this test, regardless of whether
    TELEGRAM_BOT_TOKEN is set in the environment. This ensures sent_messages and
    clear() are always available without depending on env state.
    """
    # Ensure all other services are registered
    register_services()

    # Force a fresh TelegramMock so sent_messages and clear() are always available
    telegram_mock = TelegramMock()
    ServiceRegistry.register("telegram", telegram_mock)

    # Pre-populate dummy alert queue
    redis_client.set_val("iiis:alert_queue", "pending_alert_payload")
    assert redis_client.get_val("iiis:alert_queue") == "pending_alert_payload"

    # Use the mock reference directly
    telegram_mock.clear()

    # Activate Ghost Mode
    ghost_mode.activate_ghost_mode("Simulated crash event")
    assert ghost_mode.is_ghost_mode_active() is True

    # Verify alert queue was purged
    assert redis_client.get_val("iiis:alert_queue") is None

    # Verify Telegram warnings were sent
    assert len(telegram_mock.sent_messages) == 1
    msg_type, msg_body = telegram_mock.sent_messages[0]
    assert msg_type == "WARNING"
    assert "🚨 GHOST MODE ACTIVATED" in msg_body
    assert "Simulated crash event" in msg_body

    # Attempt manual resume
    res = ghost_mode.resume_system()
    assert res is True
    assert ghost_mode.is_ghost_mode_active() is False

    # Verify Telegram notification for resume
    assert len(telegram_mock.sent_messages) == 2
    assert "IIIS System Resumed" in telegram_mock.sent_messages[1][1]
