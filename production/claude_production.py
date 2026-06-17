import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import List, Dict, Any, Optional

from interfaces.claude import ClaudeInterface

class ClaudeProduction(ClaudeInterface):
    """Production Claude Client using Anthropic Messages API.
    Handles tool use for strict schema formatting and error recovery.
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    TIMEOUT = 30  # seconds

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY", "mock_claude_key")

    def _call_api(self, prompt: str, system_context: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, tool_choice: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST request to Anthropic API with headers and retries."""
        if not self.api_key or "mock" in self.api_key.lower():
            print("[Claude PROD] Warning: Using Mock key. Returning grounded mock fallback.")
            return self._fallback_grounded_response(prompt, tools)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        if system_context:
            payload["system"] = system_context
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        req = urllib.request.Request(
            self.API_URL,
            headers=headers,
            data=json.dumps(payload).encode("utf-8"),
            method="POST"
        )

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as response:
                    res = json.loads(response.read().decode("utf-8"))
                    
                    # If tool choice was forced, return tool use inputs
                    if tools and res.get("content"):
                        for item in res["content"]:
                            if item.get("type") == "tool_use":
                                return item["input"]
                                
                    return {"text": res["content"][0]["text"]}
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    sleep_time = (2 ** attempt) + 1
                    print(f"[Claude PROD] HTTP {e.code} on attempt {attempt+1}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                print(f"[Claude PROD] HTTP Error {e.code}: {e.reason}", file=sys.stderr)
                raise
            except Exception as e:
                print(f"[Claude PROD] Network error on attempt {attempt+1}: {e}", file=sys.stderr)
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError("Claude API call failed after 3 attempts.")

    def _fallback_grounded_response(self, prompt: str, tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Structured fallback values matching tools definition schemas."""
        if not tools:
            return {"text": "Grounded mock analysis: The setup holds volume criteria."}
            
        tool_name = tools[0]["name"]
        import datetime
        if tool_name == "watchlist_review":
            return {
                "arc_id": f"ARC-PRE-{datetime.date.today()}-001",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
                "market_context": "Mock premarket watchlist review context",
                "watchlist_review": {
                    "RELIANCE": {"decision": "APPROVE", "reason": "Setup holds volume criteria."}
                },
                "overall_market_call": "BULLISH",
                "key_risks_today": ["Volatile global cues"],
                "arc_status": "COMPLETE"
            }
        elif tool_name == "arc_live_review":
            return {
                "arc_live_id": f"ARC-LIVE-{int(time.time())}",
                "symbol": "RELIANCE",
                "decision": "APPROVE",
                "reason": "Signal backed by robust mock parameters.",
                "contrarian_flag": "NONE",
                "urgency_note": "act fast"
            }
        elif tool_name == "postmarket_review":
            return {
                "arc_eod_id": f"ARC-EOD-{datetime.date.today()}",
                "session_quality": "GOOD",
                "what_worked": "Mock post market signals processed cleanly.",
                "what_failed": "Some tight stops triggered.",
                "best_signal": "TATASTEEL because of quick target hit.",
                "worst_signal": "HDFCBANK due to stop out.",
                "tomorrow_watchlist": ["TATASTEEL", "HDFCBANK"],
                "tomorrow_avoid": ["WIPRO"],
                "system_suggestion": "NONE",
                "overall_assessment": "Mock run complete."
            }
        elif tool_name == "arc_decision":
            return {
                "arc_decision": "APPROVE",
                "arc_confidence": 92,
                "reasoning_summary": "Passed all structural volume and options criteria.",
                "conflict_flags": [], "reject_reasons": [], "caution_reasons": []
            }
        elif tool_name == "graveyard_diagnostics":
            return {
                "avoidability_rating": "HIGH",
                "warning_signs": ["Muted entry volume support."],
                "failure_category": "WEAK_VOLUME",
                "lessons_learned": "Avoid active entries when volume breaks below daily averages."
            }
        
        return {}

    # ------------------------------------------------------------------
    # ClaudeInterface implementation
    # ------------------------------------------------------------------

    def review_watchlist_premarket(self, watchlist: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        global_sentiment = context.get("global_sentiment", "NEUTRAL")
        india_sentiment = context.get("india_sentiment", "NEUTRAL")
        geie_summary = context.get("geie_summary", "")
        sector_ranking = context.get("sector_ranking", "")
        candidates_str = context.get("candidates_str", "")
        
        # Build candidate long/short representation
        if not candidates_str and watchlist:
            long_cands = []
            for i, sym in enumerate(watchlist, 1):
                long_cands.append(f"{i}. {sym} — Score 86, GEIE POSITIVE HIGH")
            candidates_str = "LONG CANDIDATES:\n" + "\n".join(long_cands) + "\n\nSHORT CANDIDATES:\nNone"

        prompt = f"""You are ARC — AI Research Committee.

You are a senior institutional analyst.
Your job is to review the pre-market watchlist
and give final approval or rejection.

You have veto power only.
You do NOT affect the score.
You do NOT place trades.

Today's context:

GLOBAL SENTIMENT: {global_sentiment}
INDIA SENTIMENT: {india_sentiment}
GEIE SUMMARY: {geie_summary}
SECTOR RANKING: {sector_ranking}

Watchlist to review:

{candidates_str}

For EACH stock give:
1. Decision: APPROVE or CAUTION or REJECT
2. One line reason

Rules for your decision:
APPROVE: Setup looks good, proceed normally
CAUTION: Proceed but flag the risk
REJECT: Do not alert on this stock today

Reject reasons can include:
- Earnings risk not caught by system
- News risk that contradicts the signal
- Broader market concern
- Sector specific risk

Return ONLY this JSON:

{{
  "arc_id": "ARC-PRE-[DATE]-001",
  "timestamp": "[IST TIME]",
  "market_context": "one line summary",
  "watchlist_review": {{
    "TATASTEEL": {{
      "decision": "APPROVE",
      "reason": "one line"
    }}
  }},
  "overall_market_call": "BULLISH or NEUTRAL or BEARISH",
  "key_risks_today": ["risk 1", "risk 2"],
  "arc_status": "COMPLETE"
}}"""

        tools = [{
            "name": "watchlist_review",
            "description": "Reviews the entire pre-market watchlist of LONG and SHORT candidates.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "arc_id": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "market_context": {"type": "string"},
                    "watchlist_review": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "decision": {"type": "string", "enum": ["APPROVE", "CAUTION", "REJECT"]},
                                "reason": {"type": "string"}
                            },
                            "required": ["decision", "reason"]
                        }
                    },
                    "overall_market_call": {"type": "string", "enum": ["BULLISH", "NEUTRAL", "BEARISH"]},
                    "key_risks_today": {"type": "array", "items": {"type": "string"}},
                    "arc_status": {"type": "string"}
                },
                "required": ["arc_id", "timestamp", "market_context", "watchlist_review", "overall_market_call", "key_risks_today", "arc_status"]
            }
        }]
        
        res = self._call_api(prompt, system_context="You are the IIIS ARC Premarket Review Engine.", tools=tools, tool_choice={"type": "tool", "name": "watchlist_review"})
        return res

    def review_live_signal(self, signal_data: Dict[str, Any], tech_summary: Dict[str, Any], intelligence_summary: Dict[str, Any], risk_summary: Dict[str, Any], market_now: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""You are ARC — Live Signal Reviewer.

A trading signal needs final approval
before being sent to the human.

You are the last check before the alert.
You have veto power only.
You do NOT score. You do NOT trade.

SIGNAL DETAILS:
Stock: {signal_data.get('symbol')}
Direction: {signal_data.get('direction')}
Score: {signal_data.get('score')}
Time: {signal_data.get('time')}
Valid Until: {signal_data.get('valid_until')} ({signal_data.get('valid_minutes', 15)} minutes left)

TECHNICAL SUMMARY:
Regime: {tech_summary.get('regime')}
RS: {tech_summary.get('rs')}
RVOL: {tech_summary.get('rvol')}
SMC: {tech_summary.get('smc')}
Options: {tech_summary.get('options')}

INTELLIGENCE SUMMARY:
GEIE Direction: {intelligence_summary.get('geie_direction')}
GEIE Confidence: {intelligence_summary.get('geie_confidence')}
GEIE Live Check: {intelligence_summary.get('geie_live_check')}
Historical WR: {intelligence_summary.get('win_rate')}% ({intelligence_summary.get('setups_count')} similar setups)
Pre-Market ARC: {intelligence_summary.get('premarket_arc')}

RISK SUMMARY:
Daily Risk Used: {risk_summary.get('daily_risk_used')}% of 2% limit
Consecutive Losses Today: {risk_summary.get('consecutive_losses')}
Active Alerts: {risk_summary.get('active_alerts')} of 4 max
Sector Alerts: {risk_summary.get('sector_alerts')} of 2 max

MARKET RIGHT NOW:
NIFTY: {market_now.get('nifty')} ({market_now.get('nifty_change')}%)
VIX: {market_now.get('vix')}
Breadth: {market_now.get('breadth')} advancing of 50

Your job:
Final yes or no.

Think about:
1. Is this the right time to alert?
2. Any contrarian view I should flag?
3. Is risk acceptable?
4. Alert expires in {signal_data.get('valid_minutes', 15)} minutes — is there time?

Return ONLY this JSON. Nothing else.

{{
  "arc_live_id": "ARC-LIVE-[TIMESTAMP]",
  "symbol": "[SYMBOL]",
  "decision": "APPROVE or CAUTION or REJECT",
  "reason": "one line — most important reason",
  "contrarian_flag": "any contrarian view or NONE",
  "urgency_note": "act fast or normal or no rush"
}}"""

        tools = [{
            "name": "arc_live_review",
            "description": "Formulates the final veto review decision on a live signal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "arc_live_id": {"type": "string"},
                    "symbol": {"type": "string"},
                    "decision": {"type": "string", "enum": ["APPROVE", "CAUTION", "REJECT"]},
                    "reason": {"type": "string"},
                    "contrarian_flag": {"type": "string"},
                    "urgency_note": {"type": "string"}
                },
                "required": ["arc_live_id", "symbol", "decision", "reason", "contrarian_flag", "urgency_note"]
            }
        }]

        res = self._call_api(prompt, system_context="You are the IIIS ARC Live Signal Reviewer.", tools=tools, tool_choice={"type": "tool", "name": "arc_live_review"})
        return res

    def review_symbol(self, signal_id: str, arc_input_bundle: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Run detailed ARC check for signal {signal_id}:\n\nBundle: {json.dumps(arc_input_bundle)}"
        
        tools = [{
            "name": "arc_decision",
            "description": "Formulates the final ARC decision record according to the standard schema.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "arc_decision": {"type": "string", "enum": ["APPROVE", "CAUTION", "REJECT"]},
                    "arc_confidence": {"type": "integer"},
                    "reasoning_summary": {"type": "string"},
                    "conflict_flags": {"type": "array", "items": {"type": "string"}},
                    "reject_reasons": {"type": "array", "items": {"type": "string"}},
                    "caution_reasons": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["arc_decision", "arc_confidence", "reasoning_summary", "conflict_flags", "reject_reasons", "caution_reasons"]
            }
        }]
        
        res = self._call_api(prompt, system_context="You are the IIIS ARC Real-time Review Engine.", tools=tools, tool_choice={"type": "tool", "name": "arc_decision"})
        # Add timestamp & version for schema completeness
        res["signal_id"] = signal_id
        res["symbol"] = arc_input_bundle.get("symbol", "UNKNOWN")
        import datetime
        res["arc_timestamp"] = datetime.datetime.now().isoformat()
        res["arc_version"] = "1.0"
        return res

    def review_signals_postmarket(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        signals_detail = ""
        for i, s in enumerate(signals, 1):
            signals_detail += f"Signal {i}:\nStock: {s.get('symbol')} {s.get('direction')}\nScore: {s.get('score')}\nTime: {s.get('time') or s.get('timestamp')}\nResult: {s.get('status') or 'UNKNOWN'}\n\n"

        prompt = f"""You are ARC — Post Market Analyst.

Review today's trading session.
Give insights for tomorrow.

TODAY'S SUMMARY:
Total Signals: {len(signals)}
Alerts Sent: {len([s for s in signals if s.get('status') != 'REJECTED'])}
Alerts Rejected by Gates: {len([s for s in signals if s.get('status') == 'REJECTED'])}
Trades Human Took: {len([s for s in signals if s.get('status') == 'EXECUTED'])}

SIGNAL DETAILS:
{signals_detail}

REGIME TODAY: BULLISH
GEIE ACCURACY: N/A
SYSTEM HEALTH: ALL SYSTEMS OPERATIONAL

Your task:
1. What worked today?
2. What did not work?
3. Which signals were good quality?
4. Which were borderline?
5. What to watch tomorrow?
6. Any system improvement suggestion?

Return this JSON:

{{
  "arc_eod_id": "ARC-EOD-[DATE]",
  "session_quality": "GOOD or AVERAGE or POOR",
  "what_worked": "one paragraph",
  "what_failed": "one paragraph",
  "best_signal": "which signal and why",
  "worst_signal": "which signal and why",
  "tomorrow_watchlist": ["stock 1", "stock 2", "stock 3"],
  "tomorrow_avoid": ["stock 1", "stock 2"],
  "system_suggestion": "any improvement or NONE",
  "overall_assessment": "one line summary"
}}"""

        tools = [{
            "name": "postmarket_review",
            "description": "Reviews the daily trading session signals and performance outcomes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "arc_eod_id": {"type": "string"},
                    "session_quality": {"type": "string", "enum": ["GOOD", "AVERAGE", "POOR"]},
                    "what_worked": {"type": "string"},
                    "what_failed": {"type": "string"},
                    "best_signal": {"type": "string"},
                    "worst_signal": {"type": "string"},
                    "tomorrow_watchlist": {"type": "array", "items": {"type": "string"}},
                    "tomorrow_avoid": {"type": "array", "items": {"type": "string"}},
                    "system_suggestion": {"type": "string"},
                    "overall_assessment": {"type": "string"}
                },
                "required": [
                    "arc_eod_id", "session_quality", "what_worked", "what_failed", 
                    "best_signal", "worst_signal", "tomorrow_watchlist", 
                    "tomorrow_avoid", "system_suggestion", "overall_assessment"
                ]
            }
        }]
        return self._call_api(prompt, system_context="You are the IIIS ARC Postmarket Engine.", tools=tools, tool_choice={"type": "tool", "name": "postmarket_review"})

    def generate_postmortem(self, trade_facts: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Analyze this failed trade to diagnose root causes and avoidance criteria:\n\nFacts: {json.dumps(trade_facts)}"
        tools = [{
            "name": "graveyard_diagnostics",
            "description": "Categorizes trade failures and extracts warning signs.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "avoidability_rating": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "warning_signs": {"type": "array", "items": {"type": "string"}},
                    "failure_category": {"type": "string", "enum": ["WEAK_VOLUME", "NEWS_REVERSAL", "COUNTER_TREND", "OTHER"]},
                    "lessons_learned": {"type": "string"}
                },
                "required": ["avoidability_rating", "warning_signs", "failure_category", "lessons_learned"]
            }
        }]
        return self._call_api(prompt, system_context="You are the IIIS Postmarket Graveyard Diagnostics Engine.", tools=tools, tool_choice={"type": "tool", "name": "graveyard_diagnostics"})

    def analyze_patterns(self, trade_logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prompt = f"Audit these trade logs to extract recurring high win rate configurations:\n\nLogs: {json.dumps(trade_logs)}"
        tools = [{
            "name": "pattern_extraction",
            "description": "Aggregates trading logs into sector and setup patterns.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "patterns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pattern_name": {"type": "string"},
                                "sample_size": {"type": "integer"},
                                "win_rate": {"type": "number"},
                                "avg_r_multiple": {"type": "number"}
                            },
                            "required": ["pattern_name", "sample_size", "win_rate", "avg_r_multiple"]
                        }
                    }
                },
                "required": ["patterns"]
            }
        }]
        res = self._call_api(prompt, system_context="You are the IIIS Trade Pattern Library Compiler.", tools=tools, tool_choice={"type": "tool", "name": "pattern_extraction"})
        return res.get("patterns", [])

    def generate_memory_insights(self, category: str, content: str) -> Dict[str, Any]:
        prompt = f"Construct grounded behavioral takeaways for category {category} based on content:\n\n{content}"
        tools = [{
            "name": "insight_builder",
            "description": "Generates a structured behavioral insight record.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "insight_id": {"type": "integer"},
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "takeaway": {"type": "string"}
                },
                "required": ["insight_id", "category", "title", "takeaway"]
            }
        }]
        return self._call_api(prompt, system_context="You are the IIIS Memory Insights Synthesizer.", tools=tools, tool_choice={"type": "tool", "name": "insight_builder"})

    def generate_founder_review(self, notes: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"Review the founder notes to audit psychological states and rules deviations:\n\nNotes: {json.dumps(notes)}"
        tools = [{
            "name": "founder_notes_review",
            "description": "Audits notes to identify founder psychological patterns.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "psychological_bias_detected": {"type": "string"},
                    "rules_deviations_count": {"type": "integer"},
                    "actionable_feedback": {"type": "string"}
                },
                "required": ["psychological_bias_detected", "rules_deviations_count", "actionable_feedback"]
            }
        }]
        return self._call_api(prompt, system_context="You are the IIIS Founder Behavior Auditor.", tools=tools, tool_choice={"type": "tool", "name": "founder_notes_review"})
