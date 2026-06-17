import datetime
from interfaces.base import ServiceRegistry
from audit import log_audit
import redis_client

# Local in-memory state fallback if Redis is down
_ghost_mode_local = False

def is_ghost_mode_active() -> bool:
    """Returns True if Ghost Mode is active."""
    global _ghost_mode_local
    try:
        val = redis_client.get_val("iiis:ghost_mode_active")
        if val is not None:
            return val == "True"
    except Exception as e:
        print(f"Redis check for Ghost Mode failed, falling back to local memory: {e}")
    return _ghost_mode_local

def activate_ghost_mode(reason: str):
    """Triggers Ghost Mode: ceases alert generation, logs to audit, and alerts admin."""
    global _ghost_mode_local
    if is_ghost_mode_active():
        return # Already active
        
    _ghost_mode_local = True
    
    # Store in Redis if possible
    try:
        redis_client.set_val("iiis:ghost_mode_active", "True")
    except Exception as e:
        print(f"Failed to persist Ghost Mode state to Redis: {e}")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    
    # 1. Log to Audit
    try:
        log_audit(
            component="SystemSafety",
            action="ACTIVATE_GHOST_MODE",
            result="SUCCESS",
            reason=reason,
            metadata={"timestamp": timestamp}
        )
    except Exception as e:
        print(f"Failed to log Ghost Mode activation to audit: {e}")

    # 2. Send Telegram Admin Notification
    telegram_msg = (
        f"🚨 GHOST MODE ACTIVATED\n\n"
        f"Reason: {reason}\n"
        f"Time: {timestamp}\n\n"
        f"All alerts stopped.\n"
        f"Data integrity may be compromised.\n\n"
        f"Send /resume command to restart.\n"
        f"Manual verification required before resume."
    )
    
    try:
        telegram = ServiceRegistry.get("telegram")
        telegram.send_admin_warning(telegram_msg)
    except Exception as e:
        print(f"Failed to send Ghost Mode Telegram alert: {e}")
        
    # 3. Purge alert queue
    try:
        redis_client.delete_val("iiis:alert_queue")
    except Exception as e:
        print(f"Failed to purge alert queue from Redis: {e}")
        
    print(f"*** GHOST MODE ACTIVATED: {reason} ***")

def resume_system() -> bool:
    """Resets Ghost Mode. Requires manual admin approval."""
    global _ghost_mode_local
    if not is_ghost_mode_active():
        return False
        
    _ghost_mode_local = False
    try:
        redis_client.set_val("iiis:ghost_mode_active", "False")
    except Exception as e:
        print(f"Failed to reset Ghost Mode in Redis: {e}")
        
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    
    # Log to Audit
    try:
        log_audit(
            component="SystemSafety",
            action="RESUME_SYSTEM",
            result="SUCCESS",
            reason="Manual /resume command received from admin.",
            metadata={"timestamp": timestamp}
        )
    except Exception as e:
        print(f"Failed to log resume to audit: {e}")
        
    # Alert admin of resume
    try:
        telegram = ServiceRegistry.get("telegram")
        telegram.send_admin_warning("✅ IIIS System Resumed. Normal monitoring active.")
    except Exception as e:
        print(f"Failed to send resume Telegram confirmation: {e}")
        
    print("*** SYSTEM RESUMED: Ghost Mode cleared ***")
    return True
