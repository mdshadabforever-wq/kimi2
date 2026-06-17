import datetime
import time
from decimal import Decimal
import database
from market_structure.bos_detector import BOSDetector, find_swing_points
from market_structure.choch_detector import CHOCHDetector
from market_structure.order_block_detector import OrderBlockDetector
from market_structure.fvg_detector import FVGDetector
from market_structure.structure_validator import StructureValidator
from market_structure.structure_scorer import StructureScorer
from market_structure.direction_mapper import DirectionMapper
from market_structure.structure_persistence import StructurePersistence
from market_structure.recovery_manager import RecoveryManager

class SMCEngine:
    def __init__(self):
        # Key: symbol, Value: dict of { "5m": state_dict, "15m": state_dict }
        self.states = {}

    def warmup_system(self, symbols: list[str]):
        """Warms up the SMC Engine states for a list of symbols from the database."""
        for symbol in symbols:
            self.warmup_symbol(symbol)

    def warmup_symbol(self, symbol: str):
        """Warms up the state of a single symbol for both 5m and 15m timeframes."""
        if symbol not in self.states:
            self.states[symbol] = {
                "5m": self._init_empty_state(),
                "15m": self._init_empty_state()
            }

        for tf in ["5m", "15m"]:
            # Load the last 150 candles from database
            candles = self._load_historical_candles(symbol, tf)
            
            # Check if we have structures in the database
            struct_count = self._get_structure_count_in_db(symbol, tf)
            
            if struct_count > 0:
                # Recover state from database records
                recovered = RecoveryManager.recover_state(symbol, tf, candles)
                self.states[symbol][tf].update(recovered)
                self.states[symbol][tf]["candles"] = candles
                if candles:
                    self.states[symbol][tf]["last_processed_time"] = candles[-1]["time"]
            else:
                # Bootstrap chronologically from historical candles if no DB records exist
                self._bootstrap_from_candles(symbol, tf, candles)

    def _init_empty_state(self) -> dict:
        return {
            "current_trend": "BULLISH",
            "latest_swing_high": None,
            "latest_swing_low": None,
            "active_obs": [],
            "active_fvgs": [],
            "candles": [],
            "last_processed_time": None
        }

    def _load_historical_candles(self, symbol: str, timeframe: str) -> list[dict]:
        query = """
            SELECT time, open, high, low, close, volume, vwap FROM market_data
            WHERE symbol = %s AND timeframe = %s
            ORDER BY time DESC LIMIT 150;
        """
        candles = []
        try:
            rows = database.execute_query(query, (symbol, timeframe), fetch=True)
            for row in rows:
                candles.append({
                    "time": row[0],
                    "open": Decimal(str(row[1])),
                    "high": Decimal(str(row[2])),
                    "low": Decimal(str(row[3])),
                    "close": Decimal(str(row[4])),
                    "volume": int(row[5]),
                    "vwap": Decimal(str(row[6])) if row[6] is not None else Decimal(str(row[4]))
                })
            candles.reverse() # Sort ascending (chronological)
        except Exception as e:
            print(f"[SMC ENGINE] Error loading historical candles for {symbol} {timeframe}: {e}")
        return candles

    def _get_structure_count_in_db(self, symbol: str, timeframe: str) -> int:
        query = """
            SELECT count(*) FROM smc_structures
            WHERE symbol = %s AND timeframe = %s;
        """
        try:
            res = database.execute_query(query, (symbol, timeframe), fetch=True)
            return res[0][0] if res else 0
        except Exception:
            return 0

    def _bootstrap_from_candles(self, symbol: str, timeframe: str, candles: list[dict]):
        """Builds state from scratch chronologically using historical candles and persists structures."""
        state = self._init_empty_state()
        self.states[symbol][timeframe] = state
        
        if not candles:
            return
            
        # Run step-by-step
        for i in range(len(candles)):
            sub_candles = candles[:i+1]
            self._process_candle_internal(symbol, timeframe, sub_candles[-1], sub_candles)

    def process_candle(self, symbol: str, timeframe: str, candle: dict):
        """Processes a single completed candle. Updates in-memory state and persists structures."""
        if symbol not in self.states:
            self.states[symbol] = {
                "5m": self._init_empty_state(),
                "15m": self._init_empty_state()
            }
            
        state = self.states[symbol][timeframe]
        
        # Parse candle prices to Decimal
        formatted_candle = {
            "time": candle["time"],
            "open": Decimal(str(candle["open"])),
            "high": Decimal(str(candle["high"])),
            "low": Decimal(str(candle["low"])),
            "close": Decimal(str(candle["close"])),
            "volume": int(candle.get("volume", 0)),
            "vwap": Decimal(str(candle.get("vwap", candle["close"])))
        }
        
        # Append to candles list
        state["candles"].append(formatted_candle)
        if len(state["candles"]) > 150:
            state["candles"].pop(0)
            
        # Process the candle
        self._process_candle_internal(symbol, timeframe, formatted_candle, state["candles"])
        state["last_processed_time"] = formatted_candle["time"]

    def _process_candle_internal(self, symbol: str, timeframe: str, candle: dict, candle_history: list[dict]):
        state = self.states[symbol][timeframe]
        candle_time = candle["time"]
        close_val = candle["close"]
        high_val = candle["high"]
        low_val = candle["low"]

        # 1. Update/check mitigations for active Order Blocks
        remaining_obs = []
        for ob in state["active_obs"]:
            ob_high = Decimal(str(ob["ob_high"]))
            ob_low = Decimal(str(ob["ob_low"]))
            
            if ob["ob_type"] == "BULLISH":
                # Mitigation (Broken) check: Close below OB low
                if close_val < ob_low:
                    StructurePersistence.update_order_block(
                        ob_id=ob.get("id"),
                        last_tested=ob.get("last_tested"),
                        test_count=ob.get("test_count", 0),
                        held_count=ob.get("held_count", 0),
                        broken=True,
                        broken_at=candle_time
                    )
                else:
                    # Test check: Low penetrates OB zone, but Close holds above ob_low
                    if low_val <= ob_high and close_val >= ob_low:
                        ob["test_count"] = ob.get("test_count", 0) + 1
                        ob["held_count"] = ob.get("held_count", 0) + 1
                        ob["last_tested"] = candle_time
                        StructurePersistence.update_order_block(
                            ob_id=ob.get("id"),
                            last_tested=candle_time,
                            test_count=ob["test_count"],
                            held_count=ob["held_count"],
                            broken=False,
                            broken_at=None
                        )
                    remaining_obs.append(ob)
            else: # BEARISH
                # Mitigation (Broken) check: Close above OB high
                if close_val > ob_high:
                    StructurePersistence.update_order_block(
                        ob_id=ob.get("id"),
                        last_tested=ob.get("last_tested"),
                        test_count=ob.get("test_count", 0),
                        held_count=ob.get("held_count", 0),
                        broken=True,
                        broken_at=candle_time
                    )
                else:
                    # Test check: High penetrates OB zone, but Close holds below ob_high
                    if high_val >= ob_low and close_val <= ob_high:
                        ob["test_count"] = ob.get("test_count", 0) + 1
                        ob["held_count"] = ob.get("held_count", 0) + 1
                        ob["last_tested"] = candle_time
                        StructurePersistence.update_order_block(
                            ob_id=ob.get("id"),
                            last_tested=candle_time,
                            test_count=ob["test_count"],
                            held_count=ob["held_count"],
                            broken=False,
                            broken_at=None
                        )
                    remaining_obs.append(ob)
        state["active_obs"] = remaining_obs

        # 2. Update/check mitigations for active FVGs
        remaining_fvgs = []
        for fvg in state["active_fvgs"]:
            bottom_price = Decimal(str(fvg["bottom_price"]))
            top_price = Decimal(str(fvg["top_price"]))
            
            if fvg["direction"] == "BULLISH":
                # Mitigated when subsequent close trades below FVG bottom (origin)
                if close_val < bottom_price:
                    StructurePersistence.save_structure(
                        time=fvg["time"],
                        symbol=symbol,
                        timeframe=timeframe,
                        structure_type="FVG",
                        direction="BULLISH",
                        top_price=top_price,
                        bottom_price=bottom_price,
                        mitigated=True,
                        mitigated_at=candle_time
                    )
                else:
                    remaining_fvgs.append(fvg)
            else: # BEARISH
                # Mitigated when subsequent close trades above FVG top (origin)
                if close_val > top_price:
                    StructurePersistence.save_structure(
                        time=fvg["time"],
                        symbol=symbol,
                        timeframe=timeframe,
                        structure_type="FVG",
                        direction="BEARISH",
                        top_price=top_price,
                        bottom_price=bottom_price,
                        mitigated=True,
                        mitigated_at=candle_time
                    )
                else:
                    remaining_fvgs.append(fvg)
        state["active_fvgs"] = remaining_fvgs

        # 3. Detect Swing Points (updates latest swing high/low)
        swing_highs, swing_lows = find_swing_points(candle_history)
        if swing_highs:
            state["latest_swing_high"] = Decimal(str(swing_highs[-1]["price"]))
        if swing_lows:
            state["latest_swing_low"] = Decimal(str(swing_lows[-1]["price"]))

        # 4. Check for BOS and CHOCH
        if len(candle_history) >= 5:
            # We check if the current close breaks the latest confirmed swings
            # Note: to prevent duplicate triggers, we only check the current close
            # breaking the previous latest swings
            latest_sh = state["latest_swing_high"]
            latest_sl = state["latest_swing_low"]
            
            if latest_sh is not None and latest_sl is not None:
                current_trend = state["current_trend"]
                
                if current_trend == "BULLISH":
                    if close_val < latest_sl:
                        # Reversal -> Bearish CHOCH
                        state["current_trend"] = "BEARISH"
                        StructurePersistence.save_structure(
                            time=candle_time,
                            symbol=symbol,
                            timeframe=timeframe,
                            structure_type="CHOCH",
                            direction="BEARISH",
                            top_price=latest_sl,
                            bottom_price=latest_sl
                        )
                    elif close_val > latest_sh:
                        # Continuation -> Bullish BOS
                        StructurePersistence.save_structure(
                            time=candle_time,
                            symbol=symbol,
                            timeframe=timeframe,
                            structure_type="BOS",
                            direction="BULLISH",
                            top_price=latest_sh,
                            bottom_price=latest_sh
                        )
                elif current_trend == "BEARISH":
                    if close_val > latest_sh:
                        # Reversal -> Bullish CHOCH
                        state["current_trend"] = "BULLISH"
                        StructurePersistence.save_structure(
                            time=candle_time,
                            symbol=symbol,
                            timeframe=timeframe,
                            structure_type="CHOCH",
                            direction="BULLISH",
                            top_price=latest_sh,
                            bottom_price=latest_sh
                        )
                    elif close_val < latest_sl:
                        # Continuation -> Bearish BOS
                        StructurePersistence.save_structure(
                            time=candle_time,
                            symbol=symbol,
                            timeframe=timeframe,
                            structure_type="BOS",
                            direction="BEARISH",
                            top_price=latest_sl,
                            bottom_price=latest_sl
                        )

        # 5. Detect and save new Order Blocks
        new_obs = OrderBlockDetector.detect_order_blocks(candle_history)
        if new_obs:
            latest_ob = new_obs[-1]
            # Verify if this OB is new to active OBs (based on detection time)
            if not any(ob["time"] == latest_ob["time"] for ob in state["active_obs"]):
                # Save to DB
                StructurePersistence.save_order_block(
                    symbol=symbol,
                    timeframe=timeframe,
                    ob_type=latest_ob["ob_type"],
                    ob_high=latest_ob["ob_high"],
                    ob_low=latest_ob["ob_low"],
                    ob_midpoint=latest_ob["ob_midpoint"],
                    first_detected=latest_ob["time"]
                )
                # Query DB to get the generated ID
                db_obs = StructurePersistence.load_order_blocks(symbol, timeframe)
                for db_ob in db_obs:
                    if db_ob["first_detected"] == latest_ob["time"]:
                        state["active_obs"].append(db_ob)
                        break

        # 6. Detect and save new FVGs
        new_fvgs = FVGDetector.detect_fvgs(candle_history)
        if new_fvgs:
            latest_fvg = new_fvgs[-1]
            if not any(fvg["time"] == latest_fvg["time"] for fvg in state["active_fvgs"]):
                StructurePersistence.save_structure(
                    time=latest_fvg["time"],
                    symbol=symbol,
                    timeframe=timeframe,
                    structure_type="FVG",
                    direction=latest_fvg["direction"],
                    top_price=latest_fvg["top_price"],
                    bottom_price=latest_fvg["bottom_price"]
                )
                state["active_fvgs"].append(latest_fvg)

    def process_tick(self, tick: dict) -> dict:
        """Processes a validated live market tick.
        Resolves boundary alignment to identify completed 5m and 15m candles
        from the database, runs detections, and returns the latest generated setup.
        """
        start_time = time.perf_counter()
        symbol = tick["symbol"]
        tick_time = tick["time"]

        if symbol not in self.states:
            self.warmup_symbol(symbol)

        for tf in ["5m", "15m"]:
            boundary = self._get_boundary_time(tick_time, tf)
            completed_boundary = self._get_previous_boundary(boundary, tf)
            
            state = self.states[symbol][tf]
            last_p = state.get("last_processed_time")
            
            if last_p is None or completed_boundary > last_p:
                # Query DB for the completed candle
                query = """
                    SELECT open, high, low, close, volume, vwap FROM market_data
                    WHERE symbol = %s AND timeframe = %s AND time = %s;
                """
                row = database.execute_query(query, (symbol, tf, completed_boundary), fetch=True)
                if row:
                    candle = {
                        "time": completed_boundary,
                        "open": row[0][0],
                        "high": row[0][1],
                        "low": row[0][2],
                        "close": row[0][3],
                        "volume": row[0][4],
                        "vwap": row[0][5]
                    }
                    self.process_candle(symbol, tf, candle)

        # Generate setup direction mapping
        setup = self.generate_setup(symbol)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self._record_telemetry(symbol, duration_ms)

        return setup

    def generate_setup(self, symbol: str) -> dict:
        """Evaluates active structures on 5m and 15m timeframes to map direction,
        validate cross-timeframe rules, score the setup quality, and generate entry/SL/targets.
        """
        if symbol not in self.states:
            return self._empty_setup(symbol)

        state_5m = self.states[symbol]["5m"]
        state_15m = self.states[symbol]["15m"]

        # Map list of active structures
        active_5m = self._format_active_structures_for_mapping(symbol, "5m", state_5m)
        active_15m = self._format_active_structures_for_mapping(symbol, "15m", state_15m)

        # 1. Map direction using DirectionMapper
        mapped_direction = DirectionMapper.map_direction(active_5m, active_15m)

        if mapped_direction == "NO_DIRECTION":
            return self._empty_setup(symbol)

        # Determine alignment filter direction ('BULLISH' for LONG, 'BEARISH' for SHORT)
        align_direction = "BULLISH" if mapped_direction == "LONG" else "BEARISH"

        # 2. Validate cross-timeframe rules using StructureValidator
        is_valid, ct_status = StructureValidator.validate_cross_timeframe(active_5m, active_15m, align_direction)

        if not is_valid:
            return self._empty_setup(symbol)

        # 3. Calculate confirmations count and quality score
        valid_5m = [s for s in active_5m if s["direction"] == align_direction]
        valid_15m = [s for s in active_15m if s["direction"] == align_direction]
        confirmations_count = len(valid_5m) + len(valid_15m)
        score = StructureScorer.calculate_quality_score(confirmations_count)

        # 4. Generate entry zone, stop loss, and targets
        # Let's find the latest active zone (OB or FVG) that matches the direction
        all_active_zones = [
            s for s in (state_5m["active_obs"] + state_5m["active_fvgs"] + 
                        state_15m["active_obs"] + state_15m["active_fvgs"])
        ]
        
        # Sort zones by time descending to find the freshest one
        def get_zone_time(z):
            if "first_detected" in z:
                return z["first_detected"]
            return z["time"]

        matching_zones = []
        for z in all_active_zones:
            if "ob_type" in z and z["ob_type"] == align_direction:
                matching_zones.append(z)
            elif "structure_type" in z and z["structure_type"] == "FVG" and z["direction"] == align_direction:
                matching_zones.append(z)

        if not matching_zones:
            return self._empty_setup(symbol)

        latest_zone = max(matching_zones, key=get_zone_time)

        # Extract entry high, low, midpoint
        if "ob_type" in latest_zone:
            entry_low = Decimal(str(latest_zone["ob_low"]))
            entry_high = Decimal(str(latest_zone["ob_high"]))
            midpoint = Decimal(str(latest_zone["ob_midpoint"]))
        else: # FVG
            entry_low = Decimal(str(latest_zone["bottom_price"]))
            entry_high = Decimal(str(latest_zone["top_price"]))
            midpoint = (entry_low + entry_high) / Decimal("2")

        # Get latest swings
        latest_sh = state_15m["latest_swing_high"] or state_5m["latest_swing_high"]
        latest_sl = state_15m["latest_swing_low"] or state_5m["latest_swing_low"]

        # Calculate SL and targets based on LONG or SHORT
        if mapped_direction == "LONG":
            stop_loss = entry_low * Decimal("0.999") # 0.1% buffer below zone low
            
            # Use latest swing high as target
            target_1 = latest_sh if latest_sh is not None else entry_high * Decimal("1.01")
            target_2 = target_1 * Decimal("1.01")
            
            # Ensure target is higher than entry
            if target_1 <= entry_high:
                target_1 = entry_high * Decimal("1.01")
                target_2 = entry_high * Decimal("1.02")
        else: # SHORT
            stop_loss = entry_high * Decimal("1.001") # 0.1% buffer above zone high
            
            # Use latest swing low as target
            target_1 = latest_sl if latest_sl is not None else entry_low * Decimal("0.99")
            target_2 = target_1 * Decimal("0.99")
            
            # Ensure target is lower than entry
            if target_1 >= entry_low:
                target_1 = entry_low * Decimal("0.99")
                target_2 = entry_low * Decimal("0.98")

        return {
            "symbol": symbol,
            "direction": mapped_direction,
            "score": score,
            "cross_timeframe_status": "PASS",
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": stop_loss,
            "target_1": target_1,
            "target_2": target_2,
            "confirmations_count": confirmations_count
        }

    def _empty_setup(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "direction": "NO_DIRECTION",
            "score": 0,
            "cross_timeframe_status": "FAIL",
            "entry_low": Decimal("0"),
            "entry_high": Decimal("0"),
            "stop_loss": Decimal("0"),
            "target_1": Decimal("0"),
            "target_2": Decimal("0"),
            "confirmations_count": 0
        }

    def _format_active_structures_for_mapping(self, symbol: str, timeframe: str, state: dict) -> list[dict]:
        """Converts active OBs and FVGs, and recent BOS and CHOCH to a uniform format for mapping."""
        structures = []
        
        # Add active OBs
        for ob in state["active_obs"]:
            structures.append({
                "structure_type": "OB",
                "direction": ob["ob_type"]
            })
            
        # Add active FVGs
        for fvg in state["active_fvgs"]:
            structures.append({
                "structure_type": "FVG",
                "direction": fvg["direction"]
            })

        # Find the latest BOS and CHOCH events in database to include
        if state["candles"]:
            cutoff_time = state["candles"][0]["time"]
            query = """
                SELECT structure_type, direction FROM smc_structures
                WHERE symbol = %s AND timeframe = %s AND structure_type IN ('BOS', 'CHOCH') AND time >= %s;
            """
            try:
                db_structs = StructurePersistence.load_structures(symbol, timeframe)
                # Filter structures within the time range of our candle window
                for s in db_structs:
                    if s["structure_type"] in ["BOS", "CHOCH"] and s["time"] >= cutoff_time:
                        structures.append({
                            "structure_type": s["structure_type"],
                            "direction": s["direction"]
                        })
            except Exception:
                pass
                
        return structures

    def _get_boundary_time(self, dt: datetime.datetime, timeframe: str) -> datetime.datetime:
        if timeframe == "5m":
            minute = (dt.minute // 5) * 5
            return dt.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "15m":
            minute = (dt.minute // 15) * 15
            return dt.replace(minute=minute, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported SMC timeframe: {timeframe}")

    def _get_previous_boundary(self, boundary_time: datetime.datetime, timeframe: str) -> datetime.datetime:
        from market_analysis.indicator_cache import make_aware
        bt = make_aware(boundary_time)
        if timeframe == "5m":
            return bt - datetime.timedelta(minutes=5)
        elif timeframe == "15m":
            return bt - datetime.timedelta(minutes=15)
        else:
            raise ValueError(f"Unsupported SMC timeframe: {timeframe}")

    def _record_telemetry(self, symbol: str, duration_ms: float):
        query = """
            INSERT INTO latency_metrics (symbol, receive_latency_ms, processing_latency_ms, candle_build_latency_ms, stage)
            VALUES (%s, %s, %s, %s, %s);
        """
        try:
            database.execute_query(query, (symbol, 0, int(duration_ms), 0, "SMC_ANALYSIS"))
        except Exception:
            pass
