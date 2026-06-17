# Telegram Alerts and Formats Specification

This document defines the exact layout, structure, and rules for all Telegram messages sent by the IIIS bot.

---

## 1. System Alert Format (Mandatory layout)

Every trade signal alert sent to the Telegram channel must match this exact format. No placeholders or empty blocks are allowed:

```text
🚨 IIIS SIGNAL ALERT

Signal ID: IIIS-YYYY-MM-DD-NNN
Time: HH:MM AM IST
Valid Until: HH:MM AM IST (calculated from regime rules, Section 16)

Stock: SYMBOL
Direction: LONG or SHORT
Score: XX out of 100
Confidence: HIGH or MEDIUM or LOW
Risk Grade: A+ or A or B+ or B or C

Market Context:
Regime: [Trend Day / Expiry Day / Reversal Day / Transition Day / Range Day]
Sector Rank: [number]
RS Percentile: [number]
Volume: [N]x average
VIX: [number]

Trade Levels:
Entry Zone: XXX to XXX
Stop Loss: XXX
Target 1: XXX (1.5R)
Target 2: XXX (2.5R)
Quantity: NNN shares
Risk: ₹XXX (0.5%)

Intelligence:
GEIE Direction: POSITIVE or NEGATIVE or NEUTRAL or UNAVAILABLE
GEIE Reason: [one line here]
Historical Win Rate: XX% (N setups found)
ARC Pre-Market: APPROVE or CAUTION or REJECT or UNREVIEWED

SMC Structure: [5m signal] + [15m signal]
Options: [build-up type here]

💰 BIG MONEY SIGNALS
FII Trend: [BUYER/SELLER] [N] days [✅/❌]
Bulk Deal: [Rs XXCr BUY/SELL at HH:MM] [✅/❌]
Options: [PUT/CALL writing heavy at strike] [✅/❌]
OB Zone: [level] (tested [N]x, held [N]x) [✅/❌]
RS Diverge: [+/-X.X%] vs NIFTY [+/-X.X%] [✅/❌]
Big Money Score: [XX]/100
Conclusion: [Institutions accumulating/distributing/neutral]

⚠️ This is an intelligence alert only.
Human decision required.
System never executes trades.

Alert expires: HH:MM AM IST
```

---

## 2. Ghost Mode Admin Notification

When Ghost Mode is activated by any system trigger, the following admin notification must be sent immediately:

```text
🚨 GHOST MODE ACTIVATED

Reason: [state reason here]
Time: [timestamp here]

All alerts stopped.
Data integrity may be compromised.

Send /resume command to restart.
Manual verification required before resume.
```

---

## 3. Pre-Market Watchlist Notification (08:20 AM IST)

At the completion of the pre-market review loop, the system sends the following summary:
```text
ARC Premarket Review Complete: {approve_count} APPROVE / {caution_count} CAUTION / {reject_count} REJECT
```
Where `approve_count`, `caution_count`, and `reject_count` are the count of watchlist stocks evaluated under each category.
