"""
GitHub Actions runners use UTC as their system time, not IST. Every market-
hours / time-of-day check in this bot MUST go through this helper instead
of dt.datetime.now() directly, or it will silently think the market is
closed all day (this was the bug that caused "Market closed" on every run).
"""
import datetime as dt

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)
