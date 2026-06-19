import asyncio
import sys
import os
import datetime
from dotenv import load_dotenv

# Load environment variables from .env first so they take precedence over setdefault
load_dotenv()

# ── System flags ──────────────────────────────────────────────────────
os.environ.setdefault("IIIS_TESTING", "False")

# ── Real Telegram credentials ─────────────────────────────────────────
os.environ.setdefault("TELEGRAM_BOT_TOKEN",    "mock_bot_token")
os.environ.setdefault("TELEGRAM_ADMIN_CHAT_ID", "mock_chat_id")

# ── Real Slack Incoming Webhook ───────────────────────────────────────
# Set SLACK_WEBHOOK_URL in your .env file or environment before running.
os.environ.setdefault("SLACK_WEBHOOK_URL", "mock_webhook")

from bootstrap import register_services
from database import init_db
from seeder import seed_mock_data_for_demo
from orchestrator import Orchestrator
from live_scan_loop import LiveScanLoop
from scheduler import Scheduler
from runtime_monitor import RuntimeMonitor
from config import Config


def _reset_mock_risk_state():
    """In MOCK_MODE: reset today's risk state and signals so the daily risk
    limit and duplicate-signal gates are not pre-exhausted from previous
    test runs. Safe to call before engines start."""
    try:
        import database
        today = datetime.date.today()
        # Clear daily risk budget
        database.execute_query(
            "DELETE FROM risk_state WHERE session_date = %s;", (today,)
        )
        # Clear active_alerts (FK parent of signals) before deleting signals
        database.execute_query("DELETE FROM active_alerts;")
        # Clear today's signals so duplicate gate starts fresh
        database.execute_query(
            "DELETE FROM signals WHERE DATE(timestamp) = %s;", (today,)
        )
        print(f"[MOCK RESET] Risk state, active_alerts and signals cleared for {today}.")
    except Exception as e:
        print(f"[MOCK RESET] Could not reset risk state: {e}")


async def main():
    print("=================================================================")
    print("             INITIALIZING IIIS v4.6 MOCK TRADING SYSTEM          ")
    print("=================================================================")
    
    # 1. Register Mock Services in ServiceRegistry
    register_services()
    
    # 2. Initialize PostgreSQL database tables
    try:
        init_db("schema.sql")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize database: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. MOCK_MODE only — reset today's daily risk state so gates don't block
    if Config.MOCK_MODE:
        _reset_mock_risk_state()

    # 4. Send startup Telegram confirmation (proves real bot is wired)
    try:
        from interfaces.base import ServiceRegistry
        tg = ServiceRegistry.get("telegram")
        tg.send_admin_warning(
            "<b>IIIS v4.6 System Boot</b>\n"
            "Mock trading system started.\n"
            f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}\n"
            "Awaiting first scan cycle..."
        )
    except Exception as e:
        print(f"[MAIN] Startup Telegram notification failed: {e}")

    # 4b. Send Slack boot confirmation
    try:
        from interfaces.base import ServiceRegistry
        sl = ServiceRegistry.get("slack")
        sl.send_admin_warning(
            "*IIIS v4.6 System Boot*\n"
            "Mock trading system started.\n"
            f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}\n"
            "Awaiting first scan cycle..."
        )
    except Exception as e:
        print(f"[MAIN] Startup Slack notification failed: {e}")

    # 5. Instantiate Orchestrator
    orchestrator = Orchestrator()
    
    # 6. Instantiate Live Scan Loop
    live_loop = LiveScanLoop(orchestrator=orchestrator)
    
    # 7. Seed baseline mock historical database data
    # (Enables Trend, SMC, options, and composite scorers to yield passing signals)
    seed_mock_data_for_demo(live_loop.all_symbols)
    
    # 8. Warm up core engines using the constituents
    orchestrator.warmup_engines(live_loop.all_symbols)
    
    # 9. Instantiate Scheduler and Runtime Monitor
    scheduler = Scheduler(orchestrator=orchestrator, live_loop=live_loop)
    monitor = RuntimeMonitor(interval_seconds=30)
    
    # 10. Start Background Tasks
    await scheduler.start()
    await monitor.start()
    
    print("\n=================================================================")
    print("             IIIS MOCK TRADING SYSTEM BOOTED SUCCESSFULLY        ")
    print("=================================================================")
    
    # Keep the system running indefinitely
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\nShutting down IIIS system...")
        scheduler.live_loop.stop()
        monitor.stop()
        print("System shutdown complete.")

if __name__ == "__main__":
    # Ensure event loop runs the main task
    asyncio.run(main())
