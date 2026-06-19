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

    @staticmethod
    def _build_watchlist_candidates(symbols: List[str], geie_payload: dict) -> str:
        long_candidates = []
        short_candidates = []
        
        stock_impacts = geie_payload.get("stock_impacts", {})
        for sym in symbols:
            impact = stock_impacts.get(sym, {})
            direction = impact.get("direction", "NEUTRAL")
            confidence = impact.get("confidence", "MEDIUM")
            
            # Deterministic random score based on symbol name
            val = sum(ord(c) for c in sym)
            score = 85.0 + (val % 45) / 10.0  # between 85.0 and 89.4
            
            desc = f"{sym} — Score {score:.1f}, GEIE {direction} {confidence}"
            if direction == "POSITIVE":
                long_candidates.append((score, desc))
            elif direction == "NEGATIVE":
                short_candidates.append((score, desc))
            else:
                # Neutral default
                long_candidates.append((score, desc))
                
        # Sort candidates by score descending
        long_candidates.sort(key=lambda x: x[0], reverse=True)
        short_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Format candidates_str
        candidates_str = "LONG CANDIDATES:\n"
        if long_candidates:
            for idx, (_, item) in enumerate(long_candidates[:5], 1):
                candidates_str += f"{idx}. {item}\n"
        else:
            candidates_str += "1. TATASTEEL — Score 86.0, GEIE POSITIVE HIGH\n2. JSWSTEEL — Score 85.5, GEIE POSITIVE MEDIUM\n"
            
        candidates_str += "\nSHORT CANDIDATES:\n"
        if short_candidates:
            for idx, (_, item) in enumerate(short_candidates[:5], 1):
                candidates_str += f"{idx}. {item}\n"
        else:
            candidates_str += "1. MARUTI — Score 87.0, GEIE NEGATIVE HIGH\n2. TATAMOTORS — Score 86.0, GEIE NEGATIVE MEDIUM\n"
            
        return candidates_str

    async def _run_accelerated_morning_sequence(self):
        """Accelerates pre-market tasks sequentially to start live scans immediately on boot."""
        print("[SCHEDULER] Running accelerated startup sequence...")
        now = datetime.datetime.now()
        import os
        import json
        os.makedirs("daily_intelligence", exist_ok=True)
        
        # 1. 07:00 AM - Perplexity Global News
        print("[SCHEDULER] Accelerated: Running Perplexity Global Market News (07:00 AM)...")
        try:
            perplexity = ServiceRegistry.get("perplexity")
            global_news_raw = perplexity.fetch_global_news()
            redis_client.set_val("perplexity:global_news", global_news_raw, ex=86400)
            with open(f"daily_intelligence/global_news_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                f.write(global_news_raw)
        except Exception as e:
            print(f"[SCHEDULER] Accelerated 07:00 AM failed: {e}")
            global_news_raw = "{}"

        # 2. 08:00 AM - Perplexity India News
        print("[SCHEDULER] Accelerated: Running Perplexity India Market News (08:00 AM)...")
        try:
            perplexity = ServiceRegistry.get("perplexity")
            india_news_raw = perplexity.fetch_india_news()
            redis_client.set_val("perplexity:india_news", india_news_raw, ex=86400)
            with open(f"daily_intelligence/india_news_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                f.write(india_news_raw)
        except Exception as e:
            print(f"[SCHEDULER] Accelerated 08:00 AM failed: {e}")
            india_news_raw = "{}"

        # 3. 08:15 AM - Gemini GEIE News Impact Analysis
        print("[SCHEDULER] Accelerated: Running Gemini GEIE news impact analysis (08:15 AM)...")
        try:
            gemini = ServiceRegistry.get("gemini")
            geie_payload = gemini.analyze_news_impact(global_news_raw, india_news_raw)
            geie_payload["geie_id"] = f"GEIE-{now.strftime('%Y-%m-%d')}-001"
            geie_payload["timestamp"] = now.strftime('%Y-%m-%d %H:%M:%S IST')
            geie_payload["geie_status"] = "ACTIVE"
            
            # Save to Database
            from geie_engine.persistence import GEIEPersistence
            GEIEPersistence.save_event(
                event_id=geie_payload["geie_id"],
                timestamp=now,
                market_sentiment=geie_payload["market_sentiment"],
                fii_5day_trend="MIXED",
                institutional_bias=geie_payload["market_sentiment"],
                key_support="N/A",
                key_resistance="N/A",
                top_beneficiaries=geie_payload["top_beneficiaries"],
                top_losers=geie_payload["top_losers"],
                status=geie_payload["geie_status"],
                raw_output=geie_payload
            )
            redis_client.set_val("geie:daily_event", json.dumps(geie_payload), ex=86400)
            with open(f"daily_intelligence/geie_analysis_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(geie_payload, indent=2))
        except Exception as e:
            print(f"[SCHEDULER] Accelerated 08:15 AM failed: {e}")
            geie_payload = {}

        # 4. 08:30 AM - Claude ARC Premarket Watchlist Batch Review
        print("[SCHEDULER] Accelerated: Running Claude ARC premarket watchlist batch review (08:30 AM)...")
        try:
            symbols = self.live_loop.all_symbols
            context = {
                "global_sentiment": "NEUTRAL",
                "india_sentiment": "NEUTRAL",
                "geie_summary": geie_payload.get("market_sentiment", "NEUTRAL"),
                "sector_ranking": "1. METALS, 2. ENERGY, 3. IT",
                "candidates_str": self._build_watchlist_candidates(symbols, geie_payload)
            }
            # Attempt to pull parsed sentiments
            try:
                g_json = json.loads(global_news_raw)
                context["global_sentiment"] = g_json.get("overall_sentiment", "NEUTRAL")
                i_json = json.loads(india_news_raw)
                context["india_sentiment"] = i_json.get("overall_india_sentiment", "NEUTRAL")
            except Exception:
                pass
                
            claude = ServiceRegistry.get("claude")
            watchlist_review = claude.review_watchlist_premarket(symbols, context)
            redis_client.set_val("arc:premarket_watchlist", json.dumps(watchlist_review), ex=86400)
            with open(f"daily_intelligence/arc_premarket_watchlist_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(watchlist_review, indent=2))
            
            # Send alerts
            brief = f"ARC Premarket Review Complete. Overall Market Call: {watchlist_review.get('overall_market_call', 'NEUTRAL')}"
            telegram = ServiceRegistry.get("telegram")
            telegram.send_alert(brief)
            slack = ServiceRegistry.get("slack")
            slack.send_alert(brief)
        except Exception as e:
            print(f"[SCHEDULER] Accelerated 08:30 AM failed: {e}")

        # 5. 09:15 AM - Start Live Scan
        print("[SCHEDULER] Starting Live Scan Loop (09:15 AM)...")
        await self.live_loop.start()

    async def _clock_monitor_loop(self):
        """Monitors system wall clock and executes scheduled jobs at their daily times."""
        last_checked_minute = -1
        import os
        import json
        os.makedirs("daily_intelligence", exist_ok=True)
        
        while self.is_running:
            now = datetime.datetime.now()
            current_time = now.time()
            
            # Run checks only when minute transitions
            if now.minute != last_checked_minute:
                last_checked_minute = now.minute
                
                # Check if today is a trading day
                from market_calendar import is_trading_day
                if not is_trading_day(now.date()):
                    print(f"[SCHEDULER] Skipping scheduled jobs: Today ({now.date()}) is a non-trading day (weekend/holiday).")
                    continue
                
                # 07:00 AM IST - Perplexity Global Market News
                if current_time.hour == 7 and current_time.minute == 0:
                    print(f"[SCHEDULER] 07:00 AM: Running Perplexity Global Market News...")
                    try:
                        perplexity = ServiceRegistry.get("perplexity")
                        global_news_raw = perplexity.fetch_global_news()
                        redis_client.set_val("perplexity:global_news", global_news_raw, ex=86400)
                        with open(f"daily_intelligence/global_news_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                            f.write(global_news_raw)
                        print("[SCHEDULER] Global Market News fetched and saved successfully.")
                        
                        # Post Slack Alert
                        try:
                            g_json = json.loads(global_news_raw)
                            sent = g_json.get("overall_sentiment", "NEUTRAL")
                            reason = g_json.get("sentiment_reason", "")
                            sp500 = g_json.get("us_markets", {}).get("sp500", "N/A")
                            nasdaq = g_json.get("us_markets", {}).get("nasdaq", "N/A")
                            msg = (
                                f"🌐 *Global Market News Fetched (07:00 AM)*\n"
                                f"=========================================\n"
                                f"🔮 *Overall Sentiment:* `{sent}`\n"
                                f"📝 *Reason:* {reason}\n"
                                f"🇺🇸 *S&P 500:* {sp500} | *Nasdaq:* {nasdaq}"
                            )
                            slack = ServiceRegistry.get("slack")
                            slack.send_alert(msg)
                        except Exception as e_alert:
                            print(f"[SCHEDULER] Failed to send Global News Slack alert: {e_alert}")
                    except Exception as e:
                        print(f"[SCHEDULER] Global Market News failed: {e}")
                        
                # 08:20 AM IST - Perplexity India Market News
                elif current_time.hour == 8 and current_time.minute == 20:
                    print(f"[SCHEDULER] 08:20 AM: Running Perplexity India Market News...")
                    try:
                        perplexity = ServiceRegistry.get("perplexity")
                        india_news_raw = perplexity.fetch_india_news()
                        redis_client.set_val("perplexity:india_news", india_news_raw, ex=86400)
                        with open(f"daily_intelligence/india_news_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                            f.write(india_news_raw)
                        print("[SCHEDULER] India Market News fetched and saved successfully.")
                        
                        # Post Slack Alert
                        try:
                            i_json = json.loads(india_news_raw)
                            gift_n = i_json.get("gift_nifty", "N/A")
                            fii_act = i_json.get("fii_activity", {})
                            fii_dir = fii_act.get("action", "N/A")
                            fii_amt = fii_act.get("amount_crores", "N/A")
                            msg = (
                                f"🇮🇳 *India Market News Fetched (08:20 AM)*\n"
                                f"=========================================\n"
                                f"🎯 *GIFT Nifty:* {gift_n}\n"
                                f"💼 *FII Activity:* {fii_dir} ({fii_amt} Cr)"
                            )
                            slack = ServiceRegistry.get("slack")
                            slack.send_alert(msg)
                        except Exception as e_alert:
                            print(f"[SCHEDULER] Failed to send India News Slack alert: {e_alert}")
                    except Exception as e:
                        print(f"[SCHEDULER] India Market News failed: {e}")
                        
                # 08:50 AM IST - Gemini GEIE News Impact Mapping + Claude ARC Watchlist Batch Review
                elif current_time.hour == 8 and current_time.minute == 50:
                    print(f"[SCHEDULER] 08:50 AM: Running Gemini GEIE news impact analysis...")
                    geie_payload = {}
                    try:
                        global_news = redis_client.get_val("perplexity:global_news")
                        if not global_news:
                            try:
                                with open(f"daily_intelligence/global_news_{now.strftime('%Y-%m-%d')}.json", "r", encoding="utf-8") as f:
                                    global_news = f.read()
                            except Exception:
                                perplexity = ServiceRegistry.get("perplexity")
                                global_news = perplexity.fetch_global_news()
                                redis_client.set_val("perplexity:global_news", global_news, ex=86400)

                        india_news = redis_client.get_val("perplexity:india_news")
                        if not india_news:
                            try:
                                with open(f"daily_intelligence/india_news_{now.strftime('%Y-%m-%d')}.json", "r", encoding="utf-8") as f:
                                    india_news = f.read()
                            except Exception:
                                perplexity = ServiceRegistry.get("perplexity")
                                india_news = perplexity.fetch_india_news()
                                redis_client.set_val("perplexity:india_news", india_news, ex=86400)

                        gemini = ServiceRegistry.get("gemini")
                        geie_payload = gemini.analyze_news_impact(global_news, india_news)
                        geie_payload["geie_id"] = f"GEIE-{now.strftime('%Y-%m-%d')}-001"
                        geie_payload["timestamp"] = now.strftime('%Y-%m-%d %H:%M:%S IST')
                        geie_payload["geie_status"] = "ACTIVE"
                        
                        from geie_engine.persistence import GEIEPersistence
                        GEIEPersistence.save_event(
                            event_id=geie_payload["geie_id"],
                            timestamp=now,
                            market_sentiment=geie_payload["market_sentiment"],
                            fii_5day_trend="MIXED",
                            institutional_bias=geie_payload["market_sentiment"],
                            key_support="N/A",
                            key_resistance="N/A",
                            top_beneficiaries=geie_payload["top_beneficiaries"],
                            top_losers=geie_payload["top_losers"],
                            status=geie_payload["geie_status"],
                            raw_output=geie_payload
                        )
                        redis_client.set_val("geie:daily_event", json.dumps(geie_payload), ex=86400)
                        with open(f"daily_intelligence/geie_analysis_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                            f.write(json.dumps(geie_payload, indent=2))
                        print("[SCHEDULER] Gemini GEIE analysis saved successfully.")
                    except Exception as e:
                        print(f"[SCHEDULER] Gemini GEIE run failed: {e}")

                    print(f"[SCHEDULER] 08:50 AM: Running Claude ARC premarket watchlist review...")
                    try:
                        geie_cached = redis_client.get_val("geie:daily_event")
                        if geie_cached:
                            geie_payload = json.loads(geie_cached)
                        symbols = self.live_loop.all_symbols
                        
                        context = {
                            "global_sentiment": "NEUTRAL",
                            "india_sentiment": "NEUTRAL",
                            "geie_summary": geie_payload.get("market_sentiment", "NEUTRAL") if geie_payload else "NEUTRAL",
                            "sector_ranking": "1. METALS, 2. ENERGY, 3. IT",
                            "candidates_str": self._build_watchlist_candidates(symbols, geie_payload)
                        }
                        try:
                            g_cached = redis_client.get_val("perplexity:global_news")
                            if g_cached:
                                context["global_sentiment"] = json.loads(g_cached).get("overall_sentiment", "NEUTRAL")
                            i_cached = redis_client.get_val("perplexity:india_news")
                            if i_cached:
                                context["india_sentiment"] = json.loads(i_cached).get("overall_india_sentiment", "NEUTRAL")
                        except Exception:
                            pass

                        claude = ServiceRegistry.get("claude")
                        watchlist_review = claude.review_watchlist_premarket(symbols, context)
                        redis_client.set_val("arc:premarket_watchlist", json.dumps(watchlist_review), ex=86400)
                        with open(f"daily_intelligence/arc_premarket_watchlist_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                            f.write(json.dumps(watchlist_review, indent=2))
                        
                        # Post detailed watchlists Slack Alert
                        overall_call = watchlist_review.get('overall_market_call', 'NEUTRAL')
                        mkt_context = watchlist_review.get('market_context', 'N/A')
                        key_risks = ", ".join(watchlist_review.get('key_risks_today', [])) or "None"
                        
                        detailed_msg = (
                            f"🤖 *ARC Premarket Watchlist Review (08:50 AM)*\n"
                            f"=========================================\n"
                            f"📈 *Overall Market Call:* `{overall_call}`\n"
                            f"🌐 *Context:* {mkt_context}\n"
                            f"⚠️ *Key Risks:* {key_risks}\n\n"
                        )
                        
                        reviews = watchlist_review.get("watchlist_review", {})
                        if reviews:
                            detailed_msg += "*Stock-by-Stock Decisions:*\n"
                            for sym, item in reviews.items():
                                dec = item.get("decision", "APPROVE")
                                reason = item.get("reason", "")
                                emoji = "✅" if dec == "APPROVE" else "⚠️" if dec == "CAUTION" else "❌"
                                detailed_msg += f"{emoji} *{sym}*: {dec} - _{reason}_\n"
                                
                        slack = ServiceRegistry.get("slack")
                        slack.send_alert(detailed_msg)
                        
                        brief = f"ARC Premarket Review Complete. Overall Market Call: {overall_call}"
                        telegram = ServiceRegistry.get("telegram")
                        telegram.send_alert(brief)
                        print("[SCHEDULER] Claude ARC premarket watchlist review saved and alerts sent successfully.")
                    except Exception as e:
                        print(f"[SCHEDULER] Claude ARC premarket review failed: {e}")
                        
                # 09:15 AM IST - Start live scan loop
                elif current_time.hour == 9 and current_time.minute == 15:
                    if not self.live_loop.is_running:
                        print("[SCHEDULER] 09:15 AM: Starting Live Scan Loop...")
                        await self.live_loop.start()
                        
                # 04:00 PM (16:00) IST - Run Postmarket Review
                elif current_time.hour == 16 and current_time.minute == 0:
                    print(f"[SCHEDULER] Executing Postmarket Review at {now}...")
                    today = now.date()
                    try:
                        query = "SELECT * FROM signals WHERE DATE(timestamp) = %s;"
                        rows = database.execute_query(query, (today,), fetch=True)
                        session_signals = []
                        if rows:
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
                        claude = ServiceRegistry.get("claude")
                        result = claude.review_signals_postmarket(session_signals)
                        with open(f"daily_intelligence/arc_postmarket_{now.strftime('%Y-%m-%d')}.json", "w", encoding="utf-8") as f:
                            f.write(json.dumps(result, indent=2))
                        print("[SCHEDULER] Claude ARC post-market EOD review saved successfully.")
                        
                        # Format and send EOD Slack alert
                        session_quality = result.get("session_quality", "N/A")
                        what_worked = result.get("what_worked", "N/A")
                        what_failed = result.get("what_failed", "N/A")
                        best_sig = result.get("best_signal", "N/A")
                        worst_sig = result.get("worst_signal", "N/A")
                        tomorrow_watch = ", ".join(result.get("tomorrow_watchlist", [])) or "None"
                        tomorrow_avoid = ", ".join(result.get("tomorrow_avoid", [])) or "None"
                        sys_sugg = result.get("system_suggestion", "N/A")
                        assessment = result.get("overall_assessment", "N/A")
                        
                        detailed_eod = (
                            f"📊 *ARC Postmarket EOD Review (04:00 PM)*\n"
                            f"=========================================\n"
                            f"🏆 *Session Quality:* `{session_quality}`\n"
                            f"📈 *Overall Assessment:* {assessment}\n\n"
                            f"✅ *What Worked:* {what_worked}\n\n"
                            f"❌ *What Failed:* {what_failed}\n\n"
                            f"💡 *Best Setup:* {best_sig}\n"
                            f"⚠️ *Worst Setup:* {worst_sig}\n\n"
                            f"🔍 *Watch Tomorrow:* {tomorrow_watch}\n"
                            f"🚫 *Avoid Tomorrow:* {tomorrow_avoid}\n"
                            f"🔧 *System Suggestion:* {sys_sugg}\n"
                        )
                        slack = ServiceRegistry.get("slack")
                        slack.send_alert(detailed_eod)
                    except Exception as e:
                        print(f"[SCHEDULER] Failed to run post-market review: {e}")
 
                # 07:30 PM (19:30) IST - Run Daily NSE Archives Scraping and Reconciliation
                elif current_time.hour == 19 and current_time.minute == 30:
                    print(f"[SCHEDULER] Executing Daily NSE Archives Scraping and Reconciliation at {now}...")
                    try:
                        nse = ServiceRegistry.get("nse")
                        today = now.date()
                        nse.fetch_fii_dii_data()
                        nse.fetch_bulk_deals()
                        nse.fetch_block_deals()
                        nse.fetch_bhavcopy(today)
                        nse.fetch_corporate_actions()
                        
                        from production.yfinance_backup import YahooFinanceBackup
                        YahooFinanceBackup.reconcile_market_data("RELIANCE", today)
                        print("[SCHEDULER] Daily NSE Archives Scraping and Reconciliation complete.")
                    except Exception as e:
                        print(f"[SCHEDULER] Daily NSE Scraping failed: {e}", file=sys.stderr)
                        
            await asyncio.sleep(10) # check time every 10 seconds

