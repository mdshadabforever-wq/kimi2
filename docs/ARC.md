# ARC Engine Specification

This document defines the Autonomous Review and Control (ARC) Engine, which acts as an AI-driven veto and confidence layer leveraging the Claude API.

---

## 1. Engine Specifications

* **Role:** Pre-market and post-market ONLY. Never runs in the live 60-second scan (intraday capability has been removed per NC1).
* **Weight:** 0% — does not affect the composite score.
* **Model:** `claude-3-5-sonnet-20241022`
* **Veto Power:** The ARC Engine acts as a final veto layer. It can override an upstream approval to a `REJECT` or tag it with `CAUTION`.

---

## 2. Pre-Market Batch Review (08:20 AM IST)

* **Objective:** Evaluate the daily candidate symbols watchlist.
* **Execution:** Pre-market watchlist is reviewed as a batch using bounded concurrency (**maximum 5 parallel workers**) with a **0.2-second sleep** between worker submissions to respect API rate limits.
* **Output:** For each symbol, returns one of the following decision labels:
  * `APPROVE` — Normal processing.
  * `CAUTION` — Stock remains on the watchlist, but any alerts generated are tagged with `ARC: CAUTION`.
  * `REJECT` — Stock is removed from the watchlist; no alerts can be generated for this stock today.
* **Hard Cutoff (08:50 AM IST):** Any symbol not reviewed before 08:50 AM IST is automatically assigned `CAUTION` with a confidence score of 30.

---

## 3. Post-Market Review (04:00 PM IST)

* **Objective:** Review executed signals and outcome data to compile feedback for next-day watchlist inputs.
* **Output:** Internal analytics event logged to database (not delivered to Telegram).

---

## 4. Claude API prompt and Decision Schema

### Prompt Structure
ARC constructs structured payloads including trend alignment direction, SMC structure details, options PCR and pain levels, composite score, risk states, and GEIE impacts.

### Decision JSON Schema (Mandatory)
```json
{
  "$schema": "iiis-arc-decision-v1",
  "signal_id": "string",
  "symbol": "string",
  "arc_decision": "APPROVE | CAUTION | REJECT",
  "arc_confidence": 0-100,
  "reasoning_summary": "string (max 300 chars)",
  "engine_alignment": {
    "trend": "AGREE | PARTIAL | DISAGREE",
    "smc": "AGREE | PARTIAL | DISAGREE",
    "options": "AGREE | PARTIAL | DISAGREE",
    "scoring": "AGREE | PARTIAL | DISAGREE",
    "risk": "AGREE | PARTIAL | DISAGREE",
    "geie": "AGREE | PARTIAL | DISAGREE"
  },
  "conflict_flags": ["string"],
  "reject_reasons": ["string"],
  "caution_reasons": ["string"],
  "explainability": {
    "bullish_factors": ["string"],
    "bearish_factors": ["string"],
    "neutral_factors": ["string"]
  },
  "arc_timestamp": "ISO-8601 UTC+05:30",
  "arc_version": "1.0"
}
```

---

## 5. ARC Veto & Reject Rules

ARC will issue a `REJECT` decision if any of the following rules are triggered:

| Code | Reject Trigger |
|---|---|
| `ARC_R01` | Trend direction contradicts SMC direction (e.g., Trend=BEARISH but SMC=LONG). |
| `ARC_R02` | GEIE `direction == "NEGATIVE"` AND `confidence == "HIGH"` for a LONG signal. |
| `ARC_R03` | GEIE `direction == "POSITIVE"` AND `confidence == "HIGH"` for a SHORT signal. |
| `ARC_R04` | `hard_stop_active == true` in risk state. |
| `ARC_R05` | `final_composite_score < 86.0` (scores below 86 are rejected). |
| `ARC_R06` | `smc_input.direction == "NO_DIRECTION"`. |
| `ARC_R07` | `trend_input.is_aligned == false` AND `smc_input.score < 70`. |
| `ARC_R08` | Market sentiment `"RISK_OFF"` AND signal direction is LONG AND GEIE confidence is HIGH. |
| `ARC_R09` | Claude API failure/JSON parse failure after 1 retry and no valid cache. |

---

## 6. Caching & Restart Recovery

### Redis Cache Keys
* `arc:premarket:{date}:{symbol}` (TTL: 24 hours) — Stores pre-market decision per symbol.
* `arc:watchlist:{date}` (TTL: 24 hours) — Watchlist decision map `{symbol: decision}`.

### Restart Recovery
1. **Load Watchlist Cache:** Read `arc:watchlist:{date}` from Redis. If present, restore the in-memory approval map.
2. **If Redis is Empty:** Re-run pre-market batch review to rebuild watchlist cache.

---

## 7. Failure Policy (Fallback Behavior)

If the Claude API times out (10s limit) or errors, ARC attempts **1 retry**. If the retry also fails:
1. Log the fallback trigger with `result = "FALLBACK"` and the error message to the `audit_log`.
2. Apply the fallback decision rules:
   * **Rule 1:** If `composite_score >= 90.0` and all 5 non-Claude engines `AGREE`:
     * `arc_decision = "CAUTION"`, `arc_confidence = 60`.
   * **Rule 2:** If `composite_score >= 86.0` and at least 4 engines `AGREE`:
     * `arc_decision = "CAUTION"`, `arc_confidence = 40`.
   * **Rule 3:** Otherwise:
     * `arc_decision = "REJECT"`, `arc_confidence = 0`.
3. **Critical Rule:** ARC fallback **never** issues `APPROVE`. All unreviewed stocks default to `CAUTION` (or `REJECT` if the fallback criteria are not met).
