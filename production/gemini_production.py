import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, List, Optional

from interfaces.gemini import GeminiInterface

class GeminiProduction(GeminiInterface):
    """Production Gemini client using Google AI Studio API.
    Maintains clean JSON structuring configuration and error handling.
    """

    TIMEOUT = 90  # seconds

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "mock_gemini_key")

    def _call_api(self, prompt: str, system_context: str = None, response_schema: Optional[Dict[str, Any]] = None, enable_search: bool = False) -> str:
        """Runs generateContent request to Gemini API."""
        if not self.api_key or "mock" in self.api_key.lower():
            print("[Gemini PROD] Warning: Using Mock key. Returning grounded fallback.")
            return self._fallback_grounded_response(prompt, system_context)

        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        
        combined_prompt = f"{system_context}\n\nUser Question: {prompt}" if system_context else prompt
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": combined_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2
            }
        }
        
        if enable_search:
            payload["tools"] = [{"google_search": {}}]
        
        if response_schema and not enable_search:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = response_schema

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text.startswith("```"):
                        lines = text.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines[-1].startswith("```"):
                            lines = lines[:-1]
                        text = "\n".join(lines).strip()
                    return text
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    sleep_time = (2 ** attempt) + 1
                    print(f"[Gemini PROD] HTTP {e.code} on attempt {attempt+1}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                print(f"[Gemini PROD] HTTP Error {e.code}: {e.reason}", file=sys.stderr)
                raise
            except Exception as e:
                print(f"[Gemini PROD] Network error on attempt {attempt+1}: {e}", file=sys.stderr)
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
                
        raise RuntimeError("Gemini API call failed after 3 attempts.")

    def _fallback_grounded_response(self, prompt: str, system_context: str = None) -> str:
        """Grounded fallbacks for trade summary and narrative logs."""
        if "GEIE — GLOBAL EVENT IMPACT ENGINE" in prompt.upper() or "GLOBAL INTELLIGENCE REPORT" in prompt.upper():
            # Mock Prompt 3 response
            stock_impacts = {}
            for sym in ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
                        "INDUSINDBK", "BAJFINANCE", "BAJAJFINSV", "INFY", "TCS",
                        "HCLTECH", "WIPRO", "TECHM", "RELIANCE", "ONGC", "BPCL",
                        "NTPC", "POWERGRID", "COALINDIA", "MARUTI", "TATAMOTORS",
                        "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "TATASTEEL", "JSWSTEEL",
                        "HINDALCO", "ADANIENT", "SUNPHARMA", "DRREDDY", "CIPLA",
                        "DIVISLAB", "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA",
                        "TATACONSUM", "LT", "ULTRACEMCO", "GRASIM", "ADANIPORTS",
                        "BHARTIARTL", "ASIANPAINT", "TITAN", "APOLLOHOSP",
                        "EICHERMOT", "SBILIFE", "HDFCLIFE", "UPL"]:
                stock_impacts[sym] = {
                    "direction": "POSITIVE" if sym in ["TATASTEEL", "JSWSTEEL", "RELIANCE"] else "NEUTRAL",
                    "magnitude": 2 if sym in ["TATASTEEL", "JSWSTEEL", "RELIANCE"] else 1,
                    "reasons": ["Correlation trigger or trend alignment in mock mode"],
                    "confidence": "HIGH",
                    "urgency": "INTRADAY"
                }
            return json.dumps({
                "geie_id": f"GEIE-{datetime.date.today()}-001",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
                "market_sentiment": "NEUTRAL",
                "events_analyzed": ["Mock Event Global", "Mock Event Domestic"],
                "stock_impacts": stock_impacts,
                "top_beneficiaries": ["TATASTEEL", "JSWSTEEL", "RELIANCE", "INFY", "TCS"],
                "top_losers": ["MARUTI", "TATAMOTORS"],
                "sectors_strong": ["METALS", "ENERGY"],
                "sectors_weak": ["AUTO"],
                "geie_status": "ACTIVE"
            })
            
        if "GEIE — LIVE SIGNAL ANALYZER" in prompt.upper() or "SIGNAL DATA" in prompt.upper():
            # Mock Prompt 5 response
            return json.dumps({
                "geie_live_id": f"GEIE-LIVE-{int(time.time())}",
                "symbol": "RELIANCE",
                "recommendation": "PROCEED",
                "confidence_boost": True,
                "key_observation": "Options buildup shows strong supportive writing.",
                "risk_flag": "NONE",
                "geie_still_valid": True
            })

        if "ANALYZE THE FOLLOWING TRADE" in prompt.upper() or "TRADE ATTRIBUTES:" in prompt.upper():
            return """## Trade Summary
This report analyzes the LONG paper trade for the underlying symbol. The signal was approved and resolved.

## Why Trade Was Taken
- SMC structure: Bullish BOS confirmed.
- Options: Put writing support.

## What Happened During Trade
- Entry triggered. Price progressed with volume support.

## Exit Analysis
- Exited target boundary successfully.

## Lessons Learned
- Setup worked as planned by the historical parameters."""
        
        return json.dumps({
            "market_sentiment": "RISK_ON",
            "stock_impacts": {
                "RELIANCE": {"direction": "POSITIVE", "magnitude": 2, "reasons": ["Institutional accumulation"], "confidence": "HIGH", "urgency": "INTRADAY"}
            },
            "top_beneficiaries": ["RELIANCE"],
            "top_losers": []
        })

    # ------------------------------------------------------------------
    # GeminiInterface implementation
    # ------------------------------------------------------------------

    def analyze_news_impact(self, global_news: str, india_news: str = None, options_concentration: str = None) -> Dict[str, Any]:
        """Analyzes global and Indian news and maps impact to NIFTY 50 stocks (GEIE Engine). Prompt 3."""
        prompt = f"""You are GEIE — Global Event Impact Engine.

Your job is to analyze news events and map
their impact on NIFTY 50 stocks.

You must think in second and third order effects.

Example of second order thinking:
China cuts steel production
→ First order: Steel prices rise globally
→ Second order: TATA Steel margins improve
→ Third order: MARUTI input costs rise

Today's Global Intelligence Report:
{global_news}

Today's India Intelligence Report:
{india_news}

Your task:
Analyze ALL events in both reports.
For each event, identify which NIFTY 50 stocks
are positively or negatively impacted.

NIFTY 50 stocks to analyze:
HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, AXISBANK,
INDUSINDBK, BAJFINANCE, BAJAJFINSV,
INFY, TCS, HCLTECH, WIPRO, TECHM,
RELIANCE, ONGC, BPCL, NTPC, POWERGRID, COALINDIA,
MARUTI, TATAMOTORS, M&M, BAJAJ-AUTO, HEROMOTOCO,
TATASTEEL, JSWSTEEL, HINDALCO, ADANIENT,
SUNPHARMA, DRREDDY, CIPLA, DIVISLAB,
HINDUNILVR, ITC, NESTLEIND, BRITANNIA, TATACONSUM,
LT, ULTRACEMCO, GRASIM, ADANIPORTS,
BHARTIARTL, ASIANPAINT, TITAN, APOLLOHOSP,
EICHERMOT, SBILIFE, HDFCLIFE, UPL, LT

Return ONLY this JSON. No explanation. No text.

{{
  "geie_id": "GEIE-[DATE]-001",
  "timestamp": "[IST TIME]",
  "market_sentiment": "RISK_ON or NEUTRAL or RISK_OFF",
  "events_analyzed": ["list of key events"],
  "stock_impacts": {{
    "TATASTEEL": {{
      "direction": "POSITIVE or NEGATIVE or NEUTRAL",
      "magnitude": 1 or 2 or 3,
      "reasons": ["reason 1", "reason 2"],
      "confidence": "HIGH or MEDIUM or LOW",
      "urgency": "IMMEDIATE or INTRADAY or MULTI_DAY"
    }},
    "[REPEAT FOR ALL 50 STOCKS]"
  }},
  "top_beneficiaries": ["top 5 positive stocks"],
  "top_losers": ["top 5 negative stocks"],
  "sectors_strong": ["strong sectors today"],
  "sectors_weak": ["weak sectors today"],
  "geie_status": "ACTIVE"
}}"""
        
        schema = {
            "type": "OBJECT",
            "properties": {
                "geie_id": {"type": "STRING"},
                "timestamp": {"type": "STRING"},
                "market_sentiment": {"type": "STRING", "enum": ["RISK_ON", "NEUTRAL", "RISK_OFF"]},
                "events_analyzed": {"type": "ARRAY", "items": {"type": "STRING"}},
                "stock_impacts": {
                    "type": "OBJECT",
                    "additionalProperties": {
                        "type": "OBJECT",
                        "properties": {
                            "direction": {"type": "STRING", "enum": ["POSITIVE", "NEGATIVE", "NEUTRAL"]},
                            "magnitude": {"type": "INTEGER"},
                            "reasons": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "confidence": {"type": "STRING", "enum": ["HIGH", "MEDIUM", "LOW"]},
                            "urgency": {"type": "STRING", "enum": ["IMMEDIATE", "INTRADAY", "MULTI_DAY"]}
                        },
                        "required": ["direction", "magnitude", "reasons", "confidence", "urgency"]
                    }
                },
                "top_beneficiaries": {"type": "ARRAY", "items": {"type": "STRING"}},
                "top_losers": {"type": "ARRAY", "items": {"type": "STRING"}},
                "sectors_strong": {"type": "ARRAY", "items": {"type": "STRING"}},
                "sectors_weak": {"type": "ARRAY", "items": {"type": "STRING"}},
                "geie_status": {"type": "STRING"}
            },
            "required": ["geie_id", "timestamp", "market_sentiment", "events_analyzed", "stock_impacts", "top_beneficiaries", "top_losers", "sectors_strong", "sectors_weak", "geie_status"]
        }
        
        res = self._call_api(prompt, system_context="You are the IIIS GEIE Intelligence Engine.", response_schema=None)
        return json.loads(res)

    def analyze_live_signal(self, signal_data: Dict[str, Any], tech_data: Dict[str, Any], current_market: Dict[str, Any], morning_geie: Dict[str, Any], breaking_news: str) -> Dict[str, Any]:
        """Analyzes a live trading signal against market backdrop and morning GEIE context. Prompt 5."""
        prompt = f"""You are GEIE — Live Signal Analyzer.

A trading signal has been detected.
Analyze this signal in current market context.

SIGNAL DATA:
Stock: {signal_data.get('symbol')}
Direction: {signal_data.get('direction')}
Score: {signal_data.get('score')} out of 100
Time: {signal_data.get('time')}

TECHNICAL DATA:
Regime: {tech_data.get('regime')}
Sector Rank: {tech_data.get('sector_rank')} of 10
Relative Strength: {tech_data.get('relative_strength')} percentile
Volume RVOL: {tech_data.get('rvol')}x average
India VIX: {tech_data.get('vix')}
SMC: {tech_data.get('smc_5m')} + {tech_data.get('smc_15m')}
Options: {tech_data.get('options_buildup')}
Historical Win Rate: {tech_data.get('win_rate')}% from {tech_data.get('setups_count')} setups

CURRENT MARKET:
NIFTY: {current_market.get('nifty_price')} ({current_market.get('nifty_change')}%)
A/D Ratio: {current_market.get('ad_ratio')}
Breadth: {current_market.get('breadth')}

GEIE CACHED CONTEXT:
{signal_data.get('symbol')} impact from morning:
Direction: {morning_geie.get('direction')}
Reasons: {morning_geie.get('reasons')}
Confidence: {morning_geie.get('confidence')}

CURRENT NEWS (if any breaking):
{breaking_news or 'NONE'}

Your task:
Should this signal be sent to the human?

Consider:
1. Is GEIE context still valid?
2. Any new risk since morning?
3. Does options data support direction?
4. Is timing good (avoid lunch, expiry traps)?

Return ONLY this JSON. No text. No explanation.

{{
  "geie_live_id": "GEIE-LIVE-[TIMESTAMP]",
  "symbol": "[SYMBOL]",
  "recommendation": "PROCEED or CAUTION or BLOCK",
  "confidence_boost": true or false,
  "key_observation": "one line — most important thing",
  "risk_flag": "any risk or NONE",
  "geie_still_valid": true or false
}}"""

        schema = {
            "type": "OBJECT",
            "properties": {
                "geie_live_id": {"type": "STRING"},
                "symbol": {"type": "STRING"},
                "recommendation": {"type": "STRING", "enum": ["PROCEED", "CAUTION", "BLOCK"]},
                "confidence_boost": {"type": "BOOLEAN"},
                "key_observation": {"type": "STRING"},
                "risk_flag": {"type": "STRING"},
                "geie_still_valid": {"type": "BOOLEAN"}
            },
            "required": ["geie_live_id", "symbol", "recommendation", "confidence_boost", "key_observation", "risk_flag", "geie_still_valid"]
        }
        res = self._call_api(prompt, system_context="You are the GEIE Live Signal Analyzer.", response_schema=None)
        return json.loads(res)


    def generate_report(self, prompt: str, system_context: str = None) -> str:
        return self._call_api(prompt, system_context=system_context, response_schema=None)

    def generate_founder_summary(self, notes: str) -> str:
        prompt = f"Extract psychological patterns, rules compliance, and general feedback from these founder notes:\n\n{notes}"
        return self._call_api(prompt, system_context="You are the IIIS Founder Behavior Auditor.")

    def generate_trade_story(self, trade_events: List[Dict[str, Any]]) -> str:
        prompt = f"Formulate a chronological narrative story describing the trade timeline milestones:\n\n{json.dumps(trade_events)}"
        return self._call_api(prompt, system_context="You are the IIIS Chronological Story Writer.")

    def generate_daily_narrative(self, session_date: str, metrics: Dict[str, Any]) -> str:
        prompt = f"Summarize daily trading metrics and events for date {session_date}:\n\n{json.dumps(metrics)}"
        return self._call_api(prompt, system_context="You are the IIIS Daily Narrative Compiler.")
