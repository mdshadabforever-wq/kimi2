import asyncio
import datetime
import database
import ghost_mode
import health_monitor
from audit import log_audit

class RuntimeMonitor:
    """Watches system health, coordinates Ghost Mode activations, and auto-expires active trade alerts."""

    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
        self.is_running = False

    async def start(self):
        """Starts the periodic runtime monitor loops in the background."""
        self.is_running = True
        print("[RUNTIME MONITOR] Starting health checks and auto-expiry tasks...")
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._expiry_check_loop())

    def stop(self):
        self.is_running = False
        print("[RUNTIME MONITOR] Stopped.")

    async def _health_check_loop(self):
        """Periodically calls health checks for all engines and pings DB/Redis."""
        while self.is_running:
            try:
                # Call the existing health monitor cycle
                await health_monitor.run_single_health_cycle()
            except Exception as e:
                print(f"[RUNTIME MONITOR] Health monitor cycle encountered an error: {e}")
            await asyncio.sleep(self.interval_seconds)

    async def _expiry_check_loop(self):
        """Checks for active signals that have exceeded their regime validity window and marks them EXPIRED."""
        while self.is_running:
            try:
                # Set timezone-aware UTC datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                
                # Fetch ACTIVE signals past valid_until
                query = """
                    SELECT signal_id, symbol, valid_until FROM signals 
                    WHERE status = 'ACTIVE' AND valid_until <= %s;
                """
                expired_rows = database.execute_query(query, (now,), fetch=True)
                
                if expired_rows:
                    for row in expired_rows:
                        sig_id, symbol, valid_until = row
                        
                        # Update status in signals table
                        update_query = "UPDATE signals SET status = 'EXPIRED' WHERE signal_id = %s;"
                        database.execute_query(update_query, (sig_id,))
                        
                        # Log to audit trail
                        log_audit(
                            component="RuntimeMonitor",
                            action="AUTO_EXPIRE_SIGNAL",
                            result="SUCCESS",
                            reason=f"Signal {sig_id} for {symbol} has expired past {valid_until}",
                            metadata={"signal_id": sig_id, "symbol": symbol, "valid_until": str(valid_until)}
                        )
                        print(f"[RUNTIME MONITOR] Auto-expired signal {sig_id} for {symbol} (Validity window elapsed).")
            except Exception as e:
                print(f"[RUNTIME MONITOR] Expiry check encountered an error: {e}")
            await asyncio.sleep(15) # Check for expirations every 15 seconds
