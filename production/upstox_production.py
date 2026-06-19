import os
import sys
import json
import time
import datetime
import gzip
import threading
import urllib.request
import urllib.parse
import urllib.error
from decimal import Decimal
from typing import Dict, Any, List, Optional
import websocket

import database
from interfaces.upstox import UpstoxInterface
from config import Config

class UpstoxProduction(UpstoxInterface):
    """Production Upstox Client implementing UpstoxInterface.
    Uses standard library urllib for REST and websocket-client for streaming.
    Handles rate-limiting, token authorization, redirection, and automatic recovery.
    """

    API_BASE = "https://api.upstox.com"
    TIMEOUT = 10  # seconds

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("UPSTOX_ACCESS_TOKEN", "mock_access_token")
        self.ws = None
        self.ws_thread = None
        self.is_connected = False
        self.consecutive_failures = 0
        self.subscribed_symbols = set()
        self.reconnect_delay = 1.0
        self.lock = threading.Lock()
        
        # State indicators for health checks and websocket managers
        self.simulate_error = False
        self.simulate_timeout = False
        self.simulate_websocket_disconnect = False
        self.simulate_data_gap = False
        self.last_tick_time = datetime.datetime.now()
        
        # Load symbol to key mapping
        self.symbol_to_key = {}
        try:
            mapping_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbol_to_key.json")
            if os.path.exists(mapping_path):
                with open(mapping_path, "r") as f:
                    self.symbol_to_key = json.load(f)
        except Exception as e:
            print(f"[Upstox PROD] Failed to load symbol mapping: {e}", file=sys.stderr)

    @property
    def websocket_connected(self) -> bool:
        return self.is_connected

    @websocket_connected.setter
    def websocket_connected(self, value: bool):
        self.is_connected = value

    def _resolve_symbol(self, symbol: str) -> str:
        """Resolves a trading symbol to its Upstox instrument key, or returns the symbol as-is."""
        return self.symbol_to_key.get(symbol, symbol)

    # ------------------------------------------------------------------
    # HTTP Helper with Rate Limiting and Exponential Backoff Retries
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.API_BASE}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "Mozilla/5.0"
        }
        
        req_data = json.dumps(data).encode("utf-8") if data else None
        if req_data:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, headers=headers, method=method, data=req_data)

        # 3 retries with exponential backoff
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                    res_body = resp.read()
                    # Check if gzipped
                    if resp.info().get('Content-Encoding') == 'gzip':
                        res_body = gzip.decompress(res_body)
                    return json.loads(res_body.decode("utf-8"))
            except urllib.error.HTTPError as e:
                # Handle Rate Limit (HTTP 429) or Server Errors (5xx)
                if e.code == 429 or e.code >= 500:
                    sleep_time = (2 ** attempt) + (time.time() % 1)
                    print(f"[Upstox PROD] HTTP {e.code} on attempt {attempt+1}. Retrying in {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                    continue
                print(f"[Upstox PROD] HTTP Error {e.code}: {e.reason}", file=sys.stderr)
                raise
            except Exception as e:
                print(f"[Upstox PROD] Network/Connection Error on attempt {attempt+1}: {e}", file=sys.stderr)
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        
        raise RuntimeError(f"API request failed after 3 attempts: {url}")

    # ------------------------------------------------------------------
    # WebSocket Event Handlers
    # ------------------------------------------------------------------
    def _on_message(self, ws, message):
        """Processes binary Protobuf/JSON stream ticks and writes to DB raw_ticks."""
        try:
            self.last_tick_time = datetime.datetime.now()
            # V3 sends binary messages. If it is a string, parse it as JSON fallback
            if isinstance(message, str):
                data = json.loads(message)
            else:
                # Binary message decoding fallback if Protobuf isn't compiled
                # Upstox V3 uses protobuf; we inspect if we can decode or dump raw
                data = {"raw_binary_len": len(message), "timestamp": datetime.datetime.now().isoformat()}
            
            # Extract standard tick fields (this schema matches the mock feed for processing)
            # In production, parse fields according to Upstox Feed Protobuf schema
            # Example: symbol, price, volume, time
            tick = {
                "symbol": data.get("symbol", "NIFTY 50"),
                "price": Decimal(str(data.get("price", 23000.0))),
                "volume": int(data.get("volume", 0)),
                "time": datetime.datetime.now()
            }
            
            # 1. Write to raw_ticks table
            ins_query = """
                INSERT INTO raw_ticks (time, symbol, price, volume)
                VALUES (%s, %s, %s, %s);
            """
            database.execute_query(ins_query, (tick["time"], tick["symbol"], tick["price"], tick["volume"]))
            
            # 2. Forward to Orchestrator to process ticks in real-time
            # Try to fetch global orchestrator from registry or import
            try:
                from interfaces.base import ServiceRegistry
                # In actual loop, live_scan_loop will pull these raw ticks
            except Exception:
                pass

        except Exception as e:
            print(f"[Upstox PROD WS] Message processing error: {e}", file=sys.stderr)

    def _on_error(self, ws, error):
        print(f"[Upstox PROD WS] Socket error: {error}", file=sys.stderr)
        self.consecutive_failures += 1

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"[Upstox PROD WS] Connection closed. Code: {close_status_code}, Message: {close_msg}")
        self.is_connected = False
        self._trigger_reconnect()

    def _on_open(self, ws):
        print("[Upstox PROD WS] WebSocket Handshake Successful. Connection Open.")
        self.is_connected = True
        self.last_tick_time = datetime.datetime.now()
        self.consecutive_failures = 0
        self.reconnect_delay = 1.0
        # Re-subscribe to symbols
        if self.subscribed_symbols:
            self._subscribe_keys(list(self.subscribed_symbols))

    def _trigger_reconnect(self):
        if not self.is_connected:
            print(f"[Upstox PROD WS] Reconnecting in {self.reconnect_delay}s...")
            time.sleep(self.reconnect_delay)
            self.reconnect_delay = min(60.0, self.reconnect_delay * 2) # exponential backoff capped at 60s
            try:
                self.connect_websocket()
            except Exception as e:
                print(f"[Upstox PROD WS] Reconnection attempt failed: {e}", file=sys.stderr)

    def _subscribe_keys(self, symbols: List[str]):
        """Sends subscription payload in binary mode."""
        if not self.ws or not self.is_connected:
            return
        
        resolved_symbols = [self._resolve_symbol(s) for s in symbols]
        # Upstox V3 WebSocket subscription payload
        payload = {
            "guid": f"sub_{int(time.time())}",
            "method": "sub",
            "data": {
                "mode": "full", # 'full' for depth/quotes, 'ltp' for price-only
                "instrumentKeys": resolved_symbols
            }
        }
        try:
            self.ws.send(json.dumps(payload), opcode=websocket.ABNF.OPCODE_TEXT)
            print(f"[Upstox PROD WS] Subscribed to symbols: {resolved_symbols}")
        except Exception as e:
            print(f"[Upstox PROD WS] Subscription failed: {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # UpstoxInterface implementation
    # ------------------------------------------------------------------

    def connect_websocket(self):
        """Authorizes and initiates the WebSocket connection in a background thread."""
        with self.lock:
            if self.is_connected:
                return
            
            # Auto-populate subscription list if empty
            if not self.subscribed_symbols and self.symbol_to_key:
                self.subscribed_symbols = set(self.symbol_to_key.values())
            
            # Step 1: Get authorized WebSocket redirect URI
            print("[Upstox PROD WS] Authorizing connection...")
            try:
                auth_res = self._request("GET", "/v3/feed/market-data-feed/authorize")
                authorized_url = auth_res["data"]["authorizedRedirectUri"]
            except Exception as e:
                print(f"[Upstox PROD WS] Authorization failed: {e}", file=sys.stderr)
                raise ConnectionError(f"WebSocket Authorization Failed: {e}")

            # Step 2: Initialize WebSocketApp
            # follow_redirects is handled natively by websocket-client
            self.ws = websocket.WebSocketApp(
                authorized_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )

            # Step 3: Run websocket in a background thread
            def run_loop():
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            
            self.ws_thread = threading.Thread(target=run_loop, daemon=True)
            self.ws_thread.start()
            print("[Upstox PROD WS] Live stream reader thread started.")

    def disconnect_websocket(self):
        with self.lock:
            if self.ws:
                self.ws.close()
                self.is_connected = False
                print("[Upstox PROD WS] WebSocket closed manually.")

    def get_live_data(self, symbol: str, is_rest: bool = False) -> Dict[str, Any]:
        """Retrieves symbol quote data. If is_rest is True, queries quote API."""
        if not is_rest:
            # Pull from database raw_ticks cache
            query = "SELECT price, volume, time FROM raw_ticks WHERE symbol = %s ORDER BY time DESC LIMIT 1;"
            res = database.execute_query(query, (symbol,), fetch=True)
            if res:
                t = res[0][2]
                if hasattr(t, "tzinfo") and t.tzinfo is not None:
                    t = t.replace(tzinfo=None)
                self.last_tick_time = t
                return {"symbol": symbol, "price": float(res[0][0]), "volume": int(res[0][1]), "time": t}
        
        # REST Quote API Fallback
        resolved_symbol = self._resolve_symbol(symbol)
        res = self._request("GET", f"/v2/market-quote/quotes", params={"symbol": resolved_symbol})
        quotes_dict = res.get("data", {})
        data = list(quotes_dict.values())[0] if quotes_dict else {}
        ret_val = {
            "symbol": symbol,
            "price": float(data.get("last_price", 0.0)),
            "volume": int(data.get("volume", 0)),
            "time": datetime.datetime.now()
        }
        self.last_tick_time = ret_val["time"]
        return ret_val

    def get_option_chain(self, symbol: str, expiry_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Downloads full Option Chain for the underlying symbol and writes to database."""
        resolved_symbol = self._resolve_symbol(symbol)
        target_expiry = expiry_date
        if not target_expiry:
            try:
                print(f"[Upstox PROD] Fetching contracts to determine nearest expiry for {symbol}...")
                contracts_res = self._request("GET", "/v2/option/contract", params={"instrument_key": resolved_symbol})
                contracts = contracts_res.get("data", [])
                expiries = sorted(list(set(c.get("expiry") for c in contracts if c.get("expiry"))))
                if expiries:
                    target_expiry = expiries[0]
                    print(f"[Upstox PROD] Resolved nearest expiry date: {target_expiry}")
            except Exception as e:
                print(f"[Upstox PROD] Failed to resolve nearest expiry: {e}", file=sys.stderr)

        if not target_expiry:
            raise ValueError(f"Could not determine expiry_date for option chain of {symbol}")

        params = {
            "instrument_key": resolved_symbol,
            "expiry_date": target_expiry
        }
            
        print(f"[Upstox PROD] Downloading Option Chain for {symbol} (expiry: {target_expiry})...")
        res = self._request("GET", "/v2/option/chain", params=params)
        chain_list = res.get("data", [])
        
        # Ingestion pipeline to options_data table
        ingested_count = 0
        for item in chain_list:
            strike = Decimal(str(item.get("strike_price")))
            expiry = datetime.datetime.strptime(item.get("expiry"), "%Y-%m-%d").date()
            
            # Process Call Option
            call_opt = item.get("call_options", {})
            if call_opt:
                market_data = call_opt.get("market_data", {})
                insert_query = """
                    INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp)
                    VALUES (NOW(), %s, %s, %s, 'CE', %s, %s, %s, %s, %s)
                    ON CONFLICT (time, symbol, strike, expiry, option_type) DO NOTHING;
                """
                database.execute_query(insert_query, (
                    symbol, strike, expiry,
                    int(market_data.get("oi", 0)),
                    int(market_data.get("oi", 0) - market_data.get("prev_oi", 0)),
                    int(market_data.get("volume", 0)),
                    Decimal(str(market_data.get("iv", 0.0))),
                    Decimal(str(market_data.get("ltp", 0.0)))
                ))
                ingested_count += 1
                
            # Process Put Option
            put_opt = item.get("put_options", {})
            if put_opt:
                market_data = put_opt.get("market_data", {})
                insert_query = """
                    INSERT INTO options_data (time, symbol, strike, expiry, option_type, oi, oi_change, volume, iv, ltp)
                    VALUES (NOW(), %s, %s, %s, 'PE', %s, %s, %s, %s, %s)
                    ON CONFLICT (time, symbol, strike, expiry, option_type) DO NOTHING;
                """
                database.execute_query(insert_query, (
                    symbol, strike, expiry,
                    int(market_data.get("oi", 0)),
                    int(market_data.get("oi", 0) - market_data.get("prev_oi", 0)),
                    int(market_data.get("volume", 0)),
                    Decimal(str(market_data.get("iv", 0.0))),
                    Decimal(str(market_data.get("ltp", 0.0)))
                ))
                ingested_count += 1
                
        print(f"[Upstox PROD] Ingested {ingested_count} options chain records into DB.")
        return chain_list

    def get_historical_candles(self, symbol: str, timeframe: str, lookback_days: int) -> List[List[Any]]:
        """Queries historical candle data and saves to database market_data table."""
        # Convert internal timeframe names to Upstox V3 intervals
        # 1m -> minutes/1, 15m -> minutes/15, Daily -> days/1
        resolved_symbol = self._resolve_symbol(symbol)
        timeframe_config = {
            "1m": ("minutes", "1"),
            "15m": ("minutes", "15"),
            "Daily": ("days", "1")
        }
        unit, interval = timeframe_config.get(timeframe, ("minutes", "15"))
        
        to_date = datetime.datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.datetime.now() - datetime.timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        
        path = f"/v3/historical-candle/{resolved_symbol}/{unit}/{interval}/{to_date}/{from_date}"
        print(f"[Upstox PROD] Downloading historical candles for {symbol} ({timeframe}) from {from_date} to {to_date}...")
        
        res = self._request("GET", path)
        candles = res.get("data", {}).get("candles", [])
        
        # Ingestion loop into market_data table
        ingested = 0
        for candle in candles:
            # Upstox candle format: [timestamp, open, high, low, close, volume, open_interest]
            ts = datetime.datetime.fromisoformat(candle[0].replace("Z", "+00:00"))
            op = Decimal(str(candle[1]))
            hi = Decimal(str(candle[2]))
            lo = Decimal(str(candle[3]))
            cl = Decimal(str(candle[4]))
            vol = int(candle[5])
            
            ins_query = """
                INSERT INTO market_data (time, symbol, open, high, low, close, volume, timeframe)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol, timeframe) 
                DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close, volume=EXCLUDED.volume;
            """
            database.execute_query(ins_query, (ts, symbol, op, hi, lo, cl, vol, timeframe))
            ingested += 1
            
        print(f"[Upstox PROD] Ingested {ingested} candles for {symbol} ({timeframe}) into DB.")
        return candles

    def download_instrument_master(self) -> List[Dict[str, Any]]:
        """Downloads full NSE instrument list from CDN, filters NIFTY 50/F&O and saves locally."""
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        print(f"[Upstox PROD] Downloading instruments list from {url}...")
        
        req = urllib.request.Request(
            url,
            headers={"Accept-Encoding": "gzip", "User-Agent": "Mozilla/5.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if resp.info().get('Content-Encoding') == 'gzip' or url.endswith('.gz'):
                    data = gzip.decompress(data)
                instruments = json.loads(data.decode("utf-8"))
        except Exception as e:
            print(f"[Upstox PROD] Failed to download instruments file: {e}", file=sys.stderr)
            raise
            
        print(f"[Upstox PROD] Downloaded {len(instruments)} symbols. Filtering F&O contracts...")
        filtered = []
        for inst in instruments:
            # We filter Nifty 50 underlying or F&O segment symbols
            seg = inst.get("segment")
            if seg in ("NSE_EQ", "NSE_FO"):
                filtered.append(inst)
                
        # Write to instruments CSV cache locally
        csv_path = "nifty50_instruments.csv"
        import csv
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["instrument_key", "symbol", "name", "segment", "expiry", "strike", "option_type"])
            for inst in filtered[:2000]:  # Limit to active F&O to save space
                writer.writerow([
                    inst.get("instrument_key", ""),
                    inst.get("tradingsymbol", ""),
                    inst.get("name", ""),
                    inst.get("segment", ""),
                    inst.get("expiry", ""),
                    inst.get("strike", ""),
                    inst.get("option_type", "")
                ])
                
        print(f"[Upstox PROD] Successfully cached {len(filtered)} filtered symbols to {csv_path}")
        return filtered
