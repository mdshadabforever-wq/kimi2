import datetime
import time
import math
import random
from decimal import Decimal
from typing import Dict, Any
from interfaces.upstox import UpstoxInterface
import database

class UpstoxMock(UpstoxInterface):
    def __init__(self):
        self.simulate_error = False
        self.simulate_timeout = False
        self.simulate_websocket_disconnect = False
        self.simulate_data_gap = False
        self.websocket_connected = False
        self.consecutive_failures = 0
        
        # Last received tick time
        self.last_tick_time = datetime.datetime.now()
        
        # Stateful price simulation
        self.states = {}

    def _handle_failures(self):
        if self.simulate_error:
            self.consecutive_failures += 1
            raise Exception("Simulated Upstox API Error")
        if self.simulate_timeout:
            self.consecutive_failures += 1
            raise TimeoutError("Simulated Upstox API Timeout")
        self.consecutive_failures = 0

    def connect_websocket(self):
        self._handle_failures()
        if self.simulate_websocket_disconnect:
            self.websocket_connected = False
            raise ConnectionError("Simulated Upstox WebSocket Connection Failed")
        self.websocket_connected = True
        self.last_tick_time = datetime.datetime.now()
        print("Upstox WebSocket connected.")

    def disconnect_websocket(self):
        self.websocket_connected = False
        print("Upstox WebSocket disconnected.")

    def _detect_caller_time(self) -> datetime.datetime:
        """Inspects call stack frames to detect simulated loop or scan time."""
        import inspect
        frame = inspect.currentframe()
        try:
            while frame:
                for name, val in frame.f_locals.items():
                    if isinstance(val, datetime.datetime):
                        if name in ["current_time", "timestamp", "tick_time", "as_of_time"]:
                            dt = val
                            if dt.tzinfo is not None:
                                dt = dt.replace(tzinfo=None)
                            return dt
                frame = frame.f_back
        except Exception:
            pass
        finally:
            del frame
        
        now = datetime.datetime.now()
        return now

    def _init_symbol_state(self, symbol: str):
        """Initializes state parameters for a symbol to run realistic drift/volatility."""
        from decimal import Decimal
        from scoring_engine.sector_strength import SECTOR_MAP
        
        base_price = None
        try:
            # Try to fetch latest close from DB to align starting price
            query = "SELECT close FROM market_data WHERE symbol = %s ORDER BY time DESC LIMIT 1;"
            res = database.execute_query(query, (symbol,), fetch=True)
            if res and res[0][0] is not None:
                base_price = Decimal(str(res[0][0]))
        except Exception:
            pass
            
        if base_price is None:
            if symbol == "NIFTY 50":
                base_price = Decimal("23000.0")
            elif symbol == "INDIA VIX":
                base_price = Decimal("15.0")
            else:
                base_price = Decimal("150.0")
                
        # Assign sector
        sector = SECTOR_MAP.get(symbol.upper(), "OTHER")
        
        # Distribute trend types to create rotation and divergence
        # Keep RELIANCE, TATASTEEL, INFY, L&T, LT trending UP to guarantee they exceed 86
        strong_bullish = ["RELIANCE", "TATASTEEL", "INFY", "L&T", "LT"]
        if symbol.upper() in strong_bullish:
            trend_type = "TREND_UP"
        elif sector in ["METALS", "INFRASTRUCTURE", "IT", "ENERGY"]:
            trend_type = random.choice(["TREND_UP", "TREND_UP", "RANGE"])
        elif sector in ["FMCG", "TELECOM"]:
            trend_type = random.choice(["TREND_DOWN", "TREND_DOWN", "RANGE"])
        else:
            trend_type = random.choice(["RANGE", "RANGE", "TREND_UP", "TREND_DOWN"])
            
        # Drifts (per minute step)
        sector_drifts = {
            "METALS": 0.0006,
            "INFRASTRUCTURE": 0.0006,
            "IT": 0.0003,
            "ENERGY": 0.0003,
            "BANKING": 0.0,
            "FMCG": -0.0004,
            "TELECOM": -0.0004,
            "OTHER": 0.0001
        }
        sector_drift = sector_drifts.get(sector, 0.0001)
        
        if symbol.upper() in strong_bullish:
            stock_drift = 0.0005
        else:
            stock_drift = random.uniform(-0.0001, 0.0001)
            
        volatility = random.uniform(0.001, 0.003)
        
        self.states[symbol] = {
            "base_price": base_price,
            "current_price": base_price,
            "sector": sector,
            "trend_type": trend_type,
            "sector_drift": sector_drift,
            "stock_drift": stock_drift,
            "volatility": volatility,
            "hve_active": False,
            "hve_ticks_left": 0,
            "prev_tick_time": None,
            # Forming candle boundary state (15m timeframe)
            "candle_boundary": None,
            "candle_open": None,
            "candle_high": None,
            "candle_low": None,
            "candle_volume": 0,
            "candle_vwap": None
        }

    def _write_option_chain_to_db(self, symbol: str, current_price: Decimal, tick_time: datetime.datetime, trend_type: str):
        """Generates dynamic option strikes centered around price and inserts into options_data."""
        cp = float(current_price)
        if symbol == "NIFTY 50":
            interval = 100.0
        else:
            if cp > 1000.0:
                interval = 50.0
            elif cp > 500.0:
                interval = 10.0
            elif cp > 100.0:
                interval = 5.0
            else:
                interval = 1.0
                
        atm = round(cp / interval) * interval
        strikes = [atm + i * interval for i in range(-5, 6)]
        
        pe_weights = [1, 2, 3, 4, 5, 6, 8, 10, 8, 6, 4]
        ce_weights = [1, 2, 3, 4, 5, 6, 8, 10, 8, 6, 4]
        pe_mult = 1.0
        ce_mult = 1.0
        
        if trend_type == "TREND_UP":
            pe_weights = [1, 2, 3, 4, 5, 6, 8, 10, 8, 6, 4]
            ce_weights = [4, 6, 8, 10, 8, 6, 5, 4, 3, 2, 1]
            pe_mult = 1.5
            ce_mult = 1.0
        elif trend_type == "TREND_DOWN":
            ce_weights = [1, 2, 3, 4, 5, 6, 8, 10, 8, 6, 4]
            pe_weights = [4, 6, 8, 10, 8, 6, 5, 4, 3, 2, 1]
            pe_mult = 1.0
            ce_mult = 1.5
        else:
            pe_weights = [2, 4, 6, 8, 10, 12, 10, 8, 6, 4, 2]
            ce_weights = [2, 4, 6, 8, 10, 12, 10, 8, 6, 4, 2]
            pe_mult = 1.0
            ce_mult = 1.0
            
        expiry_date = tick_time.date() + datetime.timedelta(days=7)
        
        placeholders = []
        params = []
        
        for idx, strike in enumerate(strikes):
            dist = (strike - cp) / (cp * 0.02)
            ce_ltp = max(0.05, cp * 0.02 * math.exp(-dist * 0.5))
            pe_ltp = max(0.05, cp * 0.02 * math.exp(dist * 0.5))
            
            ce_oi = int(ce_weights[idx] * 100000 * ce_mult)
            pe_oi = int(pe_weights[idx] * 100000 * pe_mult)
            
            ce_oi_change = int(ce_oi * random.uniform(0.1, 0.3))
            pe_oi_change = int(pe_oi * random.uniform(0.1, 0.3))
            
            ce_vol = int(ce_oi * random.uniform(0.05, 0.15))
            pe_vol = int(pe_oi * random.uniform(0.05, 0.15))
            
            # CE
            placeholders.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            params.extend([
                tick_time, symbol, Decimal(str(strike)), expiry_date, 'CE',
                ce_oi, ce_oi_change, ce_vol, Decimal("0.15"), Decimal(str(round(ce_ltp, 2)))
            ])
            # PE
            placeholders.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            params.extend([
                tick_time, symbol, Decimal(str(strike)), expiry_date, 'PE',
                pe_oi, pe_oi_change, pe_vol, Decimal("0.15"), Decimal(str(round(pe_ltp, 2)))
            ])
            
        query = f"""
            INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp)
            VALUES {", ".join(placeholders)}
            ON CONFLICT (time, symbol, strike, expiry, option_type) 
            DO UPDATE SET
                oi = EXCLUDED.oi,
                oi_change = EXCLUDED.oi_change,
                volume = EXCLUDED.volume,
                iv = EXCLUDED.iv,
                ltp = EXCLUDED.ltp;
        """
        database.execute_query(query, params)

    def get_live_data(self, symbol: str, is_rest: bool = False) -> Dict[str, Any]:
        self._handle_failures()
        
        if not is_rest:
            if not self.websocket_connected or self.simulate_websocket_disconnect:
                raise ConnectionError("Upstox WebSocket is not connected")
        
        # 1. Detect caller time and Naive sanity check
        tick_time = self._detect_caller_time()
        if self.simulate_data_gap:
            tick_time = tick_time - datetime.timedelta(minutes=3)
        self.last_tick_time = tick_time

        # 2. Lazy init
        if symbol not in self.states:
            self._init_symbol_state(symbol)
            
        state = self.states[symbol]
        
        # 3. Calculate elapsed time
        elapsed_minutes = 1.0
        if state["prev_tick_time"] is not None:
            delta = (tick_time - state["prev_tick_time"]).total_seconds() / 60.0
            if delta > 0:
                elapsed_minutes = delta
        state["prev_tick_time"] = tick_time
        
        # 4. Update prices
        from decimal import Decimal
        if symbol == "NIFTY 50":
            total_rel = 0.0
            count = 0
            for s, s_state in self.states.items():
                if s not in ["NIFTY 50", "INDIA VIX"]:
                    total_rel += float(s_state["current_price"]) / float(s_state["base_price"])
                    count += 1
            if count > 0:
                avg_rel = total_rel / count
                state["current_price"] = state["base_price"] * Decimal(str(avg_rel))
            else:
                state["current_price"] = state["base_price"]
        elif symbol == "INDIA VIX":
            state["current_price"] = Decimal("15.0") + Decimal(str(random.uniform(-0.5, 0.5)))
        else:
            # Normal stock
            # Check high volatility news event
            if state["hve_active"]:
                state["hve_ticks_left"] -= 1
                if state["hve_ticks_left"] <= 0:
                    state["hve_active"] = False
            else:
                if random.random() < 0.02:
                    state["hve_active"] = True
                    state["hve_ticks_left"] = random.randint(3, 8)
            
            mu = 0.0
            sigma = float(state["volatility"])
            
            if state["hve_active"]:
                sigma *= 3.0
                shock = random.choice([-0.015, 0.015])
                state["current_price"] *= Decimal(str(1.0 + shock))
                
            if state["trend_type"] == "TREND_UP":
                mu = float(state["sector_drift"]) + float(state["stock_drift"])
            elif state["trend_type"] == "TREND_DOWN":
                mu = float(state["sector_drift"]) - float(state["stock_drift"])
            elif state["trend_type"] == "RANGE":
                dev = (float(state["current_price"]) - float(state["base_price"])) / float(state["base_price"])
                mu = -0.05 * dev
                
            drift_scaled = mu * elapsed_minutes
            vol_scaled = sigma * (elapsed_minutes ** 0.5)
            z = random.normalvariate(0.0, 1.0)
            
            change_pct = drift_scaled + vol_scaled * z
            new_price = float(state["current_price"]) * (1.0 + change_pct)
            if new_price < 1.0:
                new_price = 1.0
            state["current_price"] = Decimal(str(round(new_price, 2)))

        # 5. Simulate volume with volume spikes
        base_vol = random.uniform(10000, 50000) * elapsed_minutes
        price_change_pct = abs(float(state["current_price"]) - float(state["base_price"])) / float(state["base_price"])
        vol_mult = 1.0 + 200.0 * price_change_pct
        if state["hve_active"]:
            vol_mult *= random.uniform(5.0, 12.0)
        volume = int(base_vol * vol_mult)
        if volume < 100:
            volume = 100

        # 6. Update forming 15m candle
        minute_floor = (tick_time.minute // 15) * 15
        boundary_15m = tick_time.replace(minute=minute_floor, second=0, microsecond=0)
        
        if state["candle_boundary"] is None or boundary_15m > state["candle_boundary"]:
            state["candle_boundary"] = boundary_15m
            state["candle_open"] = state["current_price"]
            state["candle_high"] = state["current_price"]
            state["candle_low"] = state["current_price"]
            state["candle_volume"] = volume
            state["candle_vwap"] = state["current_price"]
        else:
            if state["current_price"] > state["candle_high"]:
                state["candle_high"] = state["current_price"]
            if state["current_price"] < state["candle_low"]:
                state["candle_low"] = state["current_price"]
            state["candle_volume"] += volume
            tot_vol = state["candle_volume"]
            if tot_vol > 0:
                state["candle_vwap"] = (state["candle_vwap"] * Decimal(str(tot_vol - volume)) + state["current_price"] * Decimal(str(volume))) / Decimal(str(tot_vol))

        # 7. Write/Update option chain data in DB
        self._write_option_chain_to_db(symbol, state["current_price"], tick_time, state["trend_type"])

        return {
            "time": tick_time,
            "symbol": symbol,
            "open": float(state["candle_open"]),
            "high": float(state["candle_high"]),
            "low": float(state["candle_low"]),
            "close": float(state["current_price"]),
            "price": float(state["current_price"]),
            "volume": int(state["candle_volume"]),
            "vwap": float(state["candle_vwap"]),
            "timeframe": "15m"
        }

    def get_option_chain(self, symbol: str) -> Dict[str, Any]:
        self._handle_failures()
        
        cp = 150.0
        trend_type = "TREND_UP"
        if symbol in self.states:
            cp = float(self.states[symbol]["current_price"])
            trend_type = self.states[symbol]["trend_type"]
            
        if symbol == "NIFTY 50":
            interval = 100.0
        else:
            if cp > 1000.0:
                interval = 50.0
            elif cp > 500.0:
                interval = 10.0
            elif cp > 100.0:
                interval = 5.0
            else:
                interval = 1.0
                
        atm = round(cp / interval) * interval
        
        pcr = 1.45
        if trend_type == "TREND_UP":
            pcr = 1.5
        elif trend_type == "TREND_DOWN":
            pcr = 0.5
        else:
            pcr = 1.0
            
        return {
            "symbol": symbol,
            "pcr": pcr,
            "max_pain": atm,
            "highest_put_oi_strike": atm + 2 * interval,
            "highest_call_oi_strike": atm - 2 * interval,
            "strikes": [
                {"strike": atm, "option_type": "CE", "oi": 500000, "oi_change": 150000, "ltp": round(cp * 0.02, 2)},
                {"strike": atm, "option_type": "PE", "oi": int(500000 * pcr), "oi_change": 300000, "ltp": round(cp * 0.02, 2)}
            ]
        }

    def get_historical_candles(self, symbol: str, timeframe: str, lookback_days: int) -> list:
        self._handle_failures()
        
        cp = 150.0
        if symbol in self.states:
            cp = float(self.states[symbol]["base_price"])
        elif symbol == "NIFTY 50":
            cp = 23000.0
            
        now = datetime.datetime.now()
        candles = []
        for i in range(lookback_days):
            price = cp - (lookback_days - i) * 0.1
            candles.append({
                "time": now - datetime.timedelta(days=i),
                "symbol": symbol,
                "open": price - 0.2,
                "high": price + 0.5,
                "low": price - 0.3,
                "close": price,
                "volume": 1500000,
                "vwap": price,
                "timeframe": timeframe
            })
        return candles

DefinitionClass = UpstoxMock
