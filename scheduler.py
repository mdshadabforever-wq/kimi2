import asyncio
import datetime
from typing import List

import database
import redis_client
from interfaces.base import ServiceRegistry
from audit import log_audit
from orchestrator import Orchestrator
from live_scan_loop import LiveScanLoop

class Scheduler:
    """Manages system schedules and chronological triggers (08:05 GEIE, 08:20 ARC, 09:15 Live Loop, 16:00 Postmarket).
    Supports accelerated execution on startup for MOCK_MODE demo.
    """

    def __init__(self, orchestrator: Orchestrator, live_loop: LiveScanLoop):
        self.orchestrator = orchestrator
        self.live_loop = live_loop
        self.is_running = False

    async def start(self):
        """Starts the scheduler. Performs the accelerated boot sequence and runs schedule checking."""
        self.is_running = True
        print("[SCHEDULER] Starting chronological scheduler...")
        
        # 1. Run Accelerated Startup (simulate morning tasks so system is immediately ready)
        await self._run_accelerated_morning_sequence()
        
        # 2. Start Clock Monitor Loop for multi-day transitions
        asyncio.create_task(self._clock_monitor_loop())

    async def _run_accelerated_morning_sequence(self):
        """Accelerates pre-market tasks sequentially to start live scans immediately on boot."""
        print("[SCHEDULER] Running accelerated startup sequence...")
        now = datetime.datetime.now()
        
        # 1. 08:05 AM - GEIE run
        geie_time = now.replace(hour=8, minute=5, second=0, microsecond=0)
        geie_payload = self.orchestrator.run_premarket_geie(geie_time)
        print(f"[SCHEDULER] Accelerated GEIE run complete. Sentiment: {geie_payload.get('market_sentiment')}")
        
        # 2. 08:20 AM - ARC Premarket Batch Review
        arc_time = now.replace(hour=8, minute=20, second=0, microsecond=0)
        symbols = self.live_loop.all_symbols
        results = self.orchestrator.run_premarket_arc(arc_time, symbols, geie_payload)
        
        # 3. Calculate and send Premarket Brief Telegram Notification (Specification format)
        approve_count = sum(1 for v in results.values() if v == "APPROVE")
        caution_count = sum(1 for v in results.values() if v == "CAUTION")
        reject_count = sum(1 for v in results.values() if v == "REJECT")
        
        brief = f"ARC Premarket Review Complete: {approve_count} APPROVE / {caution_count} CAUTION / {reject_count} REJECT"
        telegram = ServiceRegistry.get("telegram")
        telegram.send_alert(brief)
        slack = ServiceRegistry.get("slack")
        slack.send_alert(brief)
        print(f"[SCHEDULER] Premarket Brief Sent: {brief}")
        
        # 4. 09:15 AM - Start the Live Scan Loop
        print("[SCHEDULER] Starting Live Scan Loop...")
        await self.live_loop.start()

    async def _clock_monitor_loop(self):
        """Monitors system wall clock and executes scheduled jobs at their daily times."""
        last_checked_minute = -1
        while self.is_running:
            now = datetime.datetime.now()
            current_time = now.time()
            
            # Run checks only when minute transitions
            if now.minute != last_checked_minute:
                last_checked_minute = now.minute
                
                # 08:05 AM IST - GEIE run
                if current_time.hour == 8 and current_time.minute == 5:
                    self.orchestrator.run_premarket_geie(now)
                    
                # 08:20 AM IST - ARC Batch Review
                elif current_time.hour == 8 and current_time.minute == 20:
                    geie_payload = self.orchestrator.run_premarket_geie(now) # Load cache
                    results = self.orchestrator.run_premarket_arc(now, self.live_loop.all_symbols, geie_payload)
                    approve_count = sum(1 for v in results.values() if v == "APPROVE")
                    caution_count = sum(1 for v in results.values() if v == "CAUTION")
                    reject_count = sum(1 for v in results.values() if v == "REJECT")
                    brief = f"ARC Premarket Review Complete: {approve_count} APPROVE / {caution_count} CAUTION / {reject_count} REJECT"
                    telegram = ServiceRegistry.get("telegram")
                    telegram.send_alert(brief)
                    slack = ServiceRegistry.get("slack")
                    slack.send_alert(brief)
                    
                # 09:15 AM IST - Start live scan loop
                elif current_time.hour == 9 and current_time.minute == 15:
                    if not self.live_loop.is_running:
                        await self.live_loop.start()
                        
                # 04:00 PM (16:00) IST - Run Postmarket Review
                elif current_time.hour == 16 and current_time.minute == 0:
                    print(f"[SCHEDULER] Executing Postmarket Review at {now}...")
                    # Query all signals generated today
                    today = now.date()
                    try:
                        query = "SELECT * FROM signals WHERE DATE(timestamp) = %s;"
                        rows = database.execute_query(query, (today,), fetch=True)
                        session_signals = []
                        if rows:
                            # Map signal rows to dict for Claude review
                            for r in rows:
                                session_signals.append({
                                    "signal_id": r[0],
                                    "timestamp": str(r[1]),
                                    "symbol": r[2],
                                    "direction": r[3],
                                    "score": float(r[4]),
                                    "risk_grade": r[19],
                                    "status": r[20]
                                })
                        self.orchestrator.arc_processor.run_postmarket(session_signals)
                    except Exception as e:
                        print(f"[SCHEDULER] Failed to run post-market review: {e}")
                        
            await asyncio.sleep(10) # check time every 10 seconds
