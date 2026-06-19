import datetime

# 2026 NSE Trading Holidays
NSE_HOLIDAYS = {
    datetime.date(2026, 1, 26),  # Republic Day
    datetime.date(2026, 3, 6),   # Mahashivratri
    datetime.date(2026, 3, 14),  # Holi
    datetime.date(2026, 4, 3),   # Good Friday
    datetime.date(2026, 4, 14),  # Ambedkar Jayanti
    datetime.date(2026, 5, 1),   # Maharashtra Day
    datetime.date(2026, 8, 15),  # Independence Day
    datetime.date(2026, 10, 2),  # Gandhi Jayanti
    datetime.date(2026, 10, 22), # Dussehra
    datetime.date(2026, 11, 12), # Diwali (Balipratipada)
    datetime.date(2026, 12, 25), # Christmas
}

def is_trading_day(dt: datetime.date) -> bool:
    """Checks if a date is a valid trading day for NSE (excludes weekends and public holidays)."""
    if dt.weekday() in (5, 6): # Saturday, Sunday
        return False
    if dt in NSE_HOLIDAYS:
        return False
    return True

def is_market_session_active(dt: datetime.datetime) -> bool:
    """Returns True if the datetime is within NSE normal market hours (09:15 to 15:30) on a trading day."""
    if not is_trading_day(dt.date()):
        return False
    t = dt.time()
    return datetime.time(9, 15) <= t <= datetime.time(15, 30)

def get_seconds_until_next_market_open(dt: datetime.datetime) -> float:
    """Calculates the number of seconds from the current time until the next market open (09:15 AM on a trading day)."""
    current_dt = dt
    while True:
        # Check if next open is today or a future day
        target_date = current_dt.date()
        target_open = datetime.datetime.combine(target_date, datetime.time(9, 15))
        
        if is_trading_day(target_date) and current_dt < target_open:
            return (target_open - current_dt).total_seconds()
        
        # Advance to tomorrow 12:00 AM
        current_dt = datetime.datetime.combine(target_date + datetime.timedelta(days=1), datetime.time(0, 0))
