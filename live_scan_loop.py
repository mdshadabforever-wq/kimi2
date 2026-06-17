import asyncio
import datetime
import time
from typing import List

import database
import ghost_mode
from interfaces.base import ServiceRegistry
from audit import log_audit
from market_data.instrument_loader import InstrumentLoader
from market_data.tick_processor import TickProcessor
from market_data.candle_builder import CandleBuilder, is_market_session_active
from orchestrator import Orchestrator

class LiveScanLoop:
    """Simulates the 60-second periodic live market scan loop.
    In MOCK_MODE, fetches ticks for symbols, feeds them to the TickProcessor/CandleBuilder,
    and runs signal evaluations via the Orchestrator.
    """

    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.candle_builder = CandleBuilder()
        self.tick_processor = TickProcessor(self.candle_builder.process_tick)
        self.is_running = False
        
        # Load Nifty 50 instruments list
        self.loader = InstrumentLoader()
        self.all_symbols = self.loader.symbols

    async def start(self):
        """Starts the infinite periodic scan loop (scans every 60 seconds)."""
        self.is_running = True
        print("[LIVE LOOP] Initializing live scan loop...")
        
        # Connect the mock WebSocket client
        upstox = ServiceRegistry.get("upstox")
        try:
            upstox.connect_websocket()
        except Exception as e:
            print(f"[LIVE LOOP] WebSocket connection failed: {e}")
            
        asyncio.create_task(self._run_loop())

    def stop(self):
        self.is_running = False
        upstox = ServiceRegistry.get("upstox")
        upstox.disconnect_websocket()
        print("[LIVE LOOP] Stopped.")

    async def _run_loop(self):
        while self.is_running:
            # Check if Ghost Mode is active (cease execution of live checks if active)
            if ghost_mode.is_ghost_mode_active():
                print("[LIVE LOOP] Scan loop suspended: Ghost Mode is ACTIVE.")
                await asyncio.sleep(60)
                continue

            start_time = time.perf_counter()
            timestamp = datetime.datetime.now()
            
            # Enforce market session awareness (NSE: 09:15 to 15:30 IST)
            # In MOCK_MODE, we print a warning if outside market hours, but let it proceed for demo purposes
            if not is_market_session_active(timestamp):
                print(f"[LIVE LOOP] Warning: Current time {timestamp.strftime('%H:%M:%S')} is outside normal market hours. Proceeding in MOCK mode.")

            print(f"\n[LIVE LOOP] Starting 60-second market scan cycle at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}...")
            
            # 1. Determine active watchlist (exclude symbols REJECTed by pre-market ARC review)
            active_watchlist = []
            for sym in self.all_symbols:
                arc_dec = self.orchestrator.watchlist_decisions.get(sym, "APPROVE")
                if arc_dec != "REJECT":
                    active_watchlist.append(sym)
                    
            print(f"[LIVE LOOP] Active Watchlist: {len(active_watchlist)} / {len(self.all_symbols)} symbols (excluded REJECTed constituents).")

            # 2. Ingest ticks for all active watchlist symbols
            upstox = ServiceRegistry.get("upstox")
            for symbol in active_watchlist:
                try:
                    # Fetch mock tick
                    tick = upstox.get_live_data(symbol)
                    
                    # Update tick timestamp to current wall-clock time
                    tick["time"] = timestamp
                    
                    # Ingest tick (saves to raw_ticks, builds candle)
                    self.tick_processor.process_tick(tick)
                    
                    # Feed tick to orchestrator for real-time trend/SMC updates
                    self.orchestrator.process_tick(tick)
                except Exception as e:
                    print(f"[LIVE LOOP] Failed to ingest tick for {symbol}: {e}")

            # 3. Evaluate candidate signals
            signals_found = 0
            for symbol in active_watchlist:
                try:
                    passed = self.orchestrator.evaluate_candidate_signals(symbol, timestamp)
                    if passed:
                        signals_found += 1
                except Exception as e:
                    print(f"[LIVE LOOP] Error evaluating signal for {symbol}: {e}")

            duration_ms = (time.perf_counter() - start_time) * 1000
            print(f"[LIVE LOOP] Completed market scan cycle in {duration_ms:.1f}ms. Generated {signals_found} signals.")
            
            # Sleep for 60 seconds minus processing duration to keep a tight 60s interval
            sleep_sec = max(60.0 - (time.perf_counter() - start_time), 1.0)
            await asyncio.sleep(sleep_sec)
