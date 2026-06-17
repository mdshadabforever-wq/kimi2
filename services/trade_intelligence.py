import datetime
import json
import math
from decimal import Decimal
from typing import Dict, Any, List, Optional
import database
from services.llm_provider import LLMProvider

# Strategy Version Constant
STRATEGY_VERSION = "IIIS-v4.6"

class TradeIntelligenceEngine:
    # Memory cache to track last database write time for active trades to honor the 5-minute constraint
    _last_write_times: Dict[int, datetime.datetime] = {}

    @classmethod
    def _create_story_section(cls, trade_id: int, section_name: str, timestamp: datetime.datetime, title: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Creates a chronological story section for a trade."""
        try:
            query = """
                INSERT INTO trade_story_sections (trade_id, section_name, timestamp, title, content, metadata)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            meta_json = json.dumps(metadata) if metadata else None
            database.execute_query(query, (trade_id, section_name, timestamp, title, content, meta_json))
        except Exception as e:
            print(f"[TRADE INT] Error creating story section {section_name}: {e}")

    @classmethod
    def on_signal_approved(cls, signal_id: str, timestamp: datetime.datetime, symbol: str, direction: str,
                           score_res: Dict[str, Any], confidence: str, risk_grade: str,
                           entry_low: float, entry_high: float, stop_loss: float,
                           target_1: float, target_2: float, valid_until: datetime.datetime,
                           geie_snapshot: Optional[Dict[str, Any]] = None,
                           arc_snapshot: Optional[Dict[str, Any]] = None,
                           big_money_snapshot: Optional[Dict[str, Any]] = None,
                           regime_snapshot: Optional[Dict[str, Any]] = None,
                           risk_state_snapshot: Optional[Dict[str, Any]] = None):
        """Creates a pending paper trade and logs the signal creation context on approval."""
        try:
            # 1. Insert into paper_trades
            insert_trade_query = """
                INSERT INTO paper_trades (
                    signal_id, strategy_version, symbol, direction, status,
                    entry_low, entry_high, stop_loss, target_1, target_2, valid_until, created_at
                )
                VALUES (%s, %s, %s, %s, 'PENDING', %s, %s, %s, %s, %s, %s, %s)
                RETURNING trade_id;
            """
            res = database.execute_query(insert_trade_query, (
                signal_id, STRATEGY_VERSION, symbol, direction,
                Decimal(str(entry_low)), Decimal(str(entry_high)),
                Decimal(str(stop_loss)), Decimal(str(target_1)), Decimal(str(target_2)),
                valid_until, timestamp
            ), fetch=True)
            
            if not res:
                print(f"[TRADE INT] Failed to insert paper trade for signal {signal_id}")
                return
            
            trade_id = res[0][0]

            # 2. Insert into trade_score_breakdown (Mandatory)
            comp_score = Decimal(str(score_res.get("final_composite_score", score_res.get("composite_score", 0))))
            insert_score_query = """
                INSERT INTO trade_score_breakdown (
                    trade_id, regime_score, rs_score, rvol_score, breadth_score,
                    sector_score, trend_score, smc_score, options_score, composite_score
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            database.execute_query(insert_score_query, (
                trade_id,
                Decimal(str(score_res.get("regime_score", 0))),
                Decimal(str(score_res.get("rs_score", 0))),
                Decimal(str(score_res.get("rvol_score", 0))),
                Decimal(str(score_res.get("breadth_score", 0))),
                Decimal(str(score_res.get("sector_score", 0))),
                Decimal(str(score_res.get("trend_score", 0))),
                Decimal(str(score_res.get("smc_score", 0))),
                Decimal(str(score_res.get("options_score", 0))),
                comp_score
            ))

            # 3. Save to trade_decision_memory
            decision_reason = f"Approved signal for {symbol} ({direction}) based on Trend alignment and high Composite Score of {comp_score}."
            insert_decision_query = """
                INSERT INTO trade_decision_memory (
                    trade_id, composite_score, regime_score, rs_score, rvol_score, breadth_score,
                    sector_score, trend_score, smc_score, options_score, decision_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            database.execute_query(insert_decision_query, (
                trade_id, comp_score,
                Decimal(str(score_res.get("regime_score", 0))),
                Decimal(str(score_res.get("rs_score", 0))),
                Decimal(str(score_res.get("rvol_score", 0))),
                Decimal(str(score_res.get("breadth_score", 0))),
                Decimal(str(score_res.get("sector_score", 0))),
                Decimal(str(score_res.get("trend_score", 0))),
                Decimal(str(score_res.get("smc_score", 0))),
                Decimal(str(score_res.get("options_score", 0))),
                decision_reason
            ))

            # 4. Save Signal Creation Snapshot
            cls._save_snapshot(trade_id, "Signal Creation", geie_snapshot, arc_snapshot,
                               big_money_snapshot, regime_snapshot, risk_state_snapshot)

            # 5. Create Chronological Story Section: Why Generated
            regime_name = regime_snapshot.get("regime", "NEUTRAL") if regime_snapshot else "NEUTRAL"
            geie_sent = geie_snapshot.get("market_sentiment", "NEUTRAL") if geie_snapshot else "NEUTRAL"
            arc_dec = arc_snapshot.get("arc_decision", "APPROVE") if arc_snapshot else "APPROVE"
            bm_conclusion = big_money_snapshot.get("conclusion", "N/A") if big_money_snapshot else "N/A"
            
            why_content = f"""**Market Regime:** {regime_name}
**GEIE Sentiment:** {geie_sent}
**ARC Decision:** {arc_dec}
**Big Money Flow:** {bm_conclusion}
**Composite Score:** {comp_score:.1f}/100"""
            
            cls._create_story_section(
                trade_id=trade_id,
                section_name="Why Generated",
                timestamp=timestamp,
                title="Why Trade Was Generated",
                content=why_content,
                metadata={
                    "regime": regime_name,
                    "geie_sentiment": geie_sent,
                    "arc_decision": arc_dec,
                    "big_money": bm_conclusion,
                    "composite_score": float(comp_score)
                }
            )

            # 6. Create Chronological Story Section: Signal Alert
            alert_content = f"""**Signal Generated:** {timestamp.strftime('%I:%M %p')}
**Direction:** {direction}
**Entry Zone:** {entry_low:.2f} - {entry_high:.2f}
**Stop Loss:** {stop_loss:.2f}
**Target 1:** {target_1:.2f}
**Target 2:** {target_2:.2f}
**Risk Grade:** {risk_grade} | **Confidence:** {confidence}"""

            cls._create_story_section(
                trade_id=trade_id,
                section_name="Signal Alert",
                timestamp=timestamp,
                title="Signal Alert Triggered",
                content=alert_content,
                metadata={
                    "entry_low": float(entry_low),
                    "entry_high": float(entry_high),
                    "stop_loss": float(stop_loss),
                    "target_1": float(target_1),
                    "target_2": float(target_2),
                    "confidence": confidence,
                    "risk_grade": risk_grade
                }
            )

            # 7. Log SIGNAL_CREATED event
            cls.log_event(
                trade_id=trade_id,
                timestamp=timestamp,
                event_type="SIGNAL_CREATED",
                title="Signal Approved & Trade Created",
                description=f"IIIS approved {direction} signal on {symbol} with composite score {comp_score:.1f} and risk grade {risk_grade}.",
                metadata={
                    "entry_zone": f"{entry_low:.2f} - {entry_high:.2f}",
                    "stop_loss": stop_loss,
                    "target_1": target_1,
                    "target_2": target_2,
                    "confidence": confidence,
                    "risk_grade": risk_grade
                }
            )
            print(f"[TRADE INT] Auto-created pending paper trade ID {trade_id} for symbol {symbol}")
            
        except Exception as e:
            print(f"[TRADE INT] Error on_signal_approved: {e}")

    @classmethod
    def process_tick(cls, tick: Dict[str, Any]):
        """Evaluates ticks against pending and active paper trades."""
        symbol = tick["symbol"]
        price = Decimal(str(tick["price"]))
        timestamp = tick["time"]
        volume = tick.get("volume", 0)

        # 1. Evaluate PENDING trades for this symbol
        cls._evaluate_pending_trades(symbol, price, timestamp, volume)

        # 2. Evaluate ACTIVE trades for this symbol
        cls._evaluate_active_trades(symbol, price, timestamp, volume)

    @classmethod
    def _evaluate_pending_trades(cls, symbol: str, price: Decimal, timestamp: datetime.datetime, volume: int):
        query = """
            SELECT trade_id, direction, entry_low, entry_high, stop_loss, target_1, target_2, valid_until
            FROM paper_trades
            WHERE symbol = %s AND status = 'PENDING';
        """
        rows = database.execute_query(query, (symbol,), fetch=True)
        if not rows:
            return

        for row in rows:
            trade_id, direction, entry_low, entry_high, stop_loss, target_1, target_2, valid_until = row
            
            # Check entry zone trigger: entry_low <= price <= entry_high
            if entry_low <= price <= entry_high:
                # Transition status to ACTIVE
                update_query = """
                    UPDATE paper_trades
                    SET status = 'ACTIVE', entry_price = %s, entry_time = %s, entry_volume = %s,
                        mfe = %s, mae = %s, max_profit_pct = 0.0, max_drawdown_pct = 0.0
                    WHERE trade_id = %s;
                """
                database.execute_query(update_query, (price, timestamp, volume, price, price, trade_id))
                
                # Fetch snapshots/current system states for entry snapshot
                geie = cls._get_latest_geie_event()
                arc = cls._get_latest_arc_decision(symbol)
                regime = cls._get_latest_regime()
                
                # Save entry snapshot
                cls._save_snapshot(trade_id, "Entry", geie, arc, None, regime, None)

                # Store initial trade_market_context
                regime_name = regime.get("regime", "NEUTRAL") if regime else "NEUTRAL"
                regime_score = regime.get("regime_score", 50.0) if regime else 50.0
                nifty_price = regime.get("nifty_price", 23000.0) if regime else 23000.0
                geie_sent = geie.get("market_sentiment", "NEUTRAL") if geie else "NEUTRAL"
                arc_dec = arc.get("arc_decision", "APPROVE") if arc else "APPROVE"
                bm_trend = "BUYER"
                opt_bias = "BULLISH"
                
                # Retrieve scores from breakdown if available
                score_rows = database.execute_query("SELECT sector_score, rs_score FROM trade_score_breakdown WHERE trade_id = %s;", (trade_id,), fetch=True)
                sector_score = score_rows[0][0] if score_rows else Decimal("50.0")
                rs_score = score_rows[0][1] if score_rows else Decimal("50.0")

                insert_context = """
                    INSERT INTO trade_market_context (
                        trade_id, regime_name, regime_score, nifty_price, geie_sentiment,
                        arc_decision, big_money_trend, options_bias, sector_strength_score, relative_strength_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                database.execute_query(insert_context, (
                    trade_id, regime_name, Decimal(str(regime_score)), Decimal(str(nifty_price)), geie_sent,
                    arc_dec, bm_trend, opt_bias, sector_score, rs_score
                ))

                # Create Chronological Story Section: Entry Triggered
                entry_content = f"""Price entered entry zone at **{price:.2f}**.
Volume at entry: **{volume:,} shares** (approx {volume/5000:.1f}x average tick volume)."""
                cls._create_story_section(
                    trade_id=trade_id,
                    section_name="Entry Triggered",
                    timestamp=timestamp,
                    title="Entry Position Triggered",
                    content=entry_content,
                    metadata={"entry_price": float(price), "entry_volume": int(volume)}
                )

                # Log ENTRY_TRIGGERED event
                cls.log_event(
                    trade_id=trade_id,
                    timestamp=timestamp,
                    event_type="ENTRY_TRIGGERED",
                    title="Entry Position Triggered",
                    description=f"Market price {price:.2f} entered the entry zone. Trade is now active.",
                    metadata={"entry_price": float(price), "entry_volume": volume}
                )
                cls._last_write_times[trade_id] = timestamp
                print(f"[TRADE INT] Trade ID {trade_id} ({symbol}) activated at entry price {price:.2f}")

    @classmethod
    def _evaluate_active_trades(cls, symbol: str, price: Decimal, timestamp: datetime.datetime, volume: int):
        query = """
            SELECT trade_id, direction, entry_price, stop_loss, target_1, target_2, valid_until,
                   mfe, mae, max_profit_pct, max_drawdown_pct, entry_time
            FROM paper_trades
            WHERE symbol = %s AND status = 'ACTIVE';
        """
        rows = database.execute_query(query, (symbol,), fetch=True)
        if not rows:
            return

        for row in rows:
            trade_id, direction, entry_price, stop_loss, target_1, target_2, valid_until, mfe, mae, max_profit_pct, max_drawdown_pct, entry_time = row
            
            # 1. Update running stats
            is_long = direction == "LONG"
            
            # Profit % & Drawdown % from entry
            if is_long:
                profit_pct = ((price - entry_price) / entry_price) * 100
                drawdown_pct = ((entry_price - price) / entry_price) * 100
            else:
                profit_pct = ((entry_price - price) / entry_price) * 100
                drawdown_pct = ((price - entry_price) / entry_price) * 100

            if drawdown_pct < 0:
                drawdown_pct = Decimal("0.0")
            if profit_pct < 0:
                profit_pct = Decimal("0.0")

            # MFE and MAE updates (as absolute price levels or relative percent - let's store absolute price levels)
            new_mfe = mfe
            new_mae = mae
            if is_long:
                if price > mfe:
                    new_mfe = price
                if price < mae:
                    new_mae = price
            else:
                if price < mfe:
                    new_mfe = price
                if price > mae:
                    new_mae = price

            new_max_profit = max(max_profit_pct, profit_pct)
            new_max_drawdown = max(max_drawdown_pct, drawdown_pct)
            
            holding_mins = int((timestamp.replace(tzinfo=None) - entry_time.replace(tzinfo=None)).total_seconds() / 60)

            # Check Exit Conditions
            is_exit = False
            exit_reason = None
            exit_price = price
            outcome_class = "TIME_EXIT"

            # Check SL
            if is_long:
                if price <= stop_loss:
                    is_exit = True
                    exit_reason = "HIT_SL"
                    exit_price = stop_loss
                    outcome_class = "LOSS"
            else:
                if price >= stop_loss:
                    is_exit = True
                    exit_reason = "HIT_SL"
                    exit_price = stop_loss
                    outcome_class = "LOSS"

            # Check Target 2 (takes precedence over Target 1 if both hit in same timeframe)
            if not is_exit:
                if is_long:
                    if price >= target_2:
                        is_exit = True
                        exit_reason = "HIT_T2"
                        exit_price = target_2
                        outcome_class = "WIN"
                else:
                    if price <= target_2:
                        is_exit = True
                        exit_reason = "HIT_T2"
                        exit_price = target_2
                        outcome_class = "WIN"

            # Check Target 1
            if not is_exit:
                if is_long:
                    if price >= target_1:
                        is_exit = True
                        exit_reason = "HIT_T1"
                        exit_price = target_1
                        outcome_class = "PARTIAL_WIN"
                else:
                    if price <= target_1:
                        is_exit = True
                        exit_reason = "HIT_T1"
                        exit_price = target_1
                        outcome_class = "PARTIAL_WIN"

            # Check Expiry
            if not is_exit and timestamp.replace(tzinfo=None) >= valid_until.replace(tzinfo=None):
                is_exit = True
                exit_reason = "EXPIRED"
                exit_price = price
                # If expired with profit, call it partial win or breakeven
                if profit_pct > Decimal("0.5"):
                    outcome_class = "PARTIAL_WIN"
                elif profit_pct < Decimal("-0.5"):
                    outcome_class = "LOSS"
                else:
                    outcome_class = "BREAKEVEN"

            # Capture News events matches and attach to trade timeline
            cls._capture_news_for_trade(trade_id, symbol, timestamp)

            if is_exit:
                # Calculate final stats
                final_duration = max(1, int((timestamp.replace(tzinfo=None) - entry_time.replace(tzinfo=None)).total_seconds() / 60))
                
                # Final R-Multiple
                # Long: (exit - entry) / (entry - stop)
                # Short: (entry - exit) / (stop - entry)
                denom = entry_price - stop_loss if is_long else stop_loss - entry_price
                if denom != 0:
                    r_multiple = (exit_price - entry_price) / denom if is_long else (entry_price - exit_price) / denom
                else:
                    r_multiple = Decimal("0.00")
                r_multiple = round(r_multiple, 2)

                # Update DB to close the trade
                update_exit_query = """
                    UPDATE paper_trades
                    SET status = %s, outcome_classification = %s,
                        exit_price = %s, exit_time = %s, holding_minutes = %s, final_r_multiple = %s,
                        mfe = %s, mae = %s, max_profit_pct = %s, max_drawdown_pct = %s
                    WHERE trade_id = %s;
                """
                database.execute_query(update_exit_query, (
                    exit_reason, outcome_class, exit_price, timestamp, final_duration, r_multiple,
                    new_mfe, new_mae, new_max_profit, new_max_drawdown, trade_id
                ))

                # Save Exit Snapshot
                geie = cls._get_latest_geie_event()
                arc = cls._get_latest_arc_decision(symbol)
                regime = cls._get_latest_regime()
                cls._save_snapshot(trade_id, "Exit", geie, arc, None, regime, None)

                # Fetch candle stats (Mandatory)
                candle_metadata = cls._calculate_candle_analytics(symbol, entry_time, timestamp)

                # Store into trade_candle_statistics table
                insert_candles_query = """
                    INSERT INTO trade_candle_statistics (
                        trade_id, total_candles, green_candles, red_candles,
                        largest_favorable, largest_adverse, average_range,
                        highest_volume, lowest_volume
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_id) DO NOTHING;
                """
                database.execute_query(insert_candles_query, (
                    trade_id,
                    candle_metadata.get("total_candles", 0),
                    candle_metadata.get("green_candles", 0),
                    candle_metadata.get("red_candles", 0),
                    Decimal(str(candle_metadata.get("largest_favorable_candle", 0.0))),
                    Decimal(str(candle_metadata.get("largest_adverse_candle", 0.0))),
                    Decimal(str(candle_metadata.get("average_candle_range", 0.0))),
                    candle_metadata.get("highest_volume_candle", 0),
                    candle_metadata.get("lowest_volume_candle", 0)
                ))

                # Create Chronological Story Section: Trade Closed
                exit_content = f"""Trade closed at **{exit_price:.2f}** due to **{exit_reason}**.
Classification: **{outcome_class}**
Final Return: **{r_multiple:+.2f}R**
Duration: **{final_duration} minutes**
Total candles formed: **{candle_metadata.get('total_candles', 0)}** (Green: {candle_metadata.get('green_candles', 0)}, Red: {candle_metadata.get('red_candles', 0)})"""
                
                cls._create_story_section(
                    trade_id=trade_id,
                    section_name="Trade Closed",
                    timestamp=timestamp,
                    title=f"Trade Closed: {exit_reason}",
                    content=exit_content,
                    metadata={
                        "exit_price": float(exit_price),
                        "exit_reason": exit_reason,
                        "outcome": outcome_class,
                        "r_multiple": float(r_multiple),
                        "duration_mins": final_duration
                    }
                )

                # Log exit events
                event_type_map = {
                    "HIT_SL": "STOPLOSS_HIT",
                    "HIT_T1": "TARGET_1_HIT",
                    "HIT_T2": "TARGET_2_HIT",
                    "EXPIRED": "EXPIRED"
                }
                cls.log_event(
                    trade_id=trade_id,
                    timestamp=timestamp,
                    event_type=event_type_map.get(exit_reason, "TRADE_CLOSED"),
                    title=f"Position Closed: {exit_reason}",
                    description=f"Trade closed at price {exit_price:.2f} due to {exit_reason}. Classification: {outcome_class}.",
                    metadata={
                        "exit_price": float(exit_price),
                        "duration_mins": final_duration,
                        "r_multiple": float(r_multiple),
                        "candle_analytics": candle_metadata
                    }
                )

                # Log final TRADE_CLOSED event with candle stats
                cls.log_event(
                    trade_id=trade_id,
                    timestamp=timestamp,
                    event_type="TRADE_CLOSED",
                    title="Trade Story Closed",
                    description=f"Institutional record finalized. Total candles during trade: {candle_metadata.get('total_candles')}.",
                    metadata=candle_metadata
                )

                # Generate AI Trade analyst report
                cls.generate_ai_report(trade_id)
                
                # Trigger Memory Engine to update pattern stats, tomorrow intelligence, and graveyard logs
                try:
                    from services.memory_engine import MemoryEngine
                    MemoryEngine.on_trade_completed(trade_id)
                except Exception as e:
                    print(f"[TRADE INT] MemoryEngine hook failed: {e}")
                    
                print(f"[TRADE INT] Closed Trade ID {trade_id} ({symbol}) due to {exit_reason} with outcome {outcome_class}")

            else:
                # 5-minute database updates for active trades
                last_write = cls._last_write_times.get(trade_id, entry_time)
                elapsed_since_write = (timestamp.replace(tzinfo=None) - last_write.replace(tzinfo=None)).total_seconds() / 60.0
                
                if elapsed_since_write >= 5.0:
                    update_active_query = """
                        UPDATE paper_trades
                        SET mfe = %s, mae = %s, max_profit_pct = %s, max_drawdown_pct = %s, holding_minutes = %s
                        WHERE trade_id = %s;
                    """
                    database.execute_query(update_active_query, (
                        new_mfe, new_mae, new_max_profit, new_max_drawdown, holding_mins, trade_id
                    ))
                    cls._last_write_times[trade_id] = timestamp
                    
                    # Log REGIME_CHANGE event if regime changed in DB
                    cls._check_and_log_regime_change(trade_id, timestamp)

    @classmethod
    def _check_and_log_regime_change(cls, trade_id: int, timestamp: datetime.datetime):
        """Checks if the regime has changed since the last logged event and appends to the story."""
        try:
            regime = cls._get_latest_regime()
            if not regime:
                return
            regime_name = regime.get("regime", "NEUTRAL")
            
            # Fetch last logged regime change or signal regime
            check_query = """
                SELECT description FROM trade_events
                WHERE trade_id = %s AND event_type = 'REGIME_CHANGE'
                ORDER BY timestamp DESC LIMIT 1;
            """
            res = database.execute_query(check_query, (trade_id,), fetch=True)
            
            is_new = False
            if not res:
                is_new = True # Log first regime change event
            else:
                last_desc = res[0][0]
                if regime_name not in last_desc:
                    is_new = True

            if is_new:
                cls.log_event(
                    trade_id=trade_id,
                    timestamp=timestamp,
                    event_type="REGIME_CHANGE",
                    title="Market Regime Update",
                    description=f"Market transitioned into regime: {regime_name} (Score: {regime.get('regime_score', 50)})",
                    metadata=regime
                )
        except Exception as e:
            print(f"[TRADE INT] Error checking regime change: {e}")

    @classmethod
    def _capture_news_for_trade(cls, trade_id: int, symbol: str, timestamp: datetime.datetime):
        """Scans for new GEIE events or mock events affecting the trade symbol."""
        try:
            # Query geie_events table for any events since trade start
            # To ensure the timeline has rich news matching, we search geie_events
            query = """
                SELECT event_id, timestamp, event_name, raw_output FROM geie_events
                WHERE timestamp >= (SELECT entry_time FROM paper_trades WHERE trade_id = %s)
                  AND timestamp <= %s;
            """
            rows = database.execute_query(query, (trade_id, timestamp), fetch=True)
            
            for row in rows:
                ev_id, ev_time, ev_name, raw = row
                
                # Check if this event was already linked
                check_query = "SELECT count(*) FROM trade_news WHERE trade_id = %s AND headline = %s;"
                c_res = database.execute_query(check_query, (trade_id, ev_name), fetch=True)
                if c_res[0][0] > 0:
                    continue

                raw_data = raw or {}
                stock_impact = raw_data.get("stock_impacts", {}).get(symbol.upper(), {})
                sentiment = stock_impact.get("direction", "NEUTRAL")
                impact = stock_impact.get("confidence", "MEDIUM")

                # If the symbol is mentioned directly, link it
                if symbol.upper() in raw_data.get("beneficiaries", []) or symbol.upper() in raw_data.get("losers", []) or stock_impact:
                    # Save to trade_news
                    insert_news = """
                        INSERT INTO trade_news (trade_id, timestamp, source, category, headline, sentiment, impact)
                        VALUES (%s, %s, 'GEIE News Monitor', 'Macro/Sector News', %s, %s, %s);
                    """
                    database.execute_query(insert_news, (trade_id, ev_time, ev_name, sentiment, impact))

                    # Create Chronological Story Section: News Impact
                    news_content = f"""GEIE detected catalyst headline: **{ev_name}**
Source: **GEIE News Monitor**
Sentiment: **{sentiment}** | Urgency: **{impact}**"""
                    cls._create_story_section(
                        trade_id=trade_id,
                        section_name="News Impact",
                        timestamp=ev_time,
                        title=f"News Impact: {sentiment} Catalyst",
                        content=news_content,
                        metadata={"headline": ev_name, "sentiment": sentiment, "impact": impact}
                    )

                    # Log event
                    cls.log_event(
                        trade_id=trade_id,
                        timestamp=ev_time,
                        event_type="NEWS_DETECTED",
                        title="News Event Detected",
                        description=f"GEIE detected matching catalyst: {ev_name}",
                        metadata={"sentiment": sentiment, "impact": impact, "source": "GEIE News Monitor"}
                    )
        except Exception as e:
            print(f"[TRADE INT] Error capturing news: {e}")

    @classmethod
    def _calculate_candle_analytics(cls, symbol: str, start_time: datetime.datetime, end_time: datetime.datetime) -> Dict[str, Any]:
        """Queries database market_data (1m timeframe) to calculate exact trade candle statistics."""
        fallback = {
            "total_candles": 0, "green_candles": 0, "red_candles": 0,
            "largest_favorable_candle": 0.0, "largest_adverse_candle": 0.0,
            "average_candle_range": 0.0, "highest_volume_candle": 0, "lowest_volume_candle": 0
        }
        try:
            # Query 1m candles
            query = """
                SELECT open, high, low, close, volume FROM market_data
                WHERE symbol = %s AND timeframe = '1m' AND time >= %s AND time <= %s
                ORDER BY time ASC;
            """
            rows = database.execute_query(query, (symbol, start_time, end_time), fetch=True)
            if not rows:
                # Try 15m timeframe if 1m is missing
                query = """
                    SELECT open, high, low, close, volume FROM market_data
                    WHERE symbol = %s AND timeframe = '15m' AND time >= %s AND time <= %s
                    ORDER BY time ASC;
                """
                rows = database.execute_query(query, (symbol, start_time, end_time), fetch=True)
                if not rows:
                    return fallback

            total = len(rows)
            green = 0
            red = 0
            
            # Fetch direction from paper_trades
            res_pt = database.execute_query("SELECT direction FROM paper_trades WHERE symbol = %s LIMIT 1;", (symbol,), fetch=True)
            is_long = res_pt[0][0] == "LONG" if res_pt else True

            largest_fav = Decimal("-999999.0")
            largest_adv = Decimal("-999999.0")
            sum_range = Decimal("0.0")
            high_vol = 0
            low_vol = 999999999999

            for r in rows:
                op, hi, lo, cl, vol = [Decimal(str(x)) for x in r]
                vol = int(vol)

                # Green/Red
                if cl > op:
                    green += 1
                elif cl < op:
                    red += 1

                # Range
                sum_range += (hi - lo)

                # Volume
                if vol > high_vol:
                    high_vol = vol
                if vol < low_vol:
                    low_vol = vol

                # Favorable/Adverse
                # Green = favorable for LONG, adverse for SHORT
                # Red = adverse for LONG, favorable for SHORT
                if is_long:
                    fav_change = cl - op
                    adv_change = op - cl
                else:
                    fav_change = op - cl
                    adv_change = cl - op

                if fav_change > largest_fav:
                    largest_fav = fav_change
                if adv_change > largest_adv:
                    largest_adv = adv_change

            avg_range = sum_range / Decimal(str(total))
            largest_fav = max(Decimal("0.0"), largest_fav)
            largest_adv = max(Decimal("0.0"), largest_adv)

            return {
                "total_candles": total,
                "green_candles": green,
                "red_candles": red,
                "largest_favorable_candle": float(round(largest_fav, 2)),
                "largest_adverse_candle": float(round(largest_adv, 2)),
                "average_candle_range": float(round(avg_range, 2)),
                "highest_volume_candle": high_vol,
                "lowest_volume_candle": low_vol if low_vol != 999999999999 else 0
            }

        except Exception as e:
            print(f"[TRADE INT] Error calculating candle analytics: {e}")
            return fallback

    @classmethod
    def log_event(cls, trade_id: int, timestamp: datetime.datetime, event_type: str,
                  title: str, description: str, metadata: Optional[Dict[str, Any]] = None):
        """Logs a chronological event linked to the trade."""
        query = """
            INSERT INTO trade_events (trade_id, timestamp, event_type, title, description, metadata)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        meta_json = json.dumps(metadata) if metadata else None
        database.execute_query(query, (trade_id, timestamp, event_type, title, description, meta_json))

    @classmethod
    def _save_snapshot(cls, trade_id: int, snapshot_type: str, geie: Optional[Dict[str, Any]],
                       arc: Optional[Dict[str, Any]], big_money: Optional[Dict[str, Any]],
                       regime: Optional[Dict[str, Any]], risk_state: Optional[Dict[str, Any]]):
        """Saves a JSONB snapshot of all relevant market variables."""
        query = """
            INSERT INTO trade_snapshots (trade_id, snapshot_type, geie, arc, big_money, regime, risk_state)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        database.execute_query(query, (
            trade_id, snapshot_type,
            json.dumps(geie) if geie else None,
            json.dumps(arc) if arc else None,
            json.dumps(big_money) if big_money else None,
            json.dumps(regime) if regime else None,
            json.dumps(risk_state) if risk_state else None
        ))

    @classmethod
    def generate_ai_report(cls, trade_id: int) -> str:
        """Assembles trade timeline and indicators facts and triggers LLM Provider report generation."""
        try:
            # 1. Fetch trade facts
            pt_query = """
                SELECT symbol, direction, status, outcome_classification, entry_price, exit_price,
                       holding_minutes, final_r_multiple, valid_until, entry_low, entry_high,
                       stop_loss, target_1, target_2
                FROM paper_trades WHERE trade_id = %s;
            """
            pt_res = database.execute_query(pt_query, (trade_id,), fetch=True)
            if not pt_res:
                return ""
            row = pt_res[0]
            symbol, direction, status, outcome, entry, exit_p, duration, r_mult, valid_until, entry_l, entry_h, sl, t1, t2 = row

            # Fetch score breakdown
            sb_query = """
                SELECT regime_score, rs_score, rvol_score, breadth_score, sector_score,
                       trend_score, smc_score, options_score, composite_score
                FROM trade_score_breakdown WHERE trade_id = %s;
            """
            sb_res = database.execute_query(sb_query, (trade_id,), fetch=True)
            sb = sb_res[0] if sb_res else [50.0]*9

            # Fetch chronological timeline
            timeline_query = """
                SELECT timestamp, event_type, title, description FROM trade_events
                WHERE trade_id = %s ORDER BY timestamp ASC;
            """
            timeline_res = database.execute_query(timeline_query, (trade_id,), fetch=True)
            timeline_text = []
            for t in timeline_res:
                timeline_text.append(f"- [{t[0].strftime('%Y-%m-%d %H:%M:%S')}] **{t[1]}** | {t[2]} - {t[3]}")

            # Fetch news
            news_query = """
                SELECT timestamp, source, headline, sentiment, impact FROM trade_news
                WHERE trade_id = %s ORDER BY timestamp ASC;
            """
            news_res = database.execute_query(news_query, (trade_id,), fetch=True)
            news_text = []
            for n in news_res:
                news_text.append(f"- [{n[0].strftime('%H:%M:%S')}] {n[2]} (Source: {n[1]}, Sentiment: {n[3]}, Impact: {n[4]})")

            # Fetch snapshots (Premarket ARC + GEIE)
            sn_query = """
                SELECT geie, arc, big_money, regime, risk_state FROM trade_snapshots
                WHERE trade_id = %s AND snapshot_type = 'Signal Creation';
            """
            sn_res = database.execute_query(sn_query, (trade_id,), fetch=True)
            geie_sn, arc_sn, bm_sn, regime_sn, risk_sn = sn_res[0] if sn_res else [None]*5

            # 2. Build prompt context
            context = f"""
TRADE ATTRIBUTES:
Symbol: {symbol}
Direction: {direction}
Outcome: {outcome} (Exit Reason: {status})
Entry Price: {entry} (Zone: {entry_l} - {entry_h})
Exit Price: {exit_p}
Holding Duration: {duration} minutes
Final R-Multiple: {r_mult}
Stop Loss: {sl}
Target 1: {t1}
Target 2: {t2}

SCORE BREAKDOWN:
Regime Score: {sb[0]}
Relative Strength Score: {sb[1]}
Relative Volume Score: {sb[2]}
Market Breadth Score: {sb[3]}
Sector Score: {sb[4]}
Trend Score: {sb[5]}
SMC Score: {sb[6]}
Options Score: {sb[7]}
Composite Score: {sb[8]}

ARC PREMARKET DECISION:
{arc_sn or "APPROVE (Standard)"}

GEIE EVENT CONTEXT:
{geie_sn or "No active events"}

CHRONOLOGICAL EVENT TIMELINE:
{chr(10).join(timeline_text)}

NEWS EVENTS REGISTERED:
{chr(10).join(news_text) if news_text else "None"}
"""

            system_context = """
You are the IIIS Post-Trade AI Analyst.
Analyze the trade parameters, timeline events, and score breakdowns to formulate a grounded, factual post-trade report.
Strictly avoid hallucinations or inventing data. Limit explanations only to the database facts provided in the prompt.
You MUST format your output with these exact markdown headers:

## Trade Summary
Describe the symbol, direction, score, and grade.

## Why Trade Was Taken
Explain the options, SMC structures, pre-market ARC status, GEIE sentiment, and score breakdowns.

## What Happened During Trade
Trace price progression, regime updates, news events, and volatility.

## Exit Analysis
Explain the stop loss hit, target hit, or expiry transition.

## Lessons Learned
Explain trade strengths, weaknesses, and optimization notes based on the timeline.
"""

            prompt = f"Analyze the following trade context and write the post-trade report:\n\n{context}"
            
            # Generate LLM response
            markdown_report = LLMProvider.generate_response(prompt, provider="gemini", system_context=system_context)
            
            # Form json report payload
            json_report = {
                "trade_id": trade_id,
                "symbol": symbol,
                "direction": direction,
                "composite_score": float(sb[8]),
                "holding_duration_mins": duration,
                "final_r_multiple": float(r_mult),
                "outcome": outcome,
                "timeline_events_count": len(timeline_text),
                "news_count": len(news_text)
            }

            # Split markdown to extract postmortem headers
            import re
            why_worked = "See report details."
            what_supported = "See report details."
            risks_existed = "See report details."
            lessons_learned = "See report details."

            headers = re.split(r'^##\s+', markdown_report, flags=re.MULTILINE)
            for h in headers:
                lines = h.strip().split('\n')
                if not lines:
                    continue
                title_line = lines[0].strip().lower()
                body = '\n'.join(lines[1:]).strip()
                if 'taken' in title_line or 'why' in title_line:
                    why_worked = body
                elif 'happened' in title_line or 'during' in title_line:
                    what_supported = body
                elif 'exit' in title_line:
                    risks_existed = body
                elif 'lessons' in title_line:
                    lessons_learned = body

            # Save to trade_postmortem
            insert_postmortem = """
                INSERT INTO trade_postmortem (trade_id, why_worked, what_supported, risks_existed, lessons_learned, markdown_report, json_report)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_id)
                DO UPDATE SET
                    why_worked = EXCLUDED.why_worked,
                    what_supported = EXCLUDED.what_supported,
                    risks_existed = EXCLUDED.risks_existed,
                    lessons_learned = EXCLUDED.lessons_learned,
                    markdown_report = EXCLUDED.markdown_report,
                    json_report = EXCLUDED.json_report;
            """
            database.execute_query(insert_postmortem, (
                trade_id, why_worked, what_supported, risks_existed, lessons_learned,
                markdown_report, json.dumps(json_report)
            ))

            # Create Chronological Story Section: AI Post Trade Review
            cls._create_story_section(
                trade_id=trade_id,
                section_name="AI Post Trade Review",
                timestamp=datetime.datetime.now(),
                title="AI Post-Trade Review",
                content=markdown_report,
                metadata=json_report
            )

            # Save to trade_analysis (backward compatibility)
            insert_report = """
                INSERT INTO trade_analysis (trade_id, markdown_report, json_report)
                VALUES (%s, %s, %s)
                ON CONFLICT (trade_id)
                DO UPDATE SET
                    markdown_report = EXCLUDED.markdown_report,
                    json_report = EXCLUDED.json_report,
                    generated_at = NOW();
            """
            database.execute_query(insert_report, (trade_id, markdown_report, json.dumps(json_report)))
            return markdown_report

        except Exception as e:
            print(f"[TRADE INT] Error generating AI report: {e}")
            return ""

    # Helper methods to grab current system state variables
    @staticmethod
    def _get_latest_geie_event() -> Optional[Dict[str, Any]]:
        try:
            res = database.execute_query(
                "SELECT raw_output FROM geie_events ORDER BY timestamp DESC LIMIT 1;", fetch=True
            )
            return res[0][0] if res else None
        except Exception:
            return None

    @staticmethod
    def _get_latest_arc_decision(symbol: str) -> Optional[Dict[str, Any]]:
        try:
            # Query recent pre-market reviews
            res = database.execute_query(
                "SELECT metadata FROM audit_log WHERE action = 'PREMARKET_REVIEW' AND metadata->>'symbol' = %s ORDER BY timestamp DESC LIMIT 1;",
                (symbol,), fetch=True
            )
            return res[0][0] if res else {"symbol": symbol, "arc_decision": "APPROVE"}
        except Exception:
            return None

    @staticmethod
    def _get_latest_regime() -> Optional[Dict[str, Any]]:
        try:
            res = database.execute_query(
                "SELECT regime, regime_score, nifty_price, ad_ratio FROM regime_history ORDER BY timestamp DESC LIMIT 1;",
                fetch=True
            )
            if res:
                r, s, n, a = res[0]
                return {"regime": r, "regime_score": float(s), "nifty_price": float(n), "ad_ratio": float(a)}
        except Exception:
            pass
        return {"regime": "NEUTRAL", "regime_score": 50.0}
