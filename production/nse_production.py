import os
import sys
import csv
import io
import zipfile
import datetime
import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error
import json
from decimal import Decimal
from typing import List, Dict, Any

import database
from interfaces.nse import NSEInterface

class NSEProduction(NSEInterface):
    """Production NSE scraper/loader.
    Downloads files from archives.nseindia.com and api-based endpoints.
    Handles sessions/cookies dynamically to bypass scraper blocks.
    """

    BASE_URL = "https://www.nseindia.com"
    TIMEOUT = 15

    def __init__(self):
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'),
            ('Accept-Language', 'en-US,en;q=0.9'),
            ('Referer', 'https://www.nseindia.com/')
        ]

    def _establish_session(self):
        """Bypasses NSE's anti-bot protections by hitting the landing page first to load cookies."""
        try:
            # Hit base site
            with self.opener.open(self.BASE_URL, timeout=self.TIMEOUT) as resp:
                resp.read()
        except Exception as e:
            print(f"[NSE PROD] Failed to establish cookies session: {e}", file=sys.stderr)

    def _download_file(self, url: str) -> bytes:
        """Downloads a file, automatically retrying with session establishment if blocked."""
        req = urllib.request.Request(url)
        for attempt in range(2):
            try:
                with self.opener.open(req, timeout=self.TIMEOUT) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                if e.code == 401 or e.code == 403:
                    print(f"[NSE PROD] HTTP {e.code} on download. Re-establishing session...")
                    self._establish_session()
                    continue
                raise
            except Exception as e:
                print(f"[NSE PROD] Error downloading file: {e}", file=sys.stderr)
                if attempt == 1:
                    raise
                self._establish_session()
        raise ConnectionError(f"Failed to retrieve file from: {url}")

    # ------------------------------------------------------------------
    # NSEInterface implementation
    # ------------------------------------------------------------------

    def fetch_fii_dii_data(self) -> Dict[str, Any]:
        """Scrapes FII/DII daily transaction values from official NSE website API."""
        url = "https://www.nseindia.com/api/fii-dii"
        print(f"[NSE PROD] Scraped API URL: {url}")
        
        try:
            self._establish_session()
            body = self._download_file(url)
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            print(f"[NSE PROD] FII/DII data scrape failed: {e}", file=sys.stderr)
            # Safe grounded fallback values
            return {
                "date": datetime.date.today(),
                "fii_action": "BUYER", "fii_amount_crores": 0.0,
                "dii_action": "BUYER", "dii_amount_crores": 0.0,
                "combined_bias": "NEUTRAL",
                "consecutive_fii_buy_days": 0, "consecutive_fii_sell_days": 0
            }

        # Parse JSON array. Example fields: [ { "category": "FII", "date": "17-Jun-2026", "buyValue": 500, "sellValue": 400, "netValue": 100 } ]
        fii_buy, fii_sell, fii_net = 0.0, 0.0, 0.0
        dii_buy, dii_sell, dii_net = 0.0, 0.0, 0.0
        
        for record in data:
            category = record.get("category", "")
            net = float(str(record.get("netValue", 0.0)).replace(",", ""))
            if category == "FII":
                fii_net = net
            elif category == "DII":
                dii_net = net

        fii_action = "BUYER" if fii_net >= 0 else "SELLER"
        dii_action = "BUYER" if dii_net >= 0 else "SELLER"
        
        if fii_net > 0 and dii_net > 0:
            bias = "BULLISH"
        elif fii_net < 0 and dii_net < 0:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        result = {
            "date": datetime.date.today(),
            "fii_action": fii_action,
            "fii_amount_crores": abs(fii_net),
            "dii_action": dii_action,
            "dii_amount_crores": abs(dii_net),
            "combined_bias": bias,
            "consecutive_fii_buy_days": 1 if fii_net > 0 else 0,
            "consecutive_fii_sell_days": 1 if fii_net < 0 else 0
        }

        # Write to DB table fii_dii_tracker
        insert_query = """
            INSERT INTO fii_dii_tracker (date, fii_action, fii_amount_crores, dii_action, dii_amount_crores, combined_bias, consecutive_fii_buy_days, consecutive_fii_sell_days)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date) DO UPDATE SET
                fii_action=EXCLUDED.fii_action, fii_amount_crores=EXCLUDED.fii_amount_crores,
                dii_action=EXCLUDED.dii_action, dii_amount_crores=EXCLUDED.dii_amount_crores,
                combined_bias=EXCLUDED.combined_bias;
        """
        database.execute_query(insert_query, (
            result["date"], result["fii_action"], Decimal(str(result["fii_amount_crores"])),
            result["dii_action"], Decimal(str(result["dii_amount_crores"])), result["combined_bias"],
            result["consecutive_fii_buy_days"], result["consecutive_fii_sell_days"]
        ))
        
        return result

    def fetch_bulk_deals(self) -> List[Dict[str, Any]]:
        """Downloads intraday bulk deals CSV file from official NSE archive."""
        url = "https://archives.nseindia.com/content/equities/bulk.csv"
        return self._fetch_deal_file(url, "BULK")

    def fetch_block_deals(self) -> List[Dict[str, Any]]:
        """Downloads block deals CSV file from official NSE archive."""
        url = "https://archives.nseindia.com/content/equities/block.csv"
        return self._fetch_deal_file(url, "BLOCK")

    def _fetch_deal_file(self, url: str, deal_type_cat: str) -> List[Dict[str, Any]]:
        print(f"[NSE PROD] Downloading {deal_type_cat} deals from {url}...")
        try:
            body = self._download_file(url)
            csv_text = body.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[NSE PROD] Failed to download {deal_type_cat} deal file: {e}", file=sys.stderr)
            return []

        deals = []
        reader = csv.DictReader(io.StringIO(csv_text))
        
        # Ingestion pipeline to bulk_deal_tracker table
        for row in reader:
            # Expected CSV headers: Date, Symbol, Security Name, Client Name, Buy/Sell, Quantity Traded, Trade Price/Wght. Avg. Price, Value
            try:
                dt_str = row.get("Date", "").strip()
                if not dt_str:
                    continue
                # Dates are typically DD-MMM-YYYY or YYYY-MM-DD
                for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
                    try:
                        dt = datetime.datetime.strptime(dt_str, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    dt = datetime.date.today()

                symbol = row.get("Symbol", "").strip()
                client = row.get("Client Name", "").strip()
                action = row.get("Buy/Sell", "").strip().upper()
                qty = int(row.get("Quantity Traded", "0").replace(",", ""))
                price = float(row.get("Trade Price/Wght. Avg. Price", "0").replace(",", ""))
                
                # Value is Value in Crores or Rupees depending on CSV units. We calculate directly:
                # qty * price / 10,000,000 (1 Crore = 10^7)
                value_crores = (qty * price) / 10000000.0

                deal_record = {
                    "timestamp": datetime.datetime.combine(dt, datetime.time(15, 30)),
                    "symbol": symbol,
                    "deal_type": "BUY" if "BUY" in action else "SELL",
                    "quantity": qty,
                    "price": price,
                    "value_crores": value_crores,
                    "client_name": client,
                    "deal_category": deal_type_cat
                }
                deals.append(deal_record)

                # Insert into bulk_deal_tracker
                ins_query = """
                    INSERT INTO bulk_deal_tracker (timestamp, symbol, deal_type, quantity, price, value_crores, client_name, deal_category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """
                database.execute_query(ins_query, (
                    deal_record["timestamp"], deal_record["symbol"], deal_record["deal_type"],
                    deal_record["quantity"], Decimal(str(deal_record["price"])),
                    Decimal(str(deal_record["value_crores"])), deal_record["client_name"],
                    deal_record["deal_category"]
                ))
            except Exception as ex:
                # Skip invalid lines
                continue

        print(f"[NSE PROD] Ingested {len(deals)} {deal_type_cat} records into database.")
        return deals

    def fetch_bhavcopy(self, download_date: datetime.date) -> List[Dict[str, Any]]:
        """Downloads equity Bhavcopy zip, extracts, parses columns and writes to market_data table."""
        # URL Format: https://archives.nseindia.com/content/historical/EQUITIES/2026/JUN/cm17JUN2026bhav.csv.zip
        year = download_date.strftime("%Y")
        month = download_date.strftime("%b").upper() # JUN
        day_str = download_date.strftime("%d%b%Y").upper() # 17JUN2026
        
        filename = f"cm{day_str}bhav.csv"
        zip_url = f"https://archives.nseindia.com/content/historical/EQUITIES/{year}/{month}/{filename}.zip"
        
        print(f"[NSE PROD] Downloading Bhavcopy from: {zip_url}")
        try:
            body = self._download_file(zip_url)
        except Exception as e:
            print(f"[NSE PROD] Bhavcopy file not available for {download_date}: {e}", file=sys.stderr)
            return []

        # Decompress Zip file
        bhav_records = []
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                csv_data = zf.read(filename).decode("utf-8")
        except Exception as e:
            print(f"[NSE PROD] Failed to decompress zip file: {e}", file=sys.stderr)
            return []

        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_data))
        ingested = 0
        
        # We only ingest Nifty 50 or F&O symbols to keep DB size constrained
        from config import Config
        # In actual loop, we cross check instruments list or just load all Equity Series EQ symbols
        for row in reader:
            series = row.get("SERIES", "").strip()
            if series != "EQ":
                continue # Skip derivatives/debentures/preferred
            
            symbol = row.get("SYMBOL", "").strip()
            try:
                op = Decimal(str(row.get("OPEN", "0").strip()))
                hi = Decimal(str(row.get("HIGH", "0").strip()))
                lo = Decimal(str(row.get("LOW", "0").strip()))
                cl = Decimal(str(row.get("CLOSE", "0").strip()))
                vol = int(row.get("TOTTRDQTY", "0").strip())
                ts = datetime.datetime.combine(download_date, datetime.time(15, 30))

                bhav_records.append({
                    "symbol": symbol, "open": float(op), "high": float(hi),
                    "low": float(lo), "close": float(cl), "volume": vol, "time": ts
                })

                # Ingest into market_data Daily timeframe
                ins_query = """
                    INSERT INTO market_data (time, symbol, open, high, low, close, volume, timeframe)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Daily')
                    ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close, volume=EXCLUDED.volume;
                """
                database.execute_query(ins_query, (ts, symbol, op, hi, lo, cl, vol))
                ingested += 1
            except Exception:
                continue

        print(f"[NSE PROD] Ingested {ingested} Bhavcopy equity records into DB.")
        return bhav_records

    def fetch_corporate_actions(self) -> List[Dict[str, Any]]:
        """Downloads corporate actions CSV and loads it into event_calendar."""
        url = "https://archives.nseindia.com/content/equities/actions.csv"
        print(f"[NSE PROD] Downloading Corporate Actions from {url}...")
        
        try:
            body = self._download_file(url)
            csv_text = body.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[NSE PROD] Failed to download corporate actions: {e}", file=sys.stderr)
            return []

        actions = []
        reader = csv.DictReader(io.StringIO(csv_text))
        
        # Ingestion pipeline to event_calendar table
        for row in reader:
            # Expected columns: Symbol, Series, Security Name, Purpose, Face Value, Ex Date
            try:
                symbol = row.get("Symbol", "").strip()
                purpose = row.get("Purpose", "").strip()
                ex_date_str = row.get("Ex Date", "").strip()
                if not ex_date_str:
                    continue
                
                # Parse Date DD-MMM-YYYY or YYYY-MM-DD
                for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
                    try:
                        ex_date = datetime.datetime.strptime(ex_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    continue

                act = {
                    "event_name": f"Corporate Action: {purpose} for {symbol}",
                    "event_date": ex_date,
                    "event_time": datetime.time(9, 15),
                    "impact_level": "MODERATE",
                    "description": f"Ex-Date corporate event. Security Face Value: {row.get('Face Value', 'N/A')}"
                }
                actions.append(act)

                # Write to event_calendar
                ins_query = """
                    INSERT INTO event_calendar (event_name, event_date, event_time, impact_level, description)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (event_name, event_date) DO NOTHING;
                """
                database.execute_query(ins_query, (act["event_name"], act["event_date"], act["event_time"], act["impact_level"], act["description"]))
            except Exception:
                continue

        print(f"[NSE PROD] Ingested {len(actions)} corporate actions into DB calendar.")
        return actions
