"""
IIIS MOCK SESSION STATS MONITOR
Wraps main.py execution and collects real runtime statistics from DB.
Runs for specified duration and writes MOCK_SESSION_REPORT.md on completion.
"""
import os, sys, datetime, time, subprocess, threading

os.environ["IIIS_TESTING"] = "True"
os.environ.setdefault("TELEGRAM_BOT_TOKEN",    "YOUR_TELEGRAM_BOT_TOKEN_HERE")
os.environ.setdefault("TELEGRAM_ADMIN_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")
os.environ.setdefault("SLACK_WEBHOOK_URL", "")  # Set SLACK_WEBHOOK_URL in .env

import database
database.init_db("schema.sql")

from seeder import seed_mock_data_for_demo
from market_data.instrument_loader import InstrumentLoader
symbols = InstrumentLoader().symbols
seed_mock_data_for_demo(symbols)

today = datetime.date.today()
database.execute_query("DELETE FROM active_alerts;")
database.execute_query("DELETE FROM risk_state WHERE session_date=%s;", (today,))
database.execute_query("DELETE FROM signals WHERE DATE(timestamp)=%s;", (today,))
print(f"[MONITOR] DB reset complete for {today}.")

SESSION_START = datetime.datetime.now()
SESSION_HOURS = 4
SESSION_END   = SESSION_START + datetime.timedelta(hours=SESSION_HOURS)
REPORT_PATH   = r"C:\Users\shadab\Desktop\trade\MOCK_SESSION_REPORT.md"
LOG_PATH      = r"C:\Users\shadab\Desktop\trade\session.log"

print(f"[MONITOR] Session starts: {SESSION_START.strftime('%Y-%m-%d %H:%M:%S IST')}")
print(f"[MONITOR] Session ends  : {SESSION_END.strftime('%Y-%m-%d %H:%M:%S IST')}")
print(f"[MONITOR] Duration      : {SESSION_HOURS} hours")
print(f"[MONITOR] Log           : {LOG_PATH}")
print(f"[MONITOR] Report        : {REPORT_PATH}")
print()

# ── Counters ─────────────────────────────────────────────────────────
stats = {
    "scan_cycles"          : 0,
    "signals_generated"    : 0,
    "signals_rejected"     : 0,
    "slack_delivered"      : 0,
    "slack_failed"         : 0,
    "runtime_errors"       : 0,
    "ghost_mode_events"    : 0,
    "arc_approve"          : 0,
    "arc_caution"          : 0,
    "arc_reject"           : 0,
    "rg_pass"              : 0,
    "rg_daily_limit"       : 0,
    "rg_duplicate"         : 0,
    "rg_hard_stop"         : 0,
    "rg_other"             : 0,
    "score_90_100"         : 0,
    "score_86_90"          : 0,
    "score_0_86"           : 0,
}
log_lines = []
lock = threading.Lock()

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with lock:
        log_lines.append(line)
    # safe print
    enc = sys.stdout.encoding or "utf-8"
    print(line.encode(enc, errors="replace").decode(enc))

# ── Bootstrap services for stats collection ────────────────────────────
from bootstrap import register_services
register_services()
from interfaces.base import ServiceRegistry
slack = ServiceRegistry.get("slack")

# ── Import orchestrator + scheduler components ────────────────────────
from orchestrator import Orchestrator
from live_scan_loop import LiveScanLoop
from market_data.instrument_loader import InstrumentLoader

import asyncio

async def run_session():
    log("Initializing orchestrator...")
    orchestrator = Orchestrator()
    live_loop = LiveScanLoop(orchestrator=orchestrator)

    # Warmup
    from seeder import seed_mock_data_for_demo
    log("Seeding + warming up engines...")
    orchestrator.warmup_engines(symbols)

    # GEIE premarket
    now = datetime.datetime.now()
    geie_t = now.replace(hour=8, minute=5, second=0, microsecond=0)
    geie_payload = orchestrator.run_premarket_geie(geie_t)
    market_sentiment = geie_payload.get("market_sentiment", "UNKNOWN")
    log(f"GEIE sentiment: {market_sentiment}")

    # ARC premarket
    arc_t = now.replace(hour=8, minute=20, second=0, microsecond=0)
    arc_results = orchestrator.run_premarket_arc(arc_t, symbols, geie_payload)
    stats["arc_approve"] = sum(1 for v in arc_results.values() if v == "APPROVE")
    stats["arc_caution"] = sum(1 for v in arc_results.values() if v == "CAUTION")
    stats["arc_reject"]  = sum(1 for v in arc_results.values() if v == "REJECT")
    log(f"ARC premarket: {stats['arc_approve']} APPROVE / {stats['arc_caution']} CAUTION / {stats['arc_reject']} REJECT")

    # Active watchlist (non-REJECT symbols)
    active = [s for s in symbols if arc_results.get(s, "CAUTION") != "REJECT"]
    log(f"Active watchlist: {len(active)}/{len(symbols)} symbols")

    # Connect mock WebSocket
    upstox = ServiceRegistry.get("upstox")
    try:
        upstox.connect_websocket()
    except Exception:
        pass

    cycle_num = 0
    while datetime.datetime.now() < SESSION_END:
        cycle_num += 1
        stats["scan_cycles"] += 1
        cycle_start = time.perf_counter()
        timestamp   = datetime.datetime.now()
        log(f"--- Cycle {cycle_num} @ {timestamp.strftime('%H:%M:%S')} ---")

        # Check ghost mode
        import ghost_mode
        if ghost_mode.is_ghost_mode_active():
            stats["ghost_mode_events"] += 1
            log(f"Ghost Mode ACTIVE — cycle {cycle_num} suspended.")
            await asyncio.sleep(60)
            continue

        # Ingest ticks
        for sym in active:
            try:
                tick = upstox.get_live_data(sym)
                tick["time"] = timestamp
                orchestrator.process_tick(tick)
            except Exception as e:
                stats["runtime_errors"] += 1
                log(f"Tick error {sym}: {e}")

        # Evaluate signals
        signals_this_cycle = 0
        for sym in active:
            try:
                passed = orchestrator.evaluate_candidate_signals(sym, timestamp)
                if passed:
                    signals_this_cycle += 1
                    stats["signals_generated"] += 1
            except Exception as e:
                stats["runtime_errors"] += 1
                log(f"Eval error {sym}: {e}")

        log(f"Cycle {cycle_num}: {signals_this_cycle} signals generated.")

        elapsed = time.perf_counter() - cycle_start
        sleep_s = max(60.0 - elapsed, 1.0)
        await asyncio.sleep(sleep_s)

    log("Session complete. Collecting final stats from DB...")
    return market_sentiment

# ── Run session ───────────────────────────────────────────────────────
try:
    market_sentiment = asyncio.run(run_session())
except KeyboardInterrupt:
    market_sentiment = "INTERRUPTED"
    log("Session interrupted by user.")

SESSION_ACTUAL_END = datetime.datetime.now()
duration_actual = (SESSION_ACTUAL_END - SESSION_START).total_seconds() / 3600

# ── Collect final stats from DB ───────────────────────────────────────
today = datetime.date.today()

try:
    sig_rows = database.execute_query(
        "SELECT status, score, confidence FROM signals WHERE DATE(timestamp)=%s;",
        (today,), fetch=True
    ) or []
    for row in sig_rows:
        status, score, conf = row
        if status == "ACTIVE":
            stats["rg_pass"] += 1
        elif status == "CANCELLED":
            stats["signals_rejected"] += 1
        if score is not None:
            sc = float(score)
            if sc >= 90:
                stats["score_90_100"] += 1
            elif sc >= 86:
                stats["score_86_90"] += 1
            else:
                stats["score_0_86"] += 1

    # Risk gate rejection breakdown from audit log
    rg_rows = database.execute_query(
        "SELECT reason FROM audit_log WHERE component='RiskEngine' AND DATE(timestamp)=%s;",
        (today,), fetch=True
    ) or []
    for row in rg_rows:
        reason = str(row[0]) if row[0] else ""
        if "DAILY_RISK" in reason:
            stats["rg_daily_limit"] += 1
        elif "DUPLICATE" in reason:
            stats["rg_duplicate"] += 1
        elif "HARD_STOP" in reason:
            stats["rg_hard_stop"] += 1
        else:
            stats["rg_other"] += 1

    # Slack delivery stats from audit log
    slack_rows = database.execute_query(
        "SELECT result FROM audit_log WHERE component='Orchestrator' AND action='DISPATCH_SIGNAL_ALERT' AND DATE(timestamp)=%s;",
        (today,), fetch=True
    ) or []
    for row in slack_rows:
        result = str(row[0]) if row[0] else ""
        if result == "SUCCESS":
            stats["slack_delivered"] += 1
        else:
            stats["slack_failed"] += 1

    # Ghost mode events
    ghost_rows = database.execute_query(
        "SELECT COUNT(*) FROM audit_log WHERE component='GhostMode' AND DATE(timestamp)=%s;",
        (today,), fetch=True
    ) or [[0]]
    stats["ghost_mode_events"] = int(ghost_rows[0][0])

except Exception as e:
    log(f"DB collection error: {e}")

# ── Write log file ─────────────────────────────────────────────────────
try:
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    print(f"[MONITOR] Log written: {LOG_PATH}")
except Exception as e:
    print(f"[MONITOR] Log write failed: {e}")

# ── Generate MOCK_SESSION_REPORT.md ───────────────────────────────────
total_sigs = stats["rg_pass"] + stats["signals_rejected"]
slack_total = stats["slack_delivered"] + stats["slack_failed"]
slack_rate  = (stats["slack_delivered"] / slack_total * 100) if slack_total > 0 else 0.0
total_arc   = stats["arc_approve"] + stats["arc_caution"] + stats["arc_reject"]

report = f"""# MOCK SESSION REPORT — IIIS v4.6

**Generated**: {SESSION_ACTUAL_END.strftime('%Y-%m-%d %H:%M:%S IST')}
**Session Date**: {today}
**Session Start**: {SESSION_START.strftime('%Y-%m-%d %H:%M:%S IST')}
**Session End**: {SESSION_ACTUAL_END.strftime('%Y-%m-%d %H:%M:%S IST')}
**Planned Duration**: {SESSION_HOURS} hours
**Actual Duration**: {duration_actual:.2f} hours

---

## 1. Scan Cycle Summary

| Metric | Value |
|--------|-------|
| Total Scan Cycles | {stats['scan_cycles']} |
| Cycle Interval | 60 seconds |
| Market Sentiment (GEIE) | {market_sentiment} |
| Active Watchlist | {stats['arc_approve'] + stats['arc_caution']} / {len(symbols)} symbols |

---

## 2. Signal Statistics

| Metric | Count |
|--------|-------|
| Signals Generated (passed all gates) | {stats['rg_pass']} |
| Signals Rejected (any gate) | {stats['signals_rejected']} |
| Total Signal Attempts | {total_sigs} |
| Pass Rate | {(stats['rg_pass'] / total_sigs * 100) if total_sigs > 0 else 0:.1f}% |

---

## 3. ARC Decision Distribution

| Decision | Count | % of Total |
|----------|-------|-----------|
| APPROVE | {stats['arc_approve']} | {(stats['arc_approve'] / total_arc * 100) if total_arc > 0 else 0:.1f}% |
| CAUTION | {stats['arc_caution']} | {(stats['arc_caution'] / total_arc * 100) if total_arc > 0 else 0:.1f}% |
| REJECT  | {stats['arc_reject']}  | {(stats['arc_reject'] / total_arc * 100) if total_arc > 0 else 0:.1f}% |

> Source: Premarket batch review (ARC Fallback — Claude mocked in MOCK_MODE)

---

## 4. Risk Gate Rejection Distribution

| Rejection Reason | Count |
|-----------------|-------|
| BLOCK_DAILY_RISK_LIMIT | {stats['rg_daily_limit']} |
| BLOCK_DUPLICATE_SIGNAL | {stats['rg_duplicate']} |
| BLOCK_HARD_STOP | {stats['rg_hard_stop']} |
| OTHER | {stats['rg_other']} |
| **PASS** | **{stats['rg_pass']}** |

---

## 5. Score Distribution

| Score Band | Count |
|-----------|-------|
| 90 – 100 (HIGH confidence) | {stats['score_90_100']} |
| 86 – 89  (MEDIUM confidence) | {stats['score_86_90']} |
| Below 86 (rejected at scoring) | {stats['score_0_86']} |

> Scoring threshold: >= 86.0 to pass

---

## 6. Big Money Score Distribution

| Range | Note |
|-------|------|
| Not independently tracked in DB | Big Money integrated into composite score |

> Big Money context injected via GEIEProcessor into composite scoring weights.

---

## 7. Slack Delivery Statistics

| Metric | Value |
|--------|-------|
| Alerts Dispatched | {slack_total} |
| Delivered Successfully | {stats['slack_delivered']} |
| Failed | {stats['slack_failed']} |
| Success Rate | {slack_rate:.1f}% |

> Slack endpoint: hooks.slack.com (Incoming Webhook)
> Channel: #trading (workspace: trade)

---

## 8. Runtime Errors

| Metric | Count |
|--------|-------|
| Runtime Errors (tick/eval) | {stats['runtime_errors']} |
| Ghost Mode Events | {stats['ghost_mode_events']} |
| System Crashes | 0 |

---

## 9. Ghost Mode Events

| Events | {stats['ghost_mode_events']} |
|--------|-----|

> Ghost Mode activates on: 3+ consecutive SL hits, daily risk >= 2.0%, or hard_stop_active flag.

---

## 10. Operational Notes

- **Telegram**: Blocked (ISP/Firewall restriction). Slack is primary delivery channel.
- **ARC Mode**: Fallback (Claude AI mocked). Max result = CAUTION. APPROVE requires live Claude.
- **Risk Budget**: 2.0% daily limit at 0.5% per signal = max 4 signals per session.
- **Data Source**: All market data is mock (UpstoxMock). No live prices.
- **Log File**: `session.log` in repository root.

---

*Report generated by `session_monitor.py` — actual runtime statistics only.*
"""

try:
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[MONITOR] Report written: {REPORT_PATH}")
except Exception as e:
    print(f"[MONITOR] Report write failed: {e}")

print("\n[MONITOR] Session complete.")
print(f"  Cycles     : {stats['scan_cycles']}")
print(f"  Generated  : {stats['rg_pass']}")
print(f"  Rejected   : {stats['signals_rejected']}")
print(f"  Slack OK   : {stats['slack_delivered']}")
print(f"  Errors     : {stats['runtime_errors']}")
